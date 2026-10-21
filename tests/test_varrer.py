import pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.varrer import varredura


def test_arquivo_limpo_nao_e_acusado(tmp_path):
    (tmp_path / "a.txt").write_text("texto de negocio normal\n", encoding="utf-8")
    assert varredura(tmp_path) == []


def test_termo_de_ferramenta_no_arquivo_e_acusado(tmp_path):
    (tmp_path / "a.txt").write_text("gerado por claude\n", encoding="utf-8")
    assert varredura(tmp_path) != []


def test_autor_de_ferramenta_no_log_e_acusado(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "opencode"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "opencode@local"], check=True)
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "chore: release"], check=True)
    achados = varredura(tmp_path)
    assert any("opencode" in a for a in achados)


def test_excecao_e_ignorada(tmp_path):
    (tmp_path / "a.txt").write_text("gerado por claude\n", encoding="utf-8")
    assert varredura(tmp_path, excecoes=[tmp_path / "a.txt"]) == []


def test_mensagem_de_commit_com_marcador_e_acusada(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Pessoa"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "pessoa@exemplo"], check=True)
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "Co-Authored-By: Alguem <alguem@exemplo>"], check=True)
    achados = varredura(tmp_path)
    assert any("co-authored" in a.lower() for a in achados)


def test_sigla_solta_e_acusada_mas_dentro_de_identificador_nao(tmp_path):
    (tmp_path / "a.txt").write_text("usamos IA no texto\n", encoding="utf-8")
    assert varredura(tmp_path) != []
    (tmp_path / "a.txt").unlink()
    (tmp_path / "b.txt").write_text("variavel ai = 1\ncampo ia_um\n", encoding="utf-8")
    assert varredura(tmp_path) == []
