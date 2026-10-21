import os
import pathlib
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.varrer import varredura

# o git da maquina herda o autor do ambiente, que sobrescreve o user.name do repositorio de teste
AMBIENTE = {k: v for k, v in os.environ.items()
            if k not in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                         "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=AMBIENTE)


def test_arquivo_limpo_nao_e_acusado(tmp_path):
    (tmp_path / "a.txt").write_text("texto de negocio normal\n", encoding="utf-8")
    assert varredura(tmp_path) == []


def test_termo_de_ferramenta_no_arquivo_e_acusado(tmp_path):
    (tmp_path / "a.txt").write_text("gerado por claude\n", encoding="utf-8")
    assert varredura(tmp_path) != []


def test_autor_de_ferramenta_no_log_e_acusado(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=AMBIENTE)
    _git(tmp_path, "config", "user.name", "opencode")
    _git(tmp_path, "config", "user.email", "opencode@local")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: release")
    achados = varredura(tmp_path)
    assert any("opencode" in a for a in achados)


def test_excecao_e_ignorada(tmp_path):
    (tmp_path / "a.txt").write_text("gerado por claude\n", encoding="utf-8")
    assert varredura(tmp_path, excecoes=[tmp_path / "a.txt"]) == []


def test_mensagem_de_commit_com_marcador_e_acusada(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=AMBIENTE)
    _git(tmp_path, "config", "user.name", "Pessoa")
    _git(tmp_path, "config", "user.email", "pessoa@exemplo")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "Co-Authored-By: Alguem <alguem@exemplo>")
    achados = varredura(tmp_path)
    assert any("co-authored" in a.lower() for a in achados)


def test_sigla_solta_e_acusada_mas_dentro_de_identificador_nao(tmp_path):
    (tmp_path / "a.txt").write_text("usamos IA no texto\n", encoding="utf-8")
    assert varredura(tmp_path) != []
    (tmp_path / "a.txt").unlink()
    (tmp_path / "b.txt").write_text("variavel ai = 1\ncampo ia_um\n", encoding="utf-8")
    assert varredura(tmp_path) == []
