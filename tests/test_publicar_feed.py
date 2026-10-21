import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar, ordem_publicacao
from scripts.publicar_feed import comandos_publicar, url_do_feed

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"


def _componente(indice=4):
    return carregar(str(EXEMPLO))["componentes"][indice]


def test_ordem_respeita_dependencias():
    m = carregar(str(EXEMPLO))
    ordem = ordem_publicacao(m)
    assert ordem.index("ITSecurityService") < ordem.index("ERPConsultaWeb")
    assert ordem.index("erp-frontend-shared") < ordem.index("ERPConsultaWeb")


def test_comandos_maven_usa_o_pom_e_o_feed():
    cmds = comandos_publicar(_componente(4), "https://exemplo/feed/v1")
    texto = " ".join(" ".join(x) for x in cmds)
    assert "deploy" in texto
    assert "https://exemplo/feed/v1" in texto


def test_comandos_npm_usa_publish():
    cmds = comandos_publicar(_componente(3), "https://exemplo/registry/")
    texto = " ".join(" ".join(x) for x in cmds)
    assert "publish" in texto
    assert "https://exemplo/registry/" in texto


def test_url_do_feed_maven_e_npm():
    m = carregar(str(EXEMPLO))
    maven = url_do_feed(m, "maven")
    npm = url_do_feed(m, "npm")
    assert maven.endswith("/maven/v1")
    assert npm.endswith("/npm/registry/")
    assert "mfg-java" in maven


def test_componente_que_nao_publica_nao_entra_na_ordem():
    m = carregar(str(EXEMPLO))
    ordem = ordem_publicacao(m)
    assert "neway-lib" not in ordem
    assert "SearchitExecutorService" not in ordem
