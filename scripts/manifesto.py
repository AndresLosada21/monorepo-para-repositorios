"""Leitura e validacao do manifesto que descreve a divisao do monorepo."""
import json
from pathlib import Path

TIPOS = {"maven-lib", "maven-war", "maven-jar", "npm-pkg"}
CAMPOS = ("repo", "caminho", "artefato", "tipo", "versao", "publica", "dependeDe", "descricao")


def carregar(caminho: str) -> dict:
    """Le o manifesto do disco."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def validar(m: dict) -> list[str]:
    """Devolve a lista de problemas; vazia significa manifesto utilizavel."""
    erros = []
    componentes = m.get("componentes") or []
    nomes = {c.get("repo") for c in componentes}
    for c in componentes:
        for campo in CAMPOS:
            if campo not in c:
                erros.append(f"{c.get('repo', '?')}: falta o campo '{campo}'")
        if c.get("tipo") not in TIPOS:
            erros.append(f"{c.get('repo', '?')}: tipo desconhecido '{c.get('tipo')}'")
        for dep in c.get("dependeDe") or []:
            if dep not in nomes:
                erros.append(f"{c.get('repo', '?')}: depende de '{dep}', que nao esta no manifesto")
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
    """Ordem em que os componentes com 'publica' podem ir para o feed."""
    componentes = {c["repo"]: c for c in m.get("componentes", [])}
    prontos, ordem = set(), []

    def pode(repo):
        return all(d in prontos for d in componentes[repo].get("dependeDe") or [])

    restantes = [c["repo"] for c in m.get("componentes", []) if c.get("publica")]
    while restantes:
        for repo in list(restantes):
            if pode(repo):
                ordem.append(repo)
                prontos.add(repo)
                restantes.remove(repo)
                break
        else:
            ordem += restantes
            break
    return ordem
