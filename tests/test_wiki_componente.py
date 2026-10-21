import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.modelo_wiki import ORDEM, gerar_secoes

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"


def _componente():
    return carregar(str(EXEMPLO))["componentes"][4]


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
    c = carregar(str(EXEMPLO))["componentes"][3]
    dados = _dados()
    dados.update({"tipo": "npm-pkg", "versao": "1.0.0", "artefato": c["artefato"],
                  "arquivo": "shared-1.0.0.tgz", "porta": ""})
    secoes = gerar_secoes(c, dados)
    assert "npm" in secoes["Build"]
    assert "Node 24" in secoes["Build"]
