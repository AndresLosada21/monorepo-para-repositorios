import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.separar import conferir_caminhos, gerar_comandos, escrever_pom_independente, verificar_branch_padrao

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"


def _componente():
    return carregar(str(EXEMPLO))["componentes"][0]


def test_comandos_tem_filtro_de_renomeacao_de_pasta():
    cmds = gerar_comandos(_componente(), pathlib.Path("/tmp/x"))
    texto = " ".join(" ".join(c) for c in cmds)
    assert "--path-rename" in texto
    assert "libs/neway-lib/:" in texto


def test_comandos_tem_mailmap_e_substituicao_de_texto():
    cmds = gerar_comandos(_componente(), pathlib.Path("/tmp/x"))
    texto = " ".join(" ".join(c) for c in cmds)
    assert "--mailmap" in texto
    assert "--replace-text" in texto


def test_comandos_forcam_autocrlf_off():
    cmds = gerar_comandos(_componente(), pathlib.Path("/tmp/x"))
    assert any("-c" in c and "core.autocrlf=false" in c for c in cmds)


def test_caminho_inexistente_e_acusado_antes_de_escrever(tmp_path):
    m = carregar(str(EXEMPLO))
    c = m["componentes"][0]
    erros = conferir_caminhos(c, tmp_path)
    assert erros and "libs/neway-lib" in erros[0]


def test_caminho_existente_nao_e_acusado(tmp_path):
    (tmp_path / "libs" / "neway-lib").mkdir(parents=True)
    erros = conferir_caminhos(_componente(), tmp_path)
    assert erros == []


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
    escrever_pom_independente(pom, "1.0.0", "https://exemplo/feed/v1", {"neway-lib": "1.0.0"})
    t = pom.read_text(encoding="utf-8")
    assert "<version>1.0.0</version>" in t
    assert "SNAPSHOT" not in t
    assert "https://exemplo/feed/v1" in t
    assert "<distributionManagement>" in t


def test_pom_independente_preserva_o_parent():
    tmp_path = pathlib.Path(__import__("tempfile").mkdtemp())
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>4.1.1</version></parent>
  <dependencies></dependencies>
</project>
""", encoding="utf-8")
    escrever_pom_independente(pom, "2.0.0", "https://exemplo/feed/v1", {})
    t = pom.read_text(encoding="utf-8")
    assert "<artifactId>spring-boot-starter-parent</artifactId>" in t
    assert "<version>4.1.1</version>" in t


def test_branch_padrao_ruim_e_detectado(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert verificar_branch_padrao(str(tmp_path), "reorganizacao/x") is False
