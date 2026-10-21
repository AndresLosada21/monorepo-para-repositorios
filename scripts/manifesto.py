"""Leitura e validacao do manifesto que descreve a divisao do monorepo."""
import json
import re
from pathlib import Path

TIPOS = {"maven-lib", "maven-war", "maven-jar", "npm-pkg"}
CAMPOS = ("repo", "caminho", "artefato", "tipo", "versao", "publica", "dependeDe", "descricao")
CAMPOS_DE_TOPO = ("projeto", "org", "feed", "monorepo", "responsavel", "componentes")
VERSAO = r"^[0-9]+(\.[0-9]+)*(-[A-Za-z0-9.]+)?$"


def carregar(caminho: str) -> dict:
    """Le o manifesto do disco."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def validar(m: dict) -> list[str]:
    """Devolve a lista de problemas; vazia significa manifesto utilizavel."""
    erros = []
    for campo in CAMPOS_DE_TOPO:
        if campo not in m:
            erros.append(f"manifesto: falta o campo '{campo}'")

    componentes = m.get("componentes") or []
    if not componentes:
        erros.append("manifesto: a lista de componentes esta vazia")

    nomes = {c.get("repo") for c in componentes}
    caminhos = {}
    for c in componentes:
        repo = c.get("repo", "?")
        for campo in CAMPOS:
            if campo not in c:
                erros.append(f"{repo}: falta o campo '{campo}'")
        if c.get("tipo") not in TIPOS:
            erros.append(f"{repo}: tipo desconhecido '{c.get('tipo')}'")
        if not re.match(VERSAO, str(c.get("versao", ""))):
            erros.append(f"{repo}: versao invalida '{c.get('versao')}'")
        if not isinstance(c.get("publica"), bool):
            erros.append(f"{repo}: 'publica' tem de ser verdadeiro ou falso")
        for dep in c.get("dependeDe") or []:
            if dep not in nomes:
                erros.append(f"{repo}: depende de '{dep}', que nao esta no manifesto")
        caminho = c.get("caminho")
        if caminho in caminhos:
            erros.append(f"{repo}: caminho '{caminho}' duplicado com '{caminhos[caminho]}'")
        caminhos[caminho] = repo
    erros += _ciclos(componentes)
    return erros


def _ciclos(componentes) -> list[str]:
    """Detecta ciclo no grafo de dependencias."""
    grafo = {c.get("repo"): list(c.get("dependeDe") or []) for c in componentes}
    estado, pilha = {}, []

    def visita(no):
        if estado.get(no) == "aberto":
            return pilha + [no]
        if estado.get(no) == "fechado":
            return None
        estado[no] = "aberto"
        pilha.append(no)
        for viz in grafo.get(no, []):
            achado = visita(viz)
            if achado:
                return achado
        pilha.pop()
        estado[no] = "fechado"
        return None

    for no in grafo:
        achado = visita(no)
        if achado:
            return [f"ciclo de dependencias: {' -> '.join(achado)}"]
    return []


def ordem_publicacao(m: dict) -> list[str]:
    """Ordem topologica dos componentes que publicam.

    A ordem sai do grafo de dependencias, nao da ordem do arquivo: um componente que
    depende de outro so entra depois dele, mesmo que a dependencia nao publique (ela
    ja esta no feed) e mesmo que ele esteja no fim do arquivo.
    """
    componentes = {c["repo"]: c for c in m.get("componentes", [])}
    publicam = {c["repo"] for c in m.get("componentes", []) if c.get("publica")}

    # o grafo considera todas as dependencias, publicadas ou nao
    grafo = {repo: [d for d in (c.get("dependeDe") or []) if d in componentes]
             for repo, c in componentes.items()}

    # cada publicante espera pelas dependencias que tambem publicam
    espera = {repo: {d for d in grafo.get(repo, []) if d in publicam} for repo in publicam}

    ordem, prontos = [], set()
    while len(ordem) < len(publicam):
        # pronto e aquele cujas dependencias que publicam ja sairam
        prontos_agora = sorted(repo for repo in publicam
                              if repo not in ordem and espera[repo] <= prontos)
        if not prontos_agora:
            # ciclo: nao ha ordem valida, devolve o que falta na ordem do arquivo
            return [r for r in componentes if r in publicam and r not in ordem]
        for repo in prontos_agora:
            ordem.append(repo)
            prontos.add(repo)
    return ordem
