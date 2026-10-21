"""Separa um monorepo em repositorios, um por componente, preservando o historico.

O trabalho pesado e do git filter-repo: a pasta do componente vira a raiz do repositorio novo,
o autor dos commits passa a ser o responsavel e o texto e limpo. O script conduz o processo,
confere a branch padrao e, quando precisa trocar a branch padrao, usa commit de merge para
permitir push normal.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifesto import carregar, validar  # noqa: E402

BRANCH = "reorganizacao/repositorio-independente"
# config que o git leva em toda operacao de historico: sem isso, o nome de arquivo
# ganha um caractere de retorno de linha e a arvore fica corrompida
CONFIG = ["-c", "core.autocrlf=false", "-c", "core.quotepath=false"]


def _git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} em {repo}: {r.stderr.strip()}")
    return r.stdout


def _texto_de_um_arquivo(p: Path, conteudo: str) -> None:
    p.write_text(conteudo, encoding="utf-8", newline="\n")


def responsavel_do_manifesto(m: dict) -> tuple[str, str]:
    """Nome e e-mail de quem assina os commits separados."""
    r = m.get("responsavel") or {}
    return r.get("nome", ""), r.get("email", "")


def gerar_comandos(c: dict, destino: Path) -> list[list[str]]:
    """Comandos git que separam um componente. Nao executa nada.

    O historico vem do monorepo; o repositorio novo e o destino. Os arquivos de apoio do
    filter-repo (mailmap e replace-text) vao dentro do repositorio, com caminho relativo:
    o filter-repo roda com o diretorio do repo como atual e nao acha caminho absoluto.
    """
    monorepo = c["monorepo"]["url"]
    branch = c["monorepo"].get("branch", "main")
    return [
        ["git", *CONFIG, "init", "-q", str(destino)],
        ["git", "-C", str(destino), *CONFIG, "remote", "add", "monorepo", monorepo],
        ["git", "-C", str(destino), *CONFIG, "remote", "add", "origin", c.get("url_remoto", "")],
        ["git", "-C", str(destino), *CONFIG, "fetch", "monorepo"],
        ["git", "-C", str(destino), *CONFIG, "filter-repo", "--force",
         # primeiro fica so a pasta do componente, depois ela vira a raiz
         "--path", f"{c['caminho']}/",
         "--path-rename", f"{c['caminho']}/:",
         "--mailmap", "mailmap",
         "--replace-text", "replace-text.txt",
         "--refs", f"refs/remotes/monorepo/{branch}"],
        # o filter-repo reescreve a branch e a deixa so como remota: a nova leva o codigo separado
        ["git", "-C", str(destino), *CONFIG, "branch", "-f", BRANCH, f"refs/remotes/monorepo/{branch}"],
    ]


def comandos_de_publicacao(c: dict, url_remoto: str) -> list[list[str]]:
    """Comandos que sobem o resultado para o repositorio de destino."""
    return [["git", "-C", str(c.get("destino", ".")), "push", url_remoto, f"{BRANCH}:{BRANCH}"]]


def conferir_caminhos(c: dict, raiz: Path) -> list[str]:
    """Erros quando a pasta de origem do componente nao existe no monorepo."""
    if not (Path(raiz) / c["caminho"]).exists():
        return [f"{c['repo']}: a pasta '{c['caminho']}' nao existe no monorepo"]
    return []


def verificar_branch_padrao(url: str, esperado: str) -> bool:
    """True quando a branch padrao do repositorio remoto ja e a esperada."""
    r = subprocess.run(["git", "ls-remote", "--symref", url, "HEAD"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    achou = re.search(r"ref:\s+refs/heads/(\S+)\s+HEAD", r.stdout)
    return bool(achou) and achou.group(1) == esperado


def _bloco_feed(feed_url: str, feed_id: str) -> str:
    return f"""    <!-- As bibliotecas internas vem do feed do time. A credencial nunca fica aqui:
         vem do settings.xml do usuario ou do pipeline. -->
    <repositories>
        <repository>
            <id>{feed_id}</id>
            <url>{feed_url}</url>
            <releases><enabled>true</enabled></releases>
            <snapshots><enabled>false</enabled></snapshots>
        </repository>
    </repositories>

    <distributionManagement>
        <repository>
            <id>{feed_id}</id>
            <url>{feed_url}</url>
        </repository>
    </distributionManagement>

