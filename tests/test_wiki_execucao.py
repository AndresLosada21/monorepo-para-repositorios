"""Testes de execucao da fase 4: a documentacao tem que ser gerada e o repo tem que ficar limpo."""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

AMBIENTE = {k: v for k, v in os.environ.items()
            if k not in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                         "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=AMBIENTE)
    if r.returncode:
        raise AssertionError(f"git {args}: {r.stderr.strip()}")
    return r.stdout


def _repo(tmp_path, nome):
    pasta = tmp_path / nome
    (pasta / "src" / "main" / "java" / "br" / "yamaha" / "x").mkdir(parents=True)
    (pasta / "src" / "main" / "java" / "br" / "yamaha" / "x" / "Ctrl.java").write_text(
        "package br.com.yamaha.x;\n"
        "import org.springframework.web.bind.annotation.*;\n"
        "@RestController\n"
        "public class Ctrl {\n"
        "    @GetMapping(\"/a\")\n"
        "    public String a() { return \"\"; }\n"
        "}\n", encoding="utf-8")
    (pasta / "src" / "main" / "resources").mkdir(parents=True)
    (pasta / "src" / "main" / "resources" / "application.properties").write_text(
        "server.servlet.context-path=/x\nserver.port=8081\n"
        "erp.jwt.secret=${ERP_JWT_SECRET:}\n", encoding="utf-8")
    (pasta / "pom.xml").write_text(
        "<project><groupId>br.com.teste</groupId><artifactId>x</artifactId>"
        "<version>1.0.0</version><packaging>war</packaging></project>\n", encoding="utf-8")
    _git(pasta, "init", "-q", "-b", "main")
    _git(pasta, "config", "user.name", "Pessoa")
    _git(pasta, "config", "user.email", "pessoa@exemplo")
    _git(pasta, "add", "-A")
    _git(pasta, "commit", "-q", "-m", "componente")
    return pasta


def _manifesto(tmp_path):
    man = {
        "projeto": "Projeto Teste", "org": "org-teste", "feed": "feed-teste",
        "responsavel": {"nome": "Fulano de Tal", "email": "fulano@exemplo"},
        "monorepo": {"url": "http://exemplo/mono", "branch": "main"},
        "wiki": {"raiz": "/Java/Teste", "identificador": "wiki-teste", "link_arquitetura": "http://exemplo/arquitetura"},
        "ambiente": {"servidor": "Tomcat 11", "java": "JDK 25", "build": "Maven 3.9"},
        "componentes": [
            {"repo": "comp-a", "caminho": "a", "artefato": "br.com.teste:a", "tipo": "maven-war",
             "versao": "1.0.0", "publica": True, "dependeDe": [], "descricao": "componente a"},
        ],
    }
    caminho = tmp_path / "manifesto.json"
    caminho.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho


def test_fase_4_cancela_sem_escrever_nada(tmp_path, capsys):
    """Sem --sim, a fase 4 pergunta antes de escrever, e cancelar nao escreve."""
    from scripts import wiki_componente
    repo = _repo(tmp_path, "comp-a")
    man = _manifesto(tmp_path)
    clones = tmp_path / "clones"
    clones.mkdir()
    import shutil
    shutil.copytree(repo, clones / "comp-a")

    chamadas = []

    def falsa(raiz, nome, texto, token, m):
        chamadas.append(nome)
        return "0"

    original = wiki_componente.publicar_projeto
    wiki_componente.publicar_projeto = falsa
    try:
        import builtins
        respostas = iter(["nao"])
        original_input = builtins.input
        builtins.input = lambda *a, **k: next(respostas)
        try:
            rc = wiki_componente.main(["--manifesto", str(man), "--repositorios", str(clones)])
        finally:
            builtins.input = original_input
    finally:
        wiki_componente.publicar_projeto = original

    assert rc == 1
    saida = capsys.readouterr().out
    assert "cancelado" in saida, saida
    # nada foi gerado nem publicado
    assert chamadas == [], chamadas
    assert not (clones / "comp-a" / "docs" / "wiki").exists()


def test_fase_4_publica_com_sim(tmp_path, capsys):
    """Com --sim, a copia vai para a Wiki do projeto."""
    from scripts import wiki_componente
    repo = _repo(tmp_path, "comp-a")
    man = _manifesto(tmp_path)
    clones = tmp_path / "clones"
    clones.mkdir()
    import shutil
    shutil.copytree(repo, clones / "comp-a")

    chamadas = []

    def falsa(raiz, nome, texto, token, m):
        chamadas.append((nome, texto))
        return "0"

    original = wiki_componente.publicar_projeto
    wiki_componente.publicar_projeto = falsa
    try:
        rc = wiki_componente.main(["--manifesto", str(man), "--repositorios", str(clones), "--sim"])
    finally:
        wiki_componente.publicar_projeto = original

    assert rc == 0, capsys.readouterr().out
    assert chamadas and chamadas[0][0] == "comp-a", chamadas
    texto = chamadas[0][1]
    # o aviso de fonte fica no topo e diz de onde vem a copia
    assert texto.startswith(">"), texto[:80]
    assert "Cópia da documentação do repositório" in texto
    assert "comp-a" in texto
    assert "docs/wiki" in texto
