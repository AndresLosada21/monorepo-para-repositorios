import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar, ordem_publicacao
from scripts.publicar_feed import (comandos_publicar, settings_maven, token_npmrc, url_do_feed,
                                   versoes_no_feed)

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


def test_comandos_do_dry_run_sao_os_mesmos_do_que_roda():
    """O que o dry-run mostra tem de ser o que roda: senao o operador confere um comando diferente."""
    from scripts.publicar_feed import comandos_de_execucao, comandos_publicar
    c = _componente(4)
    url = "https://exemplo/feed/v1"
    mostrado = comandos_publicar(c, url)[0]
    executado = comandos_de_execucao(c, url, "settings-feed.xml", "m2")[0]
    # a mesma forma: mesmos executaveis, mesmos argumentos, so o caminho do arquivo varia
    assert mostrado[0] == executado[0]
    assert mostrado[:3] == executado[:3]
    assert "REPO_LOCAL" in " ".join(executado) or "m2" in " ".join(executado)


def test_comandos_de_execucao_usa_o_settings_e_o_repo_locais_reais():
    from scripts.publicar_feed import comandos_de_execucao
    cmd = comandos_de_execucao(_componente(4), "https://exemplo/feed/v1", "/tmp/settings.xml", "/tmp/m2")[0]
    texto = " ".join(cmd)
    assert "/tmp/settings.xml" in texto
    assert "/tmp/m2" in texto
    assert "REPO_LOCAL" not in texto


def test_comandos_de_execucao_npm_usa_o_registro():
    from scripts.publicar_feed import comandos_de_execucao
    cmd = comandos_de_execucao(_componente(3), "https://exemplo/registry/", "/tmp/s", "/tmp/m2")[0]
    assert "publish" in cmd
    assert "https://exemplo/registry/" in cmd


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


def test_npmrc_usa_o_formato_que_o_npm_reconhece():
    """O npm procura a credencial por //host/path, nao por https://host/path."""
    texto = token_npmrc("https://pkgs.dev.azure.com/org/Projeto/_packaging/feed/npm/registry/", "SEGREDO")
    assert texto.startswith("//pkgs.dev.azure.com/")
    assert texto.rstrip().endswith(":_authToken=SEGREDO")


def test_settings_maven_tem_o_id_do_feed_e_a_credencial_por_variavel():
    texto = settings_maven("https://exemplo/feed/v1", "mfg-java")
    assert "<id>mfg-java</id>" in texto
    assert "${env.MAVEN_FEED_TOKEN}" in texto
    assert "SEGREDO" not in texto


def test_settings_maven_nao_redireciona_tudo_para_o_feed():
    """Com mirrorOf=* o build inteiro passa pelo feed, o que amarra o build ao feed."""
    texto = settings_maven("https://exemplo/feed/v1", "mfg-java")
    assert "<mirrorOf>*</mirrorOf>" not in texto


def test_versoes_no_feed_aceita_pacote_sem_escopo():
    """Um pacote npm sem escopo ou um groupId fora de br.com tambem precisa ser visto."""
    import json
    from scripts.publicar_feed import _mapa_de_pacotes
    dados = {"value": [
        {"name": "br.com.yamaha:x", "versions": [{"version": "1.0.0"}]},
        {"name": "pacote-sem-escopo", "versions": [{"version": "2.0.0"}]},
        {"name": "outro.time:lib", "versions": [{"version": "3.0.0"}]},
    ]}
    mapa = _mapa_de_pacotes(dados)
    assert mapa["br.com.yamaha:x"] == ["1.0.0"]
    assert mapa["pacote-sem-escopo"] == ["2.0.0"]
    assert mapa["outro.time:lib"] == ["3.0.0"]


def test_versoes_no_feed_avisa_quando_a_leitura_falha():
    """Falha de rede ou de token nao pode parecer 'feed vazio'."""
    from scripts.publicar_feed import versoes_no_feed
    try:
        resultado = versoes_no_feed({"org": "x", "projeto": "y", "feed": "z"}, "token-invalido")
    except Exception as e:
        return  # levantar a excecao e o comportamento correto
    assert resultado is None, "a leitura falhou mas o script devolveu um feed vazio"