"""


def _bloco_distribuicao(feed_url: str, feed_id: str) -> str:
    """Bloco so de publicacao, para quando o pom ja tem repositorios proprios."""
    return f"""    <distributionManagement>
        <repository>
            <id>{feed_id}</id>
            <url>{feed_url}</url>
        </repository>
    </distributionManagement>

"""


def _versao_do_projeto(t: str) -> tuple[int, int]:
    """Intervalo da <version> do proprio artefato, ignorando o bloco <parent>."""
    m_parent = re.search(r"<parent>.*?</parent>", t, flags=re.S)
    alvo = re.compile(r"(<artifactId>[^<]+</artifactId>\s*(?:<packaging>[^<]+</packaging>\s*)?<version>)([^<]+)(</version>)")
    m = alvo.search(t)
    if not m:
        raise SystemExit("versao do projeto nao encontrada")
    if m_parent and m_parent.start() < m.start() < m_parent.end():
        m = alvo.search(t, m_parent.end())
        if not m:
            raise SystemExit("versao do projeto nao encontrada")
    return m.start(2), m.end(2)


def escrever_pom_independente(pom: Path, versao: str, feed_url: str, versoes_internas: dict,
                                feed_id: str = "mfg-java") -> None:
    """Poe a versao do artefato, fixa as dependencias internas e declara o feed."""
    t = pom.read_text(encoding="utf-8")

    inicio, fim = _versao_do_projeto(t)
    t = t[:inicio] + versao + t[fim:]

    for artefato, v in versoes_internas.items():
        t = re.sub(rf"(<artifactId>{re.escape(artefato)}</artifactId>\s*<version>)[^<]+(</version>)",
                   rf"\g<1>{v}\g<2>", t)

    if "<distributionManagement>" not in t:
        alvo = re.search(r"\n\s*<(dependencyManagement|dependencies|repositories)>", t)
        if not alvo:
            raise SystemExit(f"{pom}: ponto de insercao do feed nao encontrado")
        if alvo.group(1) == "repositories":
            # o pom ja tem repositorios: acrescenta so o destino de publicacao, sem duplicar a tag
            bloco = _bloco_distribuicao(feed_url, feed_id)
        else:
            bloco = _bloco_feed(feed_url, feed_id)
        t = t[:alvo.start()] + "\n" + bloco + t[alvo.start() + 1:]

    pom.write_text(t, encoding="utf-8", newline="\n")


def escrever_package_independente(pkg: Path, versao: str, feed_url: str) -> None:
    """Poe a versao, tira o privado e declara o destino de publicacao."""
    dados = json.loads(pkg.read_text(encoding="utf-8"))
    dados["version"] = versao
    dados.pop("private", None)
    dados.setdefault("files", ["src"])
    dados["publishConfig"] = {"registry": feed_url}
    pkg.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def commitar_com_merge(mirror: Path, branch_nova: str, branch_antiga: str) -> str:
    """Commit de merge que traz o historico antigo como segundo pai, para permitir push normal."""
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": RESPONSAVEL[0], "GIT_AUTHOR_EMAIL": RESPONSAVEL[1],
                "GIT_COMMITTER_NAME": RESPONSAVEL[0], "GIT_COMMITTER_EMAIL": RESPONSAVEL[1]})
    arvore = subprocess.run(["git", "-C", str(mirror), "rev-parse", f"{branch_nova}^{{tree}}"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", env=env).stdout.strip()
    pai_novo = subprocess.run(["git", "-C", str(mirror), "rev-parse", branch_nova],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=env).stdout.strip()
    pai_antigo = subprocess.run(["git", "-C", str(mirror), "rev-parse", branch_antiga],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env).stdout.strip()
    msg = ("Integra o historico anterior na branch principal\n\n"
           "A branch principal passa a ter o codigo novo, com o historico antigo preservado "
           "como segundo pai, o que permite push normal.\n")
    r = subprocess.run(["git", "-C", str(mirror), "commit-tree", arvore, "-p", pai_novo, "-p", pai_antigo],
                       input=msg, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    commit = r.stdout.strip()
    if not commit:
        raise SystemExit(f"commit de merge nao gerado: {r.stderr.strip()}")
    subprocess.run(["git", "-C", str(mirror), "update-ref", f"refs/heads/{branch_nova}", commit], env=env)
    return commit


# preenchido em tempo de execucao pelo manifesto
RESPONSAVEL = ("", "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Separa um monorepo em repositorios por componente.")
    ap.add_argument("--manifesto", required=True)
    ap.add_argument("--destino", required=True, help="pasta onde os repositorios sao montados")
    ap.add_argument("--apenas", nargs="*", help="segue apenas estes componentes")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sim", action="store_true", help="nao pede confirmacao")
    args = ap.parse_args(argv)

    global RESPONSAVEL
    m = carregar(args.manifesto)
    RESPONSAVEL = responsavel_do_manifesto(m)
    erros = validar(m)
    if erros:
        print("manifesto com problemas:")
        for e in erros:
            print("  ", e)
        return 2
    if not RESPONSAVEL[0] or not RESPONSAVEL[1]:
        print("manifesto sem 'responsavel' com nome e e-mail")
        return 2

    destino = Path(args.destino)
    componentes = [c for c in m["componentes"] if not args.apenas or c["repo"] in args.apenas]
    feed_url = (f"https://pkgs.dev.azure.com/{m['org']}/"
                f"{m['projeto'].replace(' ', '%20')}/_packaging/{m['feed']}/maven/v1")
    versoes_internas = {c["artefato"].split(":")[-1]: c["versao"]
                        for c in m["componentes"] if c["tipo"].startswith("maven")}

    if args.dry_run:
        # o dry-run nao escreve: mostra os comandos e as URLs de destino
        for c in componentes:
            c = dict(c, monorepo=m["monorepo"])
            url = (f"https://dev.azure.com/{m['org']}/{m['projeto'].replace(' ', '%20')}/_git/{c['repo']}")
            c["url_remoto"] = url
            print(f"\n=== {c['repo']}  (historia de {m['monorepo']['url']})")
            for cmd in gerar_comandos(c, destino / c["repo"]):
                print("   ", " ".join(cmd))
            for cmd in comandos_de_publicacao(dict(c, destino=destino / c["repo"]), url):
                print("   ", " ".join(cmd))
        return 0

    if not args.sim:
        print(f"Esta etapa reescreve historico e sobe branch em {len(componentes)} repositorio(s).")
        print("Confirme digitando 'sim' (ou use --sim):")
        if input().strip().lower() != "sim":
            print("cancelado")
            return 1

    destino.mkdir(parents=True, exist_ok=True)
    mailmap = destino / "mailmap"
    _texto_de_um_arquivo(mailmap, f"{RESPONSAVEL[0]} <{RESPONSAVEL[1]}> opencode <opencode@local>\n")
    replace = destino / "replace-text.txt"
    _texto_de_um_arquivo(replace, "docs/superpowers/plans/==>docs/planos/\n")

    for c in componentes:
        print(f"\n=== {c['repo']}")
        repo = destino / c["repo"]
        url = f"https://dev.azure.com/{m['org']}/{m['projeto'].replace(' ', '%20')}/_git/{c['repo']}"
        c = dict(c, monorepo=m["monorepo"], url_remoto=url, destino=repo)

        erros_caminho = conferir_caminhos(c, destino)
        if erros_caminho:
            for e in erros_caminho:
                print("   ", e)
            continue

        if repo.exists():
            shutil.rmtree(repo, ignore_errors=True)
        repo.mkdir(parents=True)
        # os arquivos de apoio do filter-repo vao dentro do repo, com caminho relativo
        _texto_de_um_arquivo(repo / "mailmap", mailmap.read_text(encoding="utf-8"))
        _texto_de_um_arquivo(repo / "replace-text.txt", replace.read_text(encoding="utf-8"))

        for cmd in gerar_comandos(c, repo):
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                print(f"    FALHOU: {' '.join(cmd[:6])} -> {r.stderr.strip()[:200]}")
                break
        else:
            if c["tipo"] == "npm-pkg":
                escrever_package_independente(repo / "package.json", c["versao"],
                                             feed_url.replace("/maven/v1", "/npm/registry/"))
            else:
                escrever_pom_independente(repo / "pom.xml", c["versao"], feed_url, versoes_internas, m["feed"])
            print(f"    {c['repo']} separado em {repo}")

    print("\nbranch padrao de cada repositorio:")
    for c in componentes:
        url = f"https://dev.azure.com/{m['org']}/{m['projeto'].replace(' ', '%20')}/_git/{c['repo']}"
        ok = verificar_branch_padrao(url, BRANCH)
        print(f"    {c['repo']:<24} {BRANCH if ok else 'ainda nao publicada'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
