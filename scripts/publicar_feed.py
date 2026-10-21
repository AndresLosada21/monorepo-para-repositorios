"""Publica as versoes no feed de pacotes do Azure Artifacts, na ordem das dependencias.

Versao publicada no feed e imutavel: antes de publicar, o script confere se a versao ja existe
e, se ja existir, avisa que a proxima versao e a saida. A credencial fica so em memoria.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifesto import carregar, ordem_publicacao, validar  # noqa: E402

RECURSO = "499b84ac-1321-427f-aa17-267ca6975798"


def _token() -> str:
    az = "az.cmd" if sys.platform == "win32" else "az"
    r = subprocess.run([az, "account", "get-access-token", "--resource", RECURSO,
                        "--query", "accessToken", "-o", "tsv"], capture_output=True, text=True)
    return r.stdout.strip()


def url_do_feed(m: dict, tipo: str) -> str:
    """Endereco do feed para Maven ou para npm."""
    projeto = urllib.parse.quote(m["projeto"])
    if tipo == "npm":
        return f"https://pkgs.dev.azure.com/{m['org']}/{projeto}/_packaging/{m['feed']}/npm/registry/"
    return f"https://pkgs.dev.azure.com/{m['org']}/{projeto}/_packaging/{m['feed']}/maven/v1"


def versoes_no_feed(m: dict, token: str) -> dict:
    """Mapa artefato -> versoes ja publicadas.

    A API de pacotes fica no host feeds.dev.azure.com. O host pkgs.dev.azure.com
    serve os artefatos, mas nao responde a consulta de pacotes.
    """
    url = (f"https://feeds.dev.azure.com/{m['org']}/{urllib.parse.quote(m['projeto'])}"
           f"/_apis/Packaging/Feeds/{m['feed']}/Packages?api-version=7.1")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            d = json.loads(r.read() or b"{}")
    except Exception:
        return {}
    mapa = {}
    for p in d.get("value", []):
        nome = p.get("name", "")
        if nome.startswith("br.com") or nome.startswith("@"):
            mapa[nome] = [v.get("version") for v in p.get("versions", [])]
    return mapa


def versao_publicada(feed: str, artefato: str, versao: str, token: str) -> bool:
    """True quando a versao ja esta no feed."""
    return versao in (versoes_no_feed(feed, token).get(artefato) or [])


def comandos_publicar(c: dict, feed_url: str) -> list[list[str]]:
    """Comandos de publicacao de um componente. Nao executa nada.

    O Maven tira o destino do distributionManagement do pom.xml; o comando mostra a URL
    para o operador conferir para onde esta indo.
    """
    if c["tipo"] == "npm-pkg":
        return [["npm", "publish", "--registry", feed_url]]
    return [["mvn", "-B", "deploy", "-s", "settings-feed.xml", "-Dmaven.repo.local=REPO_LOCAL",
             f"-Ddestino={feed_url}"]]


def _settings_maven(feed_url: str, destino: Path) -> Path:
    """settings.xml temporario, com a credencial por variavel de ambiente."""
    destino.write_text(f"""<settings>
  <servers>
    <server>
      <id>mfg-java</id>
      <username>${{env.MAVEN_FEED_USER}}</username>
      <password>${{env.MAVEN_FEED_TOKEN}}</password>
    </server>
  </servers>
  <mirrors>
    <mirror>
      <id>mfg-java</id>
      <mirrorOf>*</mirrorOf>
      <url>{feed_url}</url>
    </mirror>
  </mirrors>
</settings>
""", encoding="utf-8", newline="\n")
    return destino


def _npmrc(feed_url: str, destino: Path) -> Path:
    """Arquivo de usuario do npm com a credencial, apagado no fim."""
    destino.write_text(f"{feed_url}:_authToken={os.environ['MAVEN_FEED_TOKEN']}\n", encoding="ascii")
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publica as versoes no feed, na ordem das dependencias.")
    ap.add_argument("--manifesto", required=True)
    ap.add_argument("--repositorios", required=True, help="pasta com um clone de cada repositorio")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    m = carregar(args.manifesto)
    erros = validar(m)
    if erros:
        print("manifesto com problemas:")
        for e in erros:
            print("  ", e)
        return 2

    clones = Path(args.repositorios)
    componentes = {c["repo"]: c for c in m["componentes"]}
    ordem = ordem_publicacao(m)

    # o dry-run tambem consulta o feed: mostra o que ja esta publicado
    token = _token()
    publicados = versoes_no_feed(m, token)

    print(f"ordem de publicacao: {' -> '.join(ordem)}")
    for repo in ordem:
        c = componentes[repo]
        versoes = publicados.get(c["artefato"], [])
        ja_existe = c["versao"] in versoes
        feed_url = url_do_feed(m, "npm" if c["tipo"] == "npm-pkg" else "maven")
        situacao = "JA EXISTE (a proxima versao e a saida)" if ja_existe else "nova"
        print(f"  {repo:<24} {c['artefato']:<40} {c['versao']:<10} {situacao}")
        if args.dry_run:
            for cmd in comandos_publicar(c, feed_url):
                print("      ", " ".join(cmd))
            continue
        if ja_existe:
            print("      ", "pulado: versao publicada e imutavel")
            continue
        pasta = clones / repo
        if not pasta.exists():
            print("      ", f"pulado: clone ausente em {pasta}")
            continue

        env = dict(os.environ)
        env["MAVEN_FEED_USER"] = "VSTS"
        env["MAVEN_FEED_TOKEN"] = token
        with tempfile.TemporaryDirectory() as tmp:
            if c["tipo"] == "npm-pkg":
                rc = _npmrc(feed_url, Path(tmp) / "npmrc")
                env["NPM_CONFIG_USERCONFIG"] = str(rc)
                cmd = ["npm", "publish", "--registry", feed_url]
                r = subprocess.run(cmd, cwd=pasta, env=env, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
            else:
                settings = _settings_maven(feed_url, Path(tmp) / "settings.xml")
                cmd = ["mvn", "-B", "deploy", "-s", str(settings),
                       "-Dmaven.repo.local=" + str(Path(tmp) / "m2")]
                r = subprocess.run(cmd, cwd=pasta, env=env, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
        if r.returncode:
            print("      ", "FALHOU:", (r.stdout + r.stderr).strip()[-300:])
            return 1
        print("      ", "publicado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
