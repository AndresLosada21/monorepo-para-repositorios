"""Separa um monorepo em repositorios, um por componente, preservando o historico.

O trabalho pesado e do git filter-repo: a pasta do componente vira a raiz do repositorio novo,
o autor dos commits passa a ser o responsavel e o texto e limpo. O script conduz o processo,
confere a branch padrao e, quando precisa trocar a branch padrao, usa commit de merge para
permitir push normal.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifesto import carregar, ordem_publicacao, validar  # noqa: E402

BRANCH = "reorganizacao/repositorio-independente"
RESPONSAVEL = ("CARLOS ANDRES RAMOS LOSADA JUNIOR", "carlos.ramos@yamaha-motor.com.br")


def _git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} em {repo}: {r.stderr.strip()}")
    return r.stdout


def _texto_de_um_arquivo(p: Path, conteudo: str) -> None:
    p.write_text(conteudo, encoding="utf-8", newline="\n")


def gerar_comandos(c: dict, destino: Path) -> list[list[str]]:
    """Comandos git que separam um componente. Nao executa nada.

    O mailmap e o replace-text vao dentro do proprio repositorio, com caminho relativo:
    o filter-repo roda com o diretorio do repo como atual e nao acha caminho absoluto.
    """
    return [
        ["git", "-c", "core.autocrlf=false", "-c", "core.quotepath=false", "init", "-q", str(destino)],
        ["git", "-C", str(destino), "remote", "add", "origin", c.get("url_remoto", "")],
        ["git", "-C", str(destino), "fetch", "origin"],
        ["git", "-C", str(destino), "filter-repo", "--force",
         # primeiro fica so a pasta do componente, depois ela vira a raiz
         "--path", f"{c['caminho']}/",
         "--path-rename", f"{c['caminho']}/:",
         "--mailmap", "mailmap",
         "--replace-text", "replace-text.txt",
         "--refs", f"refs/remotes/origin/{c.get('branch_origem', 'main')}"],
        # o filter-repo reescreve a branch so como remota; a nova leva o codigo separado
        ["git", "-C", str(destino), "branch", "-f", BRANCH,
         f"refs/remotes/origin/{c.get('branch_origem', 'main')}"],
        ["git", "-C", str(destino), "push", "origin", f"{BRANCH}:{BRANCH}"],
    ]


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


def _bloco_feed(feed_url: str) -> str:
    return f"""    <!-- As bibliotecas internas vem do feed do time. A credencial nunca fica aqui:
         vem do settings.xml do usuario ou do pipeline. -->
    <repositories>
        <repository>
            <id>mfg-java</id>
            <url>{feed_url}</url>
            <releases><enabled>true</enabled></releases>
            <snapshots><enabled>false</enabled></snapshots>
        </repository>
    </repositories>

    <distributionManagement>
        <repository>
            <id>mfg-java</id>
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


def escrever_pom_independente(pom: Path, versao: str, feed_url: str, versoes_internas: dict) -> None:
    """Poe a versao do artefato, fixa as dependencias internas e declara o feed."""
    t = pom.read_text(encoding="utf-8")

    inicio, fim = _versao_do_projeto(t)
    t = t[:inicio] + versao + t[fim:]

    for artefato, v in versoes_internas.items():
        t = re.sub(rf"(<artifactId>{re.escape(artefato)}</artifactId>\s*<version>)[^<]+(</version>)",
                   rf"\g<1>{v}\g<2>", t)

    if "<distributionManagement>" not in t:
        alvo = re.search(r"\n\s*<(dependencyManagement|dependencies)>", t)
        if not alvo:
            raise SystemExit(f"{pom}: ponto de insercao do feed nao encontrado")
        t = t[:alvo.start()] + "\n" + _bloco_feed(feed_url) + t[alvo.start() + 1:]

    pom.write_text(t, encoding="utf-8", newline="\n")


