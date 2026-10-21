import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar, validar, ordem_publicacao

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"


def test_exemplo_carrega_e_passa_na_validacao():
    m = carregar(str(EXEMPLO))
    assert m["projeto"] == "Digital Solution MFG Run"
    assert validar(m) == []


def test_dependencia_ausente_e_acusada():
    m = carregar(str(EXEMPLO))
    m["componentes"][0]["dependeDe"] = ["nao-existe"]
    assert any("nao-existe" in e for e in validar(m))


def test_dependencia_ciclica_e_acusada():
    m = carregar(str(EXEMPLO))
    m["componentes"][0]["dependeDe"] = [m["componentes"][1]["repo"]]
    m["componentes"][1]["dependeDe"] = [m["componentes"][0]["repo"]]
    assert any("ciclo" in e.lower() for e in validar(m))


def test_tipo_desconhecido_e_acusado():
    m = carregar(str(EXEMPLO))
    m["componentes"][0]["tipo"] = "maven-zip"
    m["componentes"][0]["publica"] = False
    assert any("tipo" in e.lower() for e in validar(m))


def test_ordem_publicacao_respeita_dependencias():
    m = carregar(str(EXEMPLO))
    ordem = ordem_publicacao(m)
    assert ordem.index("ITSecurityService") < ordem.index("ERPConsultaWeb")
    assert ordem.index("erp-frontend-shared") < ordem.index("ERPConsultaWeb")


def test_ordem_respeita_grafo_mesmo_com_dependencia_que_nao_publica():
    """A ordem sai do grafo, nao da ordem do arquivo: uma dependencia que nao publica
    nao pode empurrar o dependente para o fim."""
    m = carregar(str(EXEMPLO))
    # neway-lib nao publica, mas e dependencia de tudo: nao pode mudar nada
    antes = ordem_publicacao(m)
    # inverte a ordem do arquivo: o resultado topologico tem de ser o mesmo
    m["componentes"].reverse()
    depois = ordem_publicacao(m)
    assert antes == depois


def test_ordem_respeita_grafo_com_dependencia_que_publica_no_fim():
    m = carregar(str(EXEMPLO))
    # tira o componente que vem antes e depende de outro, e poe no fim
    alvo = [c for c in m["componentes"] if c["repo"] == "ITSecurityService"][0]
    m["componentes"].remove(alvo)
    m["componentes"].append(alvo)
    ordem = ordem_publicacao(m)
    assert ordem.index("ITSecurityService") < ordem.index("ERPConsultaWeb")


def test_campos_de_topo_obrigatorios_sao_acusados():
    m = carregar(str(EXEMPLO))
    del m["projeto"]
    assert any("projeto" in e.lower() for e in validar(m))


def test_caminho_duplicado_e_acusado():
    m = carregar(str(EXEMPLO))
    m["componentes"][1]["caminho"] = m["componentes"][0]["caminho"]
    assert any("duplicado" in e.lower() for e in validar(m))


def test_responsavel_e_obrigatorio():
    m = carregar(str(EXEMPLO))
    del m["responsavel"]
    assert any("responsavel" in e.lower() for e in validar(m))


def test_componentes_vazio_e_acusado():
    m = carregar(str(EXEMPLO))
    m["componentes"] = []
    assert validar(m) != []


def test_versao_invalida_e_acusada():
    m = carregar(str(EXEMPLO))
    m["componentes"][0]["versao"] = "nao-e-versao"
    assert any("versao" in e.lower() for e in validar(m))


def test_publica_tem_de_ser_booleano():
    m = carregar(str(EXEMPLO))
    m["componentes"][0]["publica"] = "talvez"
    assert any("publica" in e.lower() for e in validar(m))
