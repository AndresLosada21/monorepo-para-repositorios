"""Teste de execucao da limpeza: autor, mensagem e conteudo precisam sair limpos."""
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


def test_autor_mensagem_e_conteudo_saem_limpos(tmp_path):
    """A reescrita tem que trocar o autor, a mensagem e o conteudo que carregam o rastro."""
    from scripts import separar

    mono = tmp_path / "mono"
    (mono / "a" / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (mono / "a" / "docs" / "superpowers" / "plans" / "plano.md").write_text(
        "# Plano\n\n> **For agentic workers:** REQUIRED SUB-SKILL\n", encoding="utf-8")
    _git(mono, "init", "-q", "-b", "main")
    _git(mono, "config", "user.name", "opencode")
    _git(mono, "config", "user.email", "opencode@local")
    _git(mono, "add", "a")
    _git(mono, "commit", "-q", "-m", "atualiza docs/superpowers/plans/plano.md")

    c = {"repo": "comp-a", "caminho": "a", "artefato": "br.com.teste:a", "tipo": "maven-lib",
         "versao": "1.0.0", "url_remoto": "", "monorepo": {"url": str(mono), "branch": "main"}}
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "mailmap").write_text("Fulano de Tal <fulano@exemplo> opencode <opencode@local>\n", encoding="utf-8")
    (dest / "replace-text.txt").write_text(separar.REGRAS_DE_LIMPEZA, encoding="utf-8")

    for cmd in separar.gerar_comandos(c, dest):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=AMBIENTE, timeout=180)
        assert r.returncode == 0, f"{' '.join(cmd[:6])}: {r.stderr.strip()[:200]}"

    # o autor trocou
    assert "Fulano de Tal <fulano@exemplo>" in _git(dest, "log", "--format=%an <%ae>")
    # a mensagem trocou
    assert "docs/superpowers" not in _git(dest, "log", "--format=%s")
    # o conteudo trocou: a frase de instrucao saiu de dentro do arquivo
    branch = "reorganizacao/repositorio-independente"
    conteudo = _git(dest, "show", f"{branch}:docs/superpowers/plans/plano.md")
    assert "agentic" not in conteudo.lower(), conteudo
    assert "REQUIRED SUB-SKILL" not in conteudo, conteudo
    # a mensagem tambem ficou limpa
    assert "agentic" not in _git(dest, "log", "--format=%s").lower()
