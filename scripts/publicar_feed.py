"""Publica as versoes no feed de pacotes do Azure Artifacts, na ordem das dependencias.

Versao publicada no feed e imutavel: antes de publicar, o script confere se a versao ja existe
e, se ja existir, avisa que a proxima versao e a saida. A credencial fica so em memoria.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifesto import carregar, ordem_publicacao, validar  # noqa: E402

RECURSO = "499b84ac-1321-427f-aa17-267ca6975798"


def _executavel(nome: str) -> str:
    """No Windows, o comando vive em nome.cmd; sem o .cmd o CreateProcess nao acha."""
    achado = shutil.which(nome)
    if achado:
        return achado
    if os.name == "nt":
        return nome + ".cmd"
    return nome


def _token() -> str:
    az = "az.cmd" if sys.platform == "win32" else "az"
    r = subprocess.run([az, "account", "get-access-token", "--resource", RECURSO,
                        "--query", "accessToken", "-o", "tsv"], capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        raise SystemExit("nao foi possivel obter o token: rode 'az login' e de novo")
    return r.stdout.strip()


def url_do_feed(m: dict, tipo: str) -> str:
    """Endereco do feed para Maven ou para npm."""
    projeto = urllib.parse.quote(m["projeto"])
    if tipo == "npm":
        return f"https://pkgs.dev.azure.com/{m['org']}/{projeto}/_packaging/{m['feed']}/npm/registry/"
    return f"https://pkgs.dev.azure.com/{m['org']}/{projeto}/_packaging/{m['feed']}/maven/v1"


def _mapa_de_pacotes(dados: dict) -> dict:
    """Mapa artefato -> versoes, de qualquer grupo ou escopo."""
    mapa = {}
    for p in dados.get("value", []):
        nome = p.get("name", "")
        if not nome:
            continue
        mapa[nome] = [v.get("version") for v in p.get("versions", [])]
    return mapa


def versoes_no_feed(m: dict, token: str) -> dict | None:
    """Mapa artefato -> versoes ja publicadas. None quando a leitura falha.

    A API de pacotes fica no host feeds.dev.azure.com. O host pkgs.dev.azure.com serve o
    artefato para download, mas nao responde a essa consulta.
    """
    url = (f"https://feeds.dev.azure.com/{m['org']}/{urllib.parse.quote(m['projeto'])}"
           f"/_apis/Packaging/Feeds/{m['feed']}/Packages?api-version=7.1")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            dados = json.loads(r.read() or b"{}")
    except Exception as e:
        print(f"nao foi possivel ler o feed: {e}")
        return None
    return _mapa_de_pacotes(dados)


def token_npmrc(feed_url: str, token: str) -> str:
    """Linha do .npmrc com a credencial.

    O npm procura a credencial pela chave //host/path/:_authToken. Na forma https:// o
    npm nao encontra e falha com "need auth".
    """
    sem_esquema = feed_url.split("://", 1)[-1]
    return f"//{sem_esquema}:_authToken={token}\n"


def settings_maven(feed_url: str, feed_id: str) -> str:
    """settings.xml com a credencial por variavel de ambiente.

    O mirrorOf fica restrito ao proprio feed: com * o build inteiro passaria pelo feed,
    o que amarra o build ao feed e quebra em qualquer feed sem upstream.
    """
    return f"""<settings>
  <servers>
    <server>
      <id>{feed_id}</id>
      <username>${{env.MAVEN_FEED_USER}}</username>
      <password>${{env.MAVEN_FEED_TOKEN}}</password>
    </server>
  </servers>
  <profiles>
    <profile>
      <id>{feed_id}</id>
      <repositories>
        <repository>
          <id>{feed_id}</id>
          <url>{feed_url}</url>
          <releases><enabled>true</enabled></releases>
          <snapshots><enabled>false</enabled></snapshots>
        </repository>
      </repositories>
    </profile>
  </profiles>
  <activeProfiles>
    <activeProfile>{feed_id}</activeProfile>
  </activeProfiles>
</settings>
"""


def comandos_publicar(c: dict, feed_url: str) -> list[list[str]]:
    """Comandos de publicacao de um componente. Nao executa nada.

    O Maven tira o destino do distributionManagement do pom.xml; o comando mostra a URL
    para o operador conferir para onde esta indo.
    """
    if c["tipo"] == "npm-pkg":
        return [[_executavel("npm"), "publish", "--registry", feed_url]]
    return [[_executavel("mvn"), "-B", "deploy", "-s", "settings-feed.xml",
             "-Dmaven.repo.local=REPO_LOCAL", f"-Dfeed={feed_url}"]]


def comandos_de_execucao(c: dict, feed_url: str, settings: str, repo_local: str) -> list[list[str]]:
    """Os comandos que o script realmente roda, com os caminhos reais."""
    if c["tipo"] == "npm-pkg":
        return [[_executavel("npm"), "publish", "--registry", feed_url]]
    return [[_executavel("mvn"), "-B", "deploy", "-s", settings,
             "-Dmaven.repo.local=" + repo_local]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publica as versoes no feed, na ordem das dependencias.")
    ap.add_argument("--manifesto", required=True)
    ap.add_argument("--repositorios", required=True, help="pasta com um clone de cada repositorio")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sim", action="store_true", help="nao pede confirmacao")
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

    token = _token()
    publicados = versoes_no_feed(m, token)
    if publicados is None:
        print("sem a lista do feed nao da para saber o que ja foi publicado")
        return 1

    print(f"ordem de publicacao: {' -> '.join(ordem)}")
    for repo in ordem:
        c = componentes[repo]
        versoes = publicados.get(c["artefato"], [])
        ja_existe = c["versao"] in versoes
        feed_url = url_do_feed(m, "npm" if c["tipo"] == "npm-pkg" else "maven")
        situacao = "JA EXISTE (a proxima versao e a saida)" if ja_existe else "nova"
        print(f"  {repo:<24} {c['artefato']:<40} {c['versao']:<10} {situacao}")
        for cmd in comandos_publicar(c, feed_url):
            print("      ", " ".join(cmd))
        if args.dry_run:
            continue
        if ja_existe:
            print("       pulado: versao publicada e imutavel")
            continue
        pasta = clones / repo
        if not pasta.exists():
            print("       pulado: clone ausente em", pasta)
            continue

        if not args.sim:
            print(f"       publicar {c['artefato']} {c['versao']}? digite 'sim' (ou use --sim):")
            if input().strip().lower() != "sim":
                print("       cancelado")
                continue

        env = dict(os.environ)
        env["MAVEN_FEED_USER"] = "VSTS"
        env["MAVEN_FEED_TOKEN"] = token
        with tempfile.TemporaryDirectory() as tmp:
            if c["tipo"] == "npm-pkg":
                rc = Path(tmp) / "npmrc"
                rc.write_text(token_npmrc(feed_url, token), encoding="ascii")
                env["NPM_CONFIG_USERCONFIG"] = str(rc)
                cmd = [_executavel("npm"), "publish", "--registry", feed_url]
            else:
                settings = Path(tmp) / "settings.xml"
                settings.write_text(settings_maven(feed_url, m["feed"]), encoding="utf-8", newline="\n")
                cmd = [_executavel("mvn"), "-B", "deploy", "-s", str(settings),
                       "-Dmaven.repo.local=" + str(Path(tmp) / "m2")]
            r = subprocess.run(cmd, cwd=pasta, env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if r.returncode:
            print("       FALHOU:", (r.stdout + r.stderr).strip()[-300:])
            return 1
        print("       publicado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
