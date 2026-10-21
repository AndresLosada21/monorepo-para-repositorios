"""Teste de execucao de verdade: a fase 2 tem que separar um monorepo de verdade.

Este teste e o que protege a fase 2: ele roda o main do script, com um monorepo local e um
destino local, e confere o resultado na arvore de trabalho.
"""
import json
import os
import pathlib
import shutil
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


def _cenario(tmp_path):
    """Monta um monorepo com dois componentes e um destino por componente."""
    mono = tmp_path / "mono"
    mono.mkdir()
    for pasta in ("a", "b"):
        (mono / pasta).mkdir()
        (mono / pasta / "pom.xml").write_text(
            f"<project><groupId>br.com.teste</groupId><artifactId>{pasta}</artifactId>"
            f"<version>1.0.0-SNAPSHOT</version></project>\n", encoding="utf-8")
    (mono / "comum.txt").write_text("comum\n", encoding="utf-8")
    _git(mono, "init", "-q", "-b", "main")
    _git(mono, "config", "user.name", "Pessoa")
    _git(mono, "config", "user.email", "pessoa@exemplo")
    for pasta in ("a", "b"):
        _git(mono, "add", pasta)
        _git(mono, "commit", "-q", "-m", f"conteudo de {pasta}")
    _git(mono, "add", "comum.txt")
    _git(mono, "commit", "-q", "-m", "arquivo comum")
    return mono


def _manifesto(tmp_path, mono, responsavel="Fulano de Tal", email="fulano@exemplo"):
    """Manifesto com o destino de cada componente apontando para um bare local."""
    destinos = {}
    for repo in ("comp-a", "comp-b"):
        bare = tmp_path / f"destino-{repo}.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=AMBIENTE)
        destinos[repo] = str(bare)
    man = {
        "projeto": "Projeto Teste", "org": "org-teste", "feed": "feed-teste",
        "responsavel": {"nome": responsavel, "email": email},
        "monorepo": {"url": str(mono), "branch": "main"},
        "wiki": {"raiz": "/Java/Teste", "identificador": "wiki-teste", "link_arquitetura": "http://exemplo/arquitetura"},
        "ambiente": {"servidor": "Tomcat 11", "java": "JDK 25", "build": "Maven 3.9"},
        "componentes": [
            {"repo": "comp-a", "caminho": "a", "artefato": "br.com.teste:a", "tipo": "maven-lib",
             "versao": "1.0.0", "publica": True, "dependeDe": [], "descricao": "componente a",
             "destino": destinos["comp-a"]},
            {"repo": "comp-b", "caminho": "b", "artefato": "br.com.teste:b", "tipo": "maven-lib",
             "versao": "1.0.0", "publica": True, "dependeDe": [], "descricao": "componente b",
             "destino": destinos["comp-b"]},
        ],
    }
    caminho = tmp_path / "manifesto.json"
    caminho.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho, destinos


def _roda(manifesto, destino, sim=True):
    from scripts import separar
    argv = ["--manifesto", str(manifesto), "--destino", str(destino)]
    if sim:
        argv.append("--sim")
    return separar.main(argv)


def test_fase_2_separa_de_verdade(tmp_path, capsys):
    """O main do script tem que deixar cada repositorio com o conteudo e a versao do manifesto."""
    mono = _cenario(tmp_path)
    man, _ = _manifesto(tmp_path, mono)
    destino = tmp_path / "destino"

    rc = _roda(man, destino)
    assert rc == 0, capsys.readouterr().out

    for repo, versao in (("comp-a", "1.0.0"), ("comp-b", "1.0.0")):
        pasta = destino / repo
        assert (pasta / "pom.xml").exists(), f"{repo}: pom.xml nao esta na arvore de trabalho"
        assert not (pasta / "comum.txt").exists(), f"{repo}: arquivo de outro componente na arvore"
        texto = (pasta / "pom.xml").read_text(encoding="utf-8")
        assert f"<version>{versao}</version>" in texto, texto
        assert "feed-teste" in texto, texto
        log = _git(pasta, "log", "--format=%s", "reorganizacao/repositorio-independente")
        assert "conteudo de" in log, log
        assert not _git(pasta, "status", "--porcelain").strip(), _git(pasta, "status", "--porcelain")


def test_fase_2_sobe_a_branch_no_destino(tmp_path, capsys):
    """A branch separada tem de chegar no repositorio de destino."""
    mono = _cenario(tmp_path)
    man, destinos = _manifesto(tmp_path, mono)
    destino = tmp_path / "destino"
    rc = _roda(man, destino)
    assert rc == 0, capsys.readouterr().out
    for repo, bare in destinos.items():
        remoto = _git(bare, "for-each-ref", "--format=%(refname)", "refs/heads")
        assert "reorganizacao/repositorio-independente" in remoto, remoto
        conteudo = _git(bare, "ls-tree", "-r", "--name-only", "reorganizacao/repositorio-independente")
        assert "pom.xml" in conteudo, conteudo


def test_fase_2_avisa_antes_de_apagar_o_destino(tmp_path, capsys):
    """O prompt de confirmacao tem de dizer o que vai ser apagado."""
    mono = _cenario(tmp_path)
    man, _ = _manifesto(tmp_path, mono)
    destino = tmp_path / "destino"
    (destino / "comp-a").mkdir(parents=True)
    (destino / "comp-a" / "importante.txt").write_text("nao pode sumir sem aviso\n", encoding="utf-8")

    import builtins
    respostas = iter(["nao"])
    original = builtins.input
    builtins.input = lambda *a, **k: next(respostas)
    try:
        rc = _roda(man, destino, sim=False)
    finally:
        builtins.input = original

    assert rc == 1
    saida = capsys.readouterr().out
    assert "comp-a" in saida, saida
    # e o conteudo continua, porque a resposta foi nao
    assert (destino / "comp-a" / "importante.txt").exists()


def test_fase_2_nao_commita_os_arquivos_de_ajuda(tmp_path, capsys):
    """mailmap e replace-text nao podem ser commitados: eles carregam o rastro que a fase 6 limpa."""
    mono = _cenario(tmp_path)
    man, _ = _manifesto(tmp_path, mono)
    destino = tmp_path / "destino"
    _roda(man, destino)
    pasta = destino / "comp-a"
    arquivos = _git(pasta, "ls-files").split()
    assert "mailmap" not in arquivos, arquivos
    assert "replace-text.txt" not in arquivos, arquivos
    assert "pom.xml" in arquivos, arquivos
