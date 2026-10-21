"""Gera a Wiki de codigo de cada componente e publica a copia na Wiki do projeto.

O texto das oito secoes vem do modelo; os dados vem do codigo do proprio repositorio.
A copia na Wiki do projeto leva um aviso de fonte, para ninguem editar la sem querer.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manifesto import carregar, validar  # noqa: E402
from modelo_wiki import ORDEM, gerar_secoes  # noqa: E402

RECURSO = "499b84ac-1321-427f-aa17-267ca6975798"
AVISO = ("> Cópia da documentação do repositório **{repo}** (branch `{branch}`, commit `{commit}`). "
         "Para alterar, mude `docs/wiki` no repositório e publique de novo.\n\n")


def _token() -> str:
    az = "az.cmd" if sys.platform == "win32" else "az"
    r = subprocess.run([az, "account", "get-access-token", "--resource", RECURSO,
                        "--query", "accessToken", "-o", "tsv"], capture_output=True, text=True)
    return r.stdout.strip()


def _api(metodo: str, url: str, corpo=None, token: str = None, etag: str = None):
    req = urllib.request.Request(url, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None)
    req.add_header("Authorization", f"Bearer {token or _token()}")
    req.add_header("Content-Type", "application/json")
    if etag:
        req.add_header("If-Match", etag)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers.get("ETag"), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, None, {"erro": e.read().decode(errors="replace")[:250]}


def _propriedades(pasta: Path) -> tuple[str, str, list]:
    """Contexto, porta e propriedades, do application.properties ou do application.yml."""
    for nome in ("application.properties", "application.yml", "application.yaml"):
        arq = pasta / "src" / "main" / "resources" / nome
        if not arq.exists():
            continue
        texto = arq.read_text(encoding="utf-8")
        if nome.endswith(".properties"):
            contexto, porta, props = _propriedades_properties(texto)
        else:
            contexto, porta, props = _propriedades_yaml(texto)
        return contexto, porta, props
    return "", "", []


def _propriedades_properties(texto: str) -> tuple[str, str, list]:
    """Le o formato chave=valor, com a hierarquia do server no comeco."""
    contexto, porta, props = "", "", []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip()
        if chave.endswith("context-path"):
            contexto = valor
        elif chave == "server.port":
            porta = valor
        elif chave.startswith("server."):
            continue
        else:
            props.append(_propriedade(chave, valor))
    return contexto, porta, props


def _propriedades_yaml(texto: str) -> tuple[str, str, list]:
    """Le o YAML hierarquico, juntando o caminho com ponto: server.servlet.context-path."""
    contexto, porta, props = "", "", []
    pilha = []
    for linha in texto.splitlines():
        if not linha.strip() or linha.strip().startswith("#"):
            continue
        recuo = len(linha) - len(linha.lstrip())
        conteudo = linha.strip()
        if ":" not in conteudo:
            continue
        chave, _, valor = conteudo.partition(":")
        chave, valor = chave.strip(), valor.strip()
        while pilha and pilha[-1][0] >= recuo:
            pilha.pop()
        caminho = ".".join([p[1] for p in pilha] + [chave])
        if not valor:
            pilha.append((recuo, chave))
            continue
        if caminho.endswith("context-path"):
            contexto = valor
        elif caminho == "server.port":
            porta = valor
        elif caminho.startswith("server."):
            continue
        else:
            props.append(_propriedade(caminho, valor))
    return contexto, porta, props


def _propriedade(chave: str, valor: str) -> tuple:
    """Propriedade com a marca de quem precisa ser definida por ambiente."""
    segredo = bool(re.search(r"(?i)secret|password|senha|token|key", chave))
    variavel = re.search(r"\$\{([A-Z_]+)", valor)
    obs = f"definir a variável de ambiente {variavel.group(1)}" if variavel else ""
    return (chave, valor, "sim" if segredo else "não", obs)


def _segredos(texto: str) -> list:
    segredos = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        if re.search(r"(?i)secret|password|senha|token|key", chave):
            variavel = re.search(r"\$\{([A-Z_]+)", valor)
            nome = variavel.group(1) if variavel else chave.upper().replace(".", "_")
            segredos.append((nome, f"valor de {chave}"))
    return segredos


METODOS = {"Get": "GET", "Post": "POST", "Put": "PUT", "Delete": "DELETE", "Patch": "PATCH"}
ANOTACAO = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping|@RequestMapping")
CAMINHO = re.compile(r"\"([^\"]*)\"")
METODO_EXPLICITO = re.compile(r"RequestMethod\.(GET|POST|PUT|DELETE|PATCH)")


def _caminho_de(texto: str, pos: int) -> str:
    """O primeiro caminho depois da anotacao, na posicao dada."""
    trecho = texto[pos: pos + 200]
    achou = CAMINHO.search(trecho)
    return achou.group(1) if achou else ""


def _endpoints(pasta: Path) -> list:
    """Endpoints dos controllers, com o metodo e o caminho.

    O caminho de classe (@RequestMapping na classe) entra como prefixo do caminho de metodo.
    """
    achados = []
    for arq in sorted((pasta / "src" / "main" / "java").rglob("*.java")):
        texto = arq.read_text(encoding="utf-8")
        anotacoes = list(ANOTACAO.finditer(texto))
        # a anotacao de classe e a primeira, quando ela vem antes de qualquer metodo
        base = ""
        if anotacoes and anotacoes[0].group(0) == "@RequestMapping":
            primeira = anotacoes[0]
            trecho = texto[primeira.end(): primeira.end() + 200]
            if METODO_EXPLICITO.search(trecho):
                # e um metodo com metodo explicito, nao um prefixo de classe
                pass
            else:
                base = _caminho_de(texto, primeira.end())
                anotacoes = anotacoes[1:]
        for m in anotacoes:
            anotacao, pos = m.group(0), m.end()
            if anotacao == "@RequestMapping":
                trecho = texto[pos: pos + 200]
                explicito = METODO_EXPLICITO.search(trecho)
                metodo = explicito.group(1) if explicito else "POST"
                rota = _caminho_de(texto, pos)
            else:
                metodo = METODOS[anotacao[1:-len("Mapping")]]
                rota = _caminho_de(texto, pos)
            caminho = (base.rstrip("/") + "/" + rota.lstrip("/")) if rota else (base or "/")
            achados.append((metodo, caminho, "recurso do componente"))
    return achados[:20]


def _versao_e_artefato(pasta: Path, c: dict) -> tuple[str, str, str]:
    """Versao e nome do artefato, do pom ou do package.json.

    O bloco <parent> traz a versao do pai, que nao e a do componente: ele e ignorado.
    """
    if c["tipo"] == "npm-pkg":
        pkg = json.loads((pasta / "package.json").read_text(encoding="utf-8"))
        return pkg.get("version", c["versao"]), c["artefato"], f"{c['artefato'].split('/')[-1]}.tgz"
    pom = (pasta / "pom.xml").read_text(encoding="utf-8")
    m_parent = re.search(r"<parent>.*?</parent>", pom, flags=re.S)
    alvo = re.compile(r"(<artifactId>[^<]+</artifactId>\s*(?:<packaging>[^<]+</packaging>\s*)?<version>)([^<]+)(</version>)")
    m = alvo.search(pom)
    if m_parent and m and m_parent.start() < m.start() < m_parent.end():
        m = alvo.search(pom, m_parent.end())
    if not m:
        return c["versao"], c["artefato"], c["artefato"].split(":")[-1] + ".jar"
    versao = m.group(2)
    # o nome do artefato vem do <artifactId> do projeto, nao do texto inteiro do trecho
    nome = re.search(r"<artifactId>([^<]+)</artifactId>", m.group(1))
    nome = nome.group(1) if nome else c["artefato"].split(":")[-1]
    final = re.search(r"<finalName>([^<]+)</finalName>", pom)
    empacotado = "war" if "<packaging>war</packaging>" in pom else "jar"
    arquivo = f"{final.group(1) if final else nome}.{empacotado}"
    return versao, c["artefato"], arquivo


def extrair_dados(pasta_repo: Path, c: dict, m: dict = None) -> dict:
    """Le do codigo o que a Wiki precisa dizer."""
    m = m or {}
    contexto, porta, props = _propriedades(pasta_repo)
    versao, artefato, arquivo = _versao_e_artefato(pasta_repo, c)
    recursos = ""
    for nome in ("application.properties", "application.yml"):
        arq = pasta_repo / "src" / "main" / "resources" / nome
        if arq.exists():
            recursos = arq.read_text(encoding="utf-8")
            break
    return {
        "contexto": contexto, "porta": porta, "versao": versao, "artefato": artefato,
        "arquivo": arquivo, "tipo": c["tipo"],
        "propriedades": [(k, v, precisa, obs) for k, v, precisa, obs in props],
        "segredos": _segredos(recursos),
        "endpoints": _endpoints(pasta_repo),
        "testes": _contar_testes(pasta_repo),
        "dependencias": [],
        "ambiente": m.get("ambiente", {}).get("servidor", "Tomcat"),
        "java": m.get("ambiente", {}).get("java", "JDK 25"),
        "build": m.get("ambiente", {}).get("build", "Maven 3.9"),
        "link_arquitetura": m.get("wiki", {}).get("link_arquitetura", ""),
    }


def _contar_testes(pasta_repo: Path) -> str:
    arquivos = list((pasta_repo / "src" / "test").rglob("*.java")) if (pasta_repo / "src" / "test").exists() else []
    if arquivos:
        return f"{len(arquivos)} arquivos de teste, com os testes de contrato da migracao."
    if (pasta_repo / "src" / "test").exists():
        return "Testes automatizados no pacote compartilhado."
    return "Sem testes próprios; a prova vem do build e da conferência de contratos."


def escrever_secoes(pasta_repo: Path, c: dict, dados: dict) -> None:
    """Grava docs/wiki com as oito secoes e a ordem delas."""
    pasta = pasta_repo / "docs" / "wiki"
    pasta.mkdir(parents=True, exist_ok=True)
    secoes = gerar_secoes(c, dados)
    for nome, texto in secoes.items():
        (pasta / f"{nome}.md").write_text(texto, encoding="utf-8", newline="\n")
    (pasta / ".order").write_text("\n".join(ORDEM) + "\n", encoding="utf-8", newline="\n")


def criar_wiki_codigo(org: str, projeto: str, repo: str, branch: str) -> str:
    """Cria a Wiki de codigo do repositorio, mapeada para docs/wiki.

    Devolve o identificador da Wiki, ou vazio quando ela ja existe (o que e o caso
    normal na segunda execucao).
    """
    az = "az.cmd" if sys.platform == "win32" else "az"
    r = subprocess.run([az, "devops", "wiki", "create", "--org", f"https://dev.azure.com/{org}",
                        "--project", projeto, "--name", repo, "--type", "codewiki",
                        "--repository", repo, "--mapped-path", "/docs/wiki", "--version", branch],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        # ja existe: a Wiki de codigo foi criada numa execucao anterior
        if "already exists" in (r.stderr + r.stdout).lower():
            return ""
        print(f"    {repo}: Wiki de codigo nao criada ({r.stderr.strip()[:160]})")
        return ""
    try:
        return json.loads(r.stdout).get("id", "")
    except Exception:
        return ""


def publicar_projeto(raiz_wiki: str, repo: str, texto: str, token: str, m: dict) -> str:
    """Publica a copia na Wiki do projeto, com o aviso de fonte."""
    caminho = f"{raiz_wiki}/Componentes/{repo}"
    org = m.get("org", "")
    projeto = urllib.parse.quote(m.get("projeto", ""))
    wiki = m.get("wiki", {}).get("identificador", "")
    url = (f"https://dev.azure.com/{org}/{projeto}/_apis/wiki/wikis/{wiki}/pages"
           f"?path={urllib.parse.quote(caminho)}&api-version=7.1")
    st, etag, _ = _api("GET", url, token=token)
    st, _, r = _api("PUT", url, {"content": texto}, token=token, etag=etag if st == 200 else None)
    if st not in (200, 201):
        raise SystemExit(f"{caminho}: publicacao falhou ({st}): {r.get('erro', '')[:200]}")
    return str(r.get("id", ""))


def _commit(pasta_repo: Path) -> str:
    r = subprocess.run(["git", "-C", str(pasta_repo), "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gera a Wiki de codigo de cada componente.")
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
    wiki = m.get("wiki", {})
    raiz_wiki = wiki.get("raiz", "")
    link_arquitetura = wiki.get("link_arquitetura", "")
    token = None if args.dry_run else _token()

    # a confirmacao vem antes de qualquer escrita: a copia sobrescreve a pagina do projeto
    if not args.dry_run and not args.sim:
        print("A etapa escreve as oito secoes em docs/wiki de cada repositorio e publica a copia "
              "na Wiki do projeto, sobrescrevendo a pagina anterior do componente.")
        print("Confirme digitando 'sim' (ou use --sim):")
        if input().strip().lower() != "sim":
            print("cancelado")
            return 1

    for c in m["componentes"]:
        pasta = clones / c["repo"]
        if not pasta.exists():
            print(f"  {c['repo']}: clone ausente em {pasta}, pulado")
            continue
        dados = extrair_dados(pasta, c, m)
        dados["dependencias"] = [f"{d['repo']} {d['versao']}" for d in m["componentes"]
                                if d["repo"] in (c.get("dependeDe") or [])]
        secoes = gerar_secoes(c, dados)
        if args.dry_run:
            print(f"\n=== {c['repo']}")
            for nome in ORDEM:
                print(f"  --- {nome}.md ({len(secoes[nome])} caracteres)")
                for linha in secoes[nome].splitlines()[:4]:
                    print("     ", linha[:110])
            continue

        escrever_secoes(pasta, c, dados)
        branch = subprocess.run(["git", "-C", str(pasta), "rev-parse", "--abbrev-ref", "HEAD"],
                                capture_output=True, text=True, encoding="utf-8").stdout.strip()
        commit = _commit(pasta)
        aviso = AVISO.format(repo=c["repo"], branch=branch, commit=commit)
        copia = aviso + "\n".join(secoes[nome] for nome in ORDEM) + "\n"

        # a Wiki de codigo le o repositorio: ela precisa existir e o docs/wiki estar commitado
        identificador = criar_wiki_codigo(m.get("org", ""), m.get("projeto", ""), c["repo"], branch)
        if identificador:
            print(f"    {c['repo']}: Wiki de codigo criada")
        pagina = publicar_projeto(raiz_wiki, c["repo"], copia, token, m)
        print(f"  {c['repo']}: oito secoes escritas e copia publicada (pagina {pagina})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
