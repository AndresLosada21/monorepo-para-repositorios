import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar, validar

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
    from scripts.manifesto import ordem_publicacao
    m = carregar(str(EXEMPLO))
    ordem = ordem_publicacao(m)
    assert ordem.index("ITSecurityService") < ordem.index("ERPConsultaWeb")
    assert ordem.index("erp-frontend-shared") < ordem.index("ERPConsultaWeb")