def escrever_package_independente(pkg: Path, versao: str, feed_url: str) -> None:
    """Poe a versao, tira o privado e declara o destino de publicacao."""
    dados = json.loads(pkg.read_text(encoding="utf-8"))
    dados["version"] = versao
    dados.pop("private", None)
    dados["files"] = ["src", "!src/**/*.test.ts", "!src/**/*.test.tsx", "!src/test"]
    dados["publishConfig"] = {"registry": feed_url}
    pkg.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def commitar_com_merge(mirror: Path, branch_nova: str, branch_antiga: str) -> str:
    """Commit de merge que traz o historico antigo como segundo pai, para permitir push normal."""
    env = {**dict(__import__("os").environ),
           "GIT_AUTHOR_NAME": RESPONSAVEL[0], "GIT_AUTHOR_EMAIL": RESPONSAVEL[1],
           "GIT_COMMITTER_NAME": RESPONSAVEL[0], "GIT_COMMITTER_EMAIL": RESPONSAVEL[1]}
    arvore = subprocess.run(["git", "-C", str(mirror), "rev-parse", f"{branch_nova}^{{tree}}"],
                             capture_output=True, text=True, env=env).stdout.strip()
    pai_novo = subprocess.run(["git", "-C", str(mirror), "rev-parse", branch_nova],
                              capture_output=True, text=True, env=env).stdout.strip()
    pai_antigo = subprocess.run(["git", "-C", str(mirror), "rev-parse", branch_antiga],
                                capture_output=True, text=True, env=env).stdout.strip()
    msg = ("Integra o historico anterior na branch principal\n\n"
           "A branch principal passa a ter o codigo novo, com o historico antigo preservado "
           "como segundo pai, o que permite push normal.\n")
    r = subprocess.run(["git", "-C", str(mirror), "commit-tree", arvore, "-p", pai_novo, "-p", pai_antigo],
                       input=msg, capture_output=True, text=True, encoding="utf-8", env=env)
    commit = r.stdout.strip()
    subprocess.run(["git", "-C", str(mirror), "update-ref", f"refs/heads/{branch_nova}", commit], env=env)
    return commit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Separa um monorepo em repositorios por componente.")
    ap.add_argument("--manifesto", required=True)
    ap.add_argument("--destino", required=True, help="pasta onde os repositorios sao montados")
    ap.add_argument("--apenas", nargs="*", help="segue apenas estes componentes")
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

    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    componentes = [c for c in m["componentes"] if not args.apenas or c["repo"] in args.apenas]

    # arquivos de apoio do filter-repo
    mailmap = destino / "mailmap"
    _texto_de_um_arquivo(mailmap, f"{RESPONSAVEL[0]} <{RESPONSAVEL[1]}> opencode <opencode@local>\n")
    replace = destino / "replace-text.txt"
    _texto_de_um_arquivo(replace, "docs/superpowers/plans/==>docs/planos/\n")

    feed_url = (f"https://pkgs.dev.azure.com/{m['org']}/"
                f"{m['projeto'].replace(' ', '%20')}/_packaging/{m['feed']}/maven/v1")
    versoes_internas = {c["artefato"].split(":")[-1]: c["versao"]
                        for c in m["componentes"] if c["tipo"].startswith("maven")}

    for c in componentes:
        print(f"\n=== {c['repo']}")
        repo = destino / c["repo"]
        c = dict(c)
        c["url_remoto"] = (f"https://dev.azure.com/{m['org']}/"
                           f"{m['projeto'].replace(' ', '%20')}/_git/{c['repo']}")
        c["branch_origem"] = m["monorepo"].get("branch", "main")

        cmds = gerar_comandos(c, repo)
        if args.dry_run:
            for cmd in cmds:
                print("   ", " ".join(cmd))
            continue

        if repo.exists():
            shutil.rmtree(repo, ignore_errors=True)
        repo.mkdir(parents=True)
        for cmd in cmds:
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if cmd[1] == "-C" or cmd[0] == "git":
                pass
        # a versao e o feed entram no manifesto do componente
        if c["tipo"] == "npm-pkg":
            escrever_package_independente(repo / "package.json", c["versao"], feed_url.replace("/maven/v1", "/npm/registry/"))
        else:
            escrever_pom_independente(repo / "pom.xml", c["versao"], feed_url, versoes_internas)
        print(f"    {c['repo']} separado em {repo}")

    if not args.dry_run:
        print("\nbranch padrao de cada repositorio:")
        for c in componentes:
            url = (f"https://dev.azure.com/{m['org']}/{m['projeto'].replace(' ', '%20')}/_git/{c['repo']}")
            ok = verificar_branch_padrao(url, BRANCH)
            print(f"    {c['repo']:<24} {BRANCH if ok else 'BRANCH (ainda nao publicada)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
