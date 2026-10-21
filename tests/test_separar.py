import os
import pathlib
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.separar import (comandos_de_publicacao, conferir_caminhos, escrever_package_independente,
                             escrever_pom_independente, gerar_comandos, responsavel_do_manifesto)

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"
AMBIENTE = {k: v for k, v in os.environ.items()
            if k not in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                         "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}


def _componente():
    m = carregar(str(EXEMPLO))
    return dict(m["componentes"][0], monorepo=m["monorepo"], responsavel=m["responsavel"])


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, env=AMBIENTE)


def test_comandos_pegam_o_historico_no_monorepo():
    """O historico vem do monorepo; o repositorio novo so recebe o resultado."""
    c = _componente()
    cmds = gerar_comandos(c, pathlib.Path("/tmp/x"))
    texto = " ".join(" ".join(x) for x in cmds)
    assert c["monorepo"]["url"] in texto
    assert "--path-rename" in texto
    assert "libs/neway-lib/:" in texto


def test_comandos_tem_mailmap_e_substituicao_de_texto():
    cmds = gerar_comandos(_componente(), pathlib.Path("/tmp/x"))
    texto = " ".join(" ".join(x) for x in cmds)
    assert "--mailmap" in texto
    assert "--replace-text" in texto


def test_todo_comando_de_histórico_desliga_o_autocrlf():
    cmds = gerar_comandos(_componente(), pathlib.Path("/tmp/x"))
    for cmd in cmds:
        if cmd[0] == "git" and "filter-repo" in cmd or (cmd[0] == "git" and "fetch" in cmd):
            assert "core.autocrlf=false" in cmd, cmd


def test_responsavel_vem_do_manifesto():
    m = carregar(str(EXEMPLO))
    m["responsavel"] = {"nome": "Fulano de Tal", "email": "fulano@exemplo"}
    assert responsavel_do_manifesto(m) == ("Fulano de Tal", "fulano@exemplo")


def test_caminho_inexistente_e_acusado_antes_de_escrever(tmp_path):
    erros = conferir_caminhos(_componente(), tmp_path)
    assert erros and "libs/neway-lib" in erros[0]


def test_caminho_existente_nao_e_acusado(tmp_path):
    (tmp_path / "libs" / "neway-lib").mkdir(parents=True)
    assert conferir_caminhos(_componente(), tmp_path) == []


def test_pom_independente_declara_versao_e_feed(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>middleware</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>4.1.1</version></parent>
  <dependencies>
    <dependency><groupId>br.com.neway</groupId><artifactId>neway-lib</artifactId><version>1.0.0-SNAPSHOT</version></dependency>
  </dependencies>
</project>
""", encoding="utf-8")
    escrever_pom_independente(pom, "1.0.0", "https://exemplo/feed/v1", {"neway-lib": "1.0.0"}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert "<version>1.0.0</version>" in t
    assert "SNAPSHOT" not in t
    assert "https://exemplo/feed/v1" in t
    assert "<distributionManagement>" in t


def test_pom_independente_preserva_o_parent():
    tmp_path = pathlib.Path(os.environ.get("TEMP", ".")) / "pom-teste"
    tmp_path.mkdir(exist_ok=True)
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>4.1.1</version></parent>
  <dependencies></dependencies>
</project>
""", encoding="utf-8")
    escrever_pom_independente(pom, "2.0.0", "https://exemplo/feed/v1", {}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert "<artifactId>spring-boot-starter-parent</artifactId>" in t
    assert "<version>4.1.1</version>" in t


def test_pom_que_ja_tem_repositories_nao_ganha_tag_duplicada():
    tmp_path = pathlib.Path(os.environ.get("TEMP", ".")) / "pom-teste2"
    tmp_path.mkdir(exist_ok=True)
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <repositories>
    <repository><id>interno</id><url>https://interno/v1</url></repository>
  </repositories>
  <dependencies></dependencies>
</project>
""", encoding="utf-8")
    escrever_pom_independente(pom, "2.0.0", "https://exemplo/feed/v1", {}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert t.count("<repositories>") == 1
    assert t.count("<distributionManagement>") == 1


def test_id_do_feed_vem_do_manifesto():
    tmp_path = pathlib.Path(os.environ.get("TEMP", ".")) / "pom-teste3"
    tmp_path.mkdir(exist_ok=True)
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <dependencies></dependencies>
</project>
""", encoding="utf-8")
    escrever_pom_independente(pom, "2.0.0", "https://exemplo/feed/v1", {}, "outro-feed")
    t = pom.read_text(encoding="utf-8")
    assert "<id>outro-feed</id>" in t
    assert "mfg-java" not in t


def test_branch_padrao_ruim_e_detectado(tmp_path):
    """A funcao diz que a branch padrao NAO e a esperada quando o remoto traz outra."""
    origem = tmp_path / "origem.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origem)], check=True, env=AMBIENTE)
    trabalho = tmp_path / "trabalho"
    trabalho.mkdir()
    _git(trabalho, "init", "-q", "-b", "main")
    _git(trabalho, "config", "user.name", "Pessoa")
    _git(trabalho, "config", "user.email", "pessoa@exemplo")
    (trabalho / "a.txt").write_text("x\n", encoding="utf-8")
    _git(trabalho, "add", "-A")
    _git(trabalho, "commit", "-q", "-m", "c")
    _git(trabalho, "remote", "add", "origin", str(origem))
    _git(trabalho, "push", "-q", "origin", "main")
    from scripts.separar import verificar_branch_padrao
    assert verificar_branch_padrao(str(origem), "reorganizacao/x") is False
    _git(trabalho, "checkout", "-q", "-b", "reorganizacao/x")
    _git(trabalho, "push", "-q", "origin", "reorganizacao/x")
    _git(origem, "symbolic-ref", "HEAD", "refs/heads/reorganizacao/x")
    assert verificar_branch_padrao(str(origem), "reorganizacao/x") is True


def test_comandos_de_publicacao_dependem_do_manifesto():
    cmds = comandos_de_publicacao(_componente(), "https://exemplo/feed/v1")
    texto = " ".join(" ".join(x) for x in cmds)
    assert "push" in texto
