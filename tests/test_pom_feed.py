"""Testes do pom: o feed tem que entrar sem duplicar tag e o destino antigo tem que sair."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.separar import escrever_pom_independente  # noqa: E402


def _pom(tmp_path, corpo, nome="pom.xml"):
    p = tmp_path / nome
    p.write_text(corpo, encoding="utf-8")
    return p


def test_pom_na_ordem_canonica_do_maven_nao_duplica_repositories(tmp_path):
    """Na ordem do Maven (dependencies antes de repositories) a tag nao pode ficar duplicada."""
    pom = _pom(tmp_path, """<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <dependencies>
    <dependency><groupId>br.com.neway</groupId><artifactId>neway-lib</artifactId><version>1.0.0-SNAPSHOT</version></dependency>
  </dependencies>
</project>
""")
    escrever_pom_independente(pom, "2.0.0", "https://feed/v1", {"neway-lib": "1.0.0"}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert t.count("<repositories>") == 1, t
    assert t.count("<distributionManagement>") == 1, t
    assert "https://feed/v1" in t


def test_pom_que_ja_tem_repositories_nao_ganha_tag_duplicada(tmp_path):
    pom = _pom(tmp_path, """<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <repositories>
    <repository><id>interno</id><url>https://interno/v1</url></repository>
  </repositories>
  <dependencies></dependencies>
</project>
""")
    escrever_pom_independente(pom, "2.0.0", "https://feed/v1", {}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert t.count("<repositories>") == 1, t
    assert t.count("<distributionManagement>") == 1, t
    # o repositorio interno continua valendo
    assert "https://interno/v1" in t, t


def test_pom_com_destino_antigo_troca_pelo_feed(tmp_path):
    """Com distributionManagement apontando para outro lugar, o deploy tem de ir para o feed."""
    pom = _pom(tmp_path, """<project>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <distributionManagement>
    <repository>
      <id>antigo</id>
      <url>https://antigo/v1</url>
    </repository>
  </distributionManagement>
  <dependencies></dependencies>
</project>
""")
    escrever_pom_independente(pom, "2.0.0", "https://feed/v1", {}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert "https://antigo/v1" not in t, t
    assert "https://feed/v1" in t, t
    assert "<id>mfg-java</id>" in t, t


def test_pom_sem_versao_propria_recebe_a_do_manifesto(tmp_path):
    """Sem <version> propria, o projeto herda a do pai: a versao do manifesto precisa entrar."""
    pom = _pom(tmp_path, """<project>
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.1</version>
  </parent>
  <groupId>br.com.yamaha</groupId>
  <artifactId>x</artifactId>
  <dependencies></dependencies>
</project>
""")
    escrever_pom_independente(pom, "2.0.0", "https://feed/v1", {}, "mfg-java")
    t = pom.read_text(encoding="utf-8")
    assert "<version>2.0.0</version>" in t, t
    # a versao do pai nao foi atropelada
    assert "<artifactId>spring-boot-starter-parent</artifactId>\n    <version>4.1.1</version>" in t, t
