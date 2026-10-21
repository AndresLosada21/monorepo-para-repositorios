import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.modelo_wiki import ORDEM, gerar_secoes
from scripts.wiki_componente import _endpoints, _propriedades, _versao_e_artefato, extrair_dados

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"


def _componente(repo="ITSecurityService"):
    return [c for c in carregar(str(EXEMPLO))["componentes"] if c["repo"] == repo][0]


def _dados():
    c = _componente()
    return {
        "contexto": "/itSecurityService", "porta": "8081", "versao": "2.0.0",
        "artefato": c["artefato"], "arquivo": "itSecurityService.war", "tipo": "maven-war",
        "propriedades": [("erp.jwt.secret", "${ERP_JWT_SECRET}", "sim", "chave de assinatura")],
        "segredos": [("ERP_JWT_SECRET", "chave HS256 da credencial")],
        "endpoints": [("POST", "/security/refresh", "renova a credencial")],
        "testes": "17 testes", "dependencias": ["neway-lib 1.0.0"],
        "ambiente": "Tomcat 11",
    }


def test_gera_oito_secoes_na_ordem_certa():
    secoes = gerar_secoes(_componente(), _dados())
    assert list(secoes) == ORDEM
    assert len(secoes) == 8


def test_secao_de_versao_tem_a_versao_publicada():
    secoes = gerar_secoes(_componente(), _dados())
    assert "2.0.0" in secoes["Versoes"]


def test_visao_geral_tem_artefato_dependencias_e_descricao():
    c = _componente()
    secoes = gerar_secoes(c, _dados())
    v = secoes["Visao-geral"]
    assert c["artefato"] in v
    assert c["descricao"][:30] in v
    assert "neway-lib 1.0.0" in v


def test_configuracao_lista_propriedades_e_segredos():
    secoes = gerar_secoes(_componente(), _dados())
    cfg = secoes["Configuracao"]
    assert "erp.jwt.secret" in cfg
    assert "ERP_JWT_SECRET" in cfg


def test_deploy_tem_contexto_porta_e_conferencia():
    secoes = gerar_secoes(_componente(), _dados())
    dep = secoes["Deploy"]
    assert "/itSecurityService" in dep
    assert "8081" in dep
    assert "/security/refresh" in dep


def test_build_tem_comando_e_ferramentas():
    secoes = gerar_secoes(_componente(), _dados())
    b = secoes["Build"]
    assert "mvn" in b
    assert "JDK 25" in b
    assert "itSecurityService.war" in b


def test_pacote_npm_tem_ferramentas_de_node():
    c = _componente("erp-frontend-shared")
    dados = _dados()
    dados.update({"tipo": "npm-pkg", "versao": "1.0.0", "artefato": c["artefato"],
                  "arquivo": "shared-1.0.0.tgz", "porta": ""})
    secoes = gerar_secoes(c, dados)
    assert "npm" in secoes["Build"]
    assert "Node 24" in secoes["Build"]


# --- extracao de dados do codigo ---

def _controller(tmp_path, corpo):
    p = tmp_path / "src" / "main" / "java" / "br" / "yamaha" / "x" / "Ctrl.java"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(corpo, encoding="utf-8")
    return tmp_path


def test_endpoints_acham_get_e_post_mapping(tmp_path):
    pasta = _controller(tmp_path, """
package br.com.yamaha.x;
import org.springframework.web.bind.annotation.*;
@RestController
public class Ctrl {
    @GetMapping("/a")
    public String a() { return ""; }
    @PostMapping("/b")
    public String b() { return ""; }
}
""")
    eps = _endpoints(pasta)
    metodos = {e[1]: e[0] for e in eps}
    assert metodos.get("/a") == "GET"
    assert metodos.get("/b") == "POST"


def test_endpoints_acham_request_mapping_com_metodo_explicito(tmp_path):
    pasta = _controller(tmp_path, """
package br.com.yamaha.x;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/base")
public class Ctrl {
    @RequestMapping(value = "/a", method = RequestMethod.GET)
    public String a() { return ""; }
}
""")
    eps = _endpoints(pasta)
    assert ("GET", "/a", eps[0][2]) in eps


def test_endpoints_pegam_o_request_mapping_de_classe(tmp_path):
    pasta = _controller(tmp_path, """
package br.com.yamaha.x;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/base")
public class Ctrl {
    @GetMapping("/a")
    public String a() { return ""; }
}
""")
    rotas = [e[1] for e in _endpoints(pasta)]
    assert "/base/a" in rotas


def test_propriedades_leem_yml_com_dois_pontos(tmp_path):
    r = tmp_path / "src" / "main" / "resources"
    r.mkdir(parents=True)
    (r / "application.yml").write_text("server:\n  port: 8081\n  servlet:\n    context-path: /x\n"
                                      "erp:\n  jwt:\n    secret: ${ERP_JWT_SECRET:}\n", encoding="utf-8")
    contexto, porta, props = _propriedades(tmp_path)
    assert contexto == "/x"
    assert porta == "8081"
    assert any(k == "erp.jwt.secret" for k, _, _, _ in props)


def test_versao_e_artefato_ignoram_o_parent(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.1</version>
  </parent>
  <groupId>br.com.yamaha</groupId>
  <artifactId>meuServico</artifactId>
  <version>2.0.0</version>
  <packaging>war</packaging>
</project>
""", encoding="utf-8")
    c = {"tipo": "maven-war", "artefato": "br.com.yamaha:meuServico", "versao": "2.0.0"}
    versao, artefato, arquivo = _versao_e_artefato(tmp_path, c)
    assert versao == "2.0.0"
    assert artefato == "br.com.yamaha:meuServico"
    assert arquivo == "meuServico.war"


def test_extrair_dados_nao_devolve_o_proprio_componente_como_dependencia(tmp_path):
    c = _componente()
    (tmp_path / "pom.xml").write_text(
        "<project><groupId>br.com.yamaha</groupId><artifactId>x</artifactId><version>1.0.0</version></project>",
        encoding="utf-8")
    dados = extrair_dados(tmp_path, c)
    assert c["repo"] not in dados["dependencias"]
