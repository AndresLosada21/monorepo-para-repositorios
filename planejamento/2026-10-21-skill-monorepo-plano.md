# Skill monorepo-para-repositorios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar, no GitHub, a skill que transforma um monorepo em N repositórios prontos para o DevOps: com histórico preservado, sem rastro de IA, com Wiki de código padronizada e com as versões publicadas no feed.

**Architecture:** Um manifesto JSON descreve o que fazer (repositório, pasta de origem, artefato, versão, dependências). Quatro scripts leem esse manifesto e fazem o trabalho: `varrer.py` (acha rastro de IA), `separar.py` (separa e reescreve o histórico), `wiki_componente.py` (gera e publica a documentação) e `publicar_feed.py` (publica no feed na ordem das dependências). O `SKILL.md` é o roteiro das seis fases; as `references/` guardam o que deu errado e o que o DevOps precisa.

**Tech Stack:** Python 3.12 (sem dependência externa), `git` com `git-filter-repo`, Azure DevOps CLI (`az`) e API REST do Azure DevOps, Azure Artifacts (`mfg-java`), Azure Pipelines não é escopo.

**Spec:** `planejamento/2026-10-21-skill-monorepo-design.md`

## Global Constraints

- Idioma: português do Brasil. Termos de ferramenta ficam em inglês (Git, Azure DevOps, Maven, npm, feed, branch, commit).
- Nenhum segredo em arquivo, script, commit ou Wiki. A credencial do feed vem do token AAD (`az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798`), em memória, via `http.extraHeader` no Git, variável de ambiente no Maven e arquivo de usuário temporário no npm.
- A skill não varre a si mesma. Isso vale para o `SKILL.md` e para o repositório inteiro da skill.
- Todo script aceita `--dry-run` e imprime o que faria, sem escrever.
- Todo script que escreve pede confirmação explícita, salvo `--sim`.
- `core.autocrlf=false` em toda operação que mexe em histórico. Sem isso, o nome de arquivo ganha `\r` e a árvore fica corrompida.
- Toda reescrita de histórico que substitui a branch padrão usa commit de merge, para permitir push normal. *Force push* só com autorização explícita.
- Cada script é autocontido: lê o manifesto, não importa os outros.
- A skill fica em `~/.config/opencode/skills/monorepo-para-repositorios` e o repositório `AndresLosada21/monorepo-para-repositorios` tem a mesma estrutura na raiz.

## Review Focus

Cinco falhas que nenhuma tarefa exercita por acaso e que já mordem quem opera essa ferramenta:

1. **Manifesto com `caminho` que não existe no monorepo** — a separação vai gerar um repositório vazio e o pull request vai passar sem erro visível. O comportamento esperado: o script falha antes de escrever, naming the path it did not find.
2. **Componente cujo `dependeDe` aponta para outro não declarado no manifesto** — a ordem de publicação fica incompleta e o build do dependente quebra em algum ambiente. O comportamento esperado: o script acusa o ciclo ou a dependência ausente.
3. **Versão já publicada no feed** — o `mvn deploy` devolve 409 e o script não deve tentar contornar. O comportamento esperado: o script detecta antes de publicar e diz para subir a próxima versão.
4. **Texto do componente com caractere que o `filter-repo --replace-text` não alcança** (regex multilinha, ou `\r` no fim da linha) — a limpeza fica pela metade e o rastro sobrevive. O comportamento esperado: a varredura depois da reescrita acusa o que sobrou.
5. **Branch padrão do repositório continua com o código antigo** — quem clona recebe a versão errada, e o erro só aparece em produção. O comportamento esperado: a separação confere a branch padrão de cada repositório e corrige antes de seguir.

---

### Task 1: Esqueleto do repositório e o manifesto de exemplo

**Files:**
- Create: `README.md`
- Create: `manifesto_exemplo.json`
- Create: `scripts/__init__.py` (vazio, marca o pacote)
- Create: `tests/test_manifesto.py`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: nada.
- Produces: `scripts/manifesto.py` com `carregar(caminho: str) -> dict` e `validar(m: dict) -> list[str]`, importado pelas tarefas seguintes. O formato do manifesto é o do `manifesto_exemplo.json`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_manifesto.py`:

```python
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
    m["componentes"][0]["tipo"] = "maven-jar"
    m["componentes"][0]["publica"] = False
    assert any("tipo" in e.lower() for e in validar(m))
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_manifesto.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.manifesto'`

- [ ] **Step 3: Criar `scripts/manifesto.py`**

```python
"""Leitura e validação do manifesto que descreve a divisão."""
import json
from pathlib import Path

TIPOS = {"maven-lib", "maven-war", "maven-jar", "npm-pkg"}
CAMPOS = ("repo", "caminho", "artefato", "tipo", "versao", "publica", "dependeDe", "descricao")


def carregar(caminho: str) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def validar(m: dict) -> list[str]:
    """Devolve a lista de problemas; vazia significa manifesto utilizável."""
    erros = []
    componentes = m.get("componentes") or []
    nomes = {c.get("repo") for c in componentes}
    for c in componentes:
        for campo in CAMPOS:
            if campo not in c:
                erros.append(f"{c.get('repo', '?')}: falta o campo '{campo}'")
        if c.get("tipo") not in TIPOS:
            erros.append(f"{c.get('repo', '?')}: tipo desconhecido '{c.get('tipo')}'")
        for dep in c.get("dependeDe") or []:
            if dep not in nomes:
                erros.append(f"{c.get('repo', '?')}: depende de '{dep}', que não está no manifesto")
    erros += _ciclos(componentes)
    return erros


def _ciclos(componentes) -> list[str]:
    """Detecta ciclo no grafo de dependências."""
    grafo = {c.get("repo"): list(c.get("dependeDe") or []) for c in componentes}
    estado, pilha = {}, []

    def visita(no):
        if estado.get(no) == "aberto":
            return pilha + [no]
        if estado.get(no) == "fechado":
            return None
        estado[no] = "aberto"
        pilha.append(no)
        for viz in grafo.get(no, []):
            achado = visita(viz)
            if achado:
                return achado
        pilha.pop()
        estado[no] = "fechado"
        return None

    for no in grafo:
        achado = visita(no)
        if achado:
            return [f"ciclo de dependências: {' -> '.join(achado)}"]
    return []


def ordem_publicacao(m: dict) -> list[str]:
    """Ordem em que os componentes com 'publica' podem ir para o feed."""
    componentes = {c["repo"]: c for c in m.get("componentes", [])}
    prontos, ordem = set(), []

    def pode(repo):
        return all(d in prontos for d in componentes[repo].get("dependeDe") or [])

    restantes = [c["repo"] for c in m.get("componentes", []) if c.get("publica")]
    while restantes:
        for repo in list(restantes):
            if pode(repo):
                ordem.append(repo)
                prontos.add(repo)
                restantes.remove(repo)
                break
        else:
            ordem += restantes
            break
    return ordem
```

- [ ] **Step 4: Criar `manifesto_exemplo.json`**

Conteúdo: projeto "Digital Solution MFG Run", org "yamahaind", feed "mfg-java", monorepo apontando para `ERPConsulta` na branch `main`, wiki com raiz `/Java/ERP Consulta` e página de arquitetura "Arquitetura e Deploy", e os doze componentes do caso real: `neway-lib` (libs/neway-lib, maven-lib, 1.0.0, publica false), `Middleware` (libs/middleware, maven-lib, 1.0.0, false), `FinancialDcreModel` (libs/financialdcre-model, maven-lib, 1.0.0, false), `erp-frontend-shared` (frontend/packages/shared, npm-pkg, 1.0.0, true), `ITSecurityService` (apps/it-security-service, maven-war, 2.0.0, true, depende de neway-lib, Middleware e FinancialDcreModel), `SearchitService` (apps/searchit-service, maven-war, 2.0.0, true, depende de neway-lib e Middleware), `SearchitExecutorService` (apps/searchit-executor-service, maven-war, 1.0.0, false, depende de neway-lib e Middleware), `SearchitGateway` (apps/searchit-gateway, maven-jar, 2.0.1, true, depende de neway-lib e erp-frontend-shared) e `ERPConsultaWeb` (apps/erp-gateway, maven-war, 2.0.1, true, depende de neway-lib e erp-frontend-shared).

- [ ] **Step 5: Criar `pyproject.toml` e `README.md`**

`pyproject.toml` declara o pacote `scripts`, exige Python 3.11 ou mais novo e configura `pytest` com `testpaths = ["tests"]`.

`README.md`: o que a skill faz, a estrutura dos arquivos, o manifesto como fonte única, as seis fases, como instalar (copiar a pasta para `~/.config/opencode/skills/`) e a nota de que a skill não varre a si mesma.

- [ ] **Step 6: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_manifesto.py -v`
Expected: 4 PASS

- [ ] **Step 7: Commitar**

```bash
git add README.md manifesto_exemplo.json pyproject.toml scripts/manifesto.py scripts/__init__.py tests/test_manifesto.py
git commit -m "feat: esqueleto da skill e manifesto de exemplo"
```

---

### Task 2: varrer.py

**Files:**
- Create: `scripts/varrer.py`
- Create: `tests/test_varrer.py`

**Interfaces:**
- Consumes: nada.
- Produces: `varrer.varredura(pasta: Path, excecoes: list[Path] | None = None) -> list[str]`, devolve a lista de achados (vazia quando limpo). `varrer.main(argv) -> int` devolve 0 quando limpo e 1 quando há achado. O padrão de busca é o do `references/armadilhas.md`: nomes de ferramenta, marcadores de autoria automática e o vocabulário do processo de agente.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_varrer.py`:

```python
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
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_varrer.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.varrer'`

- [ ] **Step 3: Implementar `scripts/varrer.py`**

Módulos: `re`, `subprocess`, `sys` e `pathlib`. Uma lista de padrões compilados, com a regra de não acusar dentro de identificador técnico: o termo só vale quando é palavra solta, com `\b` nas bordas e `\bIA\b` e `\bAI\b` exigindo que não estejam colados a letra ou sinal. Percorre: (a) a árvore atual, ignorando binários e `package-lock.json`; (b) o histórico, com `git log --all -p`; (c) autores e committers, com `git log --all --format=%an <%ae>`; (d) as mensagens, com `git log --all --format=%s%n%b`. Cada achado sai como `caminho:linha: trecho`. A função `varredura` recebe `excecoes` como lista de caminhos absolutos a ignorar.

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_varrer.py -v`
Expected: 4 PASS

- [ ] **Step 5: Conferir contra os nove repositórios reais**

Run: `python scripts/varrer.py <pasta-do-repo> --historico` para cada um dos nove repositórios clonados do projeto "Digital Solution MFG Run".
Expected: 0 achados em cada um, e código de saída 0.

- [ ] **Step 6: Commitar**

```bash
git add scripts/varrer.py tests/test_varrer.py
git commit -m "feat: varredura de rastro de IA em arvore, historico, autores e mensagens"
```

---

### Task 3: separar.py

**Files:**
- Create: `scripts/separar.py`
- Create: `tests/test_separar.py`

**Interfaces:**
- Consumes: `scripts.manifesto.carregar`, `scripts.manifesto.validar`, `scripts.manifesto.ordem_publicacao`.
- Produces: `separar.gerar_comandos(c: dict, destino: Path) -> list[list[str]]`, que devolve a lista de comandos git que separam um componente, sem executar. `separar.verificar_branch_padrao(url: str, esperado: str) -> bool`. `separar.main(argv) -> int`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_separar.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.separar import gerar_comandos

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
    m["monorepo"]["url"] = str(tmp_path)
    c = m["componentes"][0]
    from scripts.separar import conferir_caminhos
    erros = conferir_caminhos(c, tmp_path)
    assert erros and "libs/neway-lib" in erros[0]
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_separar.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.separar'`

- [ ] **Step 3: Implementar `scripts/separar.py`**

Funções:

- `gerar_comandos(c, destino) -> list[list[str]]`: devolve, na ordem, `git -c core.autocrlf=false -c core.quotepath=false init`, `git remote add origin <url>`, `git fetch origin`, `git filter-repo --force --path-rename "<caminho>/:" --mailmap <arquivo> --replace-text <arquivo> --refs <branch>`, e `git push origin <branch>:<branch>`. O `mktree` não entra: o `filter-repo` reconstrói a árvore sozinho.
- `conferir_caminhos(c, raiz) -> list[str]`: devolve a lista de erro quando a pasta `c["caminho"]` não existe na raiz clonada.
- `escrever_pom_independente(pom: Path, versao: str, feed_url: str) -> None`: põe a versão do artefato, troca as dependências internas para a versão fixada, e acrescenta o bloco `<repositories>` e `<distributionManagement>` com o `feed_url`, no lugar da primeira tag `<dependencies>` ou `<dependencyManagement>`.
- `escrever_package_independente(pkg: Path, versao: str, feed_url: str) -> None`: põe a versão, tira `private`, acrescenta `files` e `publishConfig.registry`.
- `verificar_branch_padrao(url, esperado) -> bool`: consulta `git ls-remote --symref <url> HEAD` e confere se o branch padrão é o esperado.
- `commitar_com_merge(mirror: Path, branch_nova: str, branch_antiga: str) -> str`: cria o commit de merge com a árvore da branch nova e os dois pais, para permitir push normal.
- `main(argv) -> int`: lê o manifesto, valida, e para cada componente executa a separação. Com `--dry-run`, imprime os comandos e não escreve. Com `--sim`, não pede confirmação.

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_separar.py -v`
Expected: 4 PASS

- [ ] **Step 5: Ensaiar num monorepo de teste**

Criar, num diretório temporário, um repositório Git com três pastas (`a/`, `b/`, `c/`), um arquivo em cada uma e três commits. Rodar `python scripts/separar.py --manifesto <manifesto-de-teste> --dry-run` e depois sem `--dry-run`.
Expected: três repositórios criados, cada um com o conteúdo da sua pasta na raiz e o histórico do commit que tocou aquela pasta preservado; a branch padrão de cada um é a branch do componente.

- [ ] **Step 6: Commitar**

```bash
git add scripts/separar.py tests/test_separar.py
git commit -m "feat: separa o monorepo em repositorios com historico preservado"
```

---

### Task 4: wiki_componente.py

**Files:**
- Create: `scripts/wiki_componente.py`
- Create: `scripts/modelo_wiki.py`
- Create: `tests/test_wiki_componente.py`

**Interfaces:**
- Consumes: `scripts.manifesto.carregar`.
- Produces: `modelo_wiki.gerar_secoes(c: dict, dados: dict) -> dict[str, str]`, que devolve o texto das oito seções a partir dos dados lidos do código. `wiki_componente.publicar_projeto(raiz_wiki: str, repo: str, texto: str, token: str) -> str`, que publica a cópia na Wiki do projeto e devolve o identificador da página. `wiki_componente.main(argv) -> int`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_wiki_componente.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar
from scripts.modelo_wiki import gerar_secoes, ORDEM

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"

def test_gera_oito_secoes_na_ordem_certa():
    c = carregar(str(EXEMPLO))["componentes"][4]
    dados = {
        "contexto": "/itSecurityService", "porta": "8081", "versao": "2.0.0",
        "artefato": c["artefato"], "arquivo": "itSecurityService.war",
        "propriedades": [("erp.jwt.secret", "${ERP_JWT_SECRET}", "sim", "chave de assinatura")],
        "segredos": [("ERP_JWT_SECRET", "chave HS256")],
        "endpoints": [("POST", "/security/refresh", "200")],
        "testes": "17 testes", "dependencias": ["neway-lib 1.0.0"],
    }
    secoes = gerar_secoes(c, dados)
    assert list(secoes) == ORDEM
    assert len(secoes) == 8

def test_secao_de_versao_tem_a_versao_publicada():
    c = carregar(str(EXEMPLO))["componentes"][4]
    dados = {"contexto": "/x", "porta": "1", "versao": "2.0.0", "artefato": c["artefato"],
              "arquivo": "a.war", "propriedades": [], "segredos": [], "endpoints": [],
              "testes": "-", "dependencias": []}
    secoes = gerar_secoes(c, dados)
    assert "2.0.0" in secoes["Versoes"]
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_wiki_componente.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.modelo_wiki'`

- [ ] **Step 3: Implementar `scripts/modelo_wiki.py`**

`ORDEM = ["Visao-geral", "Build", "Configuracao", "Deploy", "Operacao", "API", "Testes", "Versoes"]`.

`gerar_secoes(c, dados) -> dict[str, str]` devolve as oito seções em português, cada uma com o conteúdo do tipo:
- **Visão geral**: a descrição do manifesto, o artefato e a versão, quem usa, de quem depende.
- **Build**: pré-requisitos (JDK 25 e Maven 3.9, ou Node 24 e npm 11), o comando, o que sai, o comando de publicação e a regra de versão.
- **Configuração**: tabela de propriedades, tabela de segredos pelo nome, recursos JNDI e endereços dos webservices.
- **Deploy**: onde roda, o contexto e a porta, a ordem em relação aos outros componentes, a tabela de conferência depois de subir, e o retorno de versão.
- **Operação**: onde ficam os logs, tabela de erros conhecidos com o que significam e o que fazer.
- **API**: tabela de endpoints com método, caminho e resposta, ou a lista de exportações, no caso do pacote de telas.
- **Testes**: como rodar, o que cobrem, onde ficam as respostas de referência.
- **Versões**: a versão atual e o que mudou nela.

- [ ] **Step 4: Implementar `scripts/wiki_componente.py`**

- `extrair_dados(pasta_repo: Path, c: dict) -> dict`: lê o `pom.xml` ou o `package.json` para versão e artefato; o `application.properties` ou `application.yml` para contexto, porta e propriedades; os controllers para os endpoints; o diretório de testes para o número de testes.
- `escrever_secoes(pasta_repo: Path, c: dict, dados: dict) -> None`: grava `docs/wiki/<secao>.md` e o `docs/wiki/.order`.
- `criar_wiki_codigo(org, projeto, repo, branch) -> str`: chama `az devops wiki create --type codewiki --mapped-path /docs/wiki` e devolve o identificador.
- `publicar_projeto(raiz_wiki, repo, texto, token) -> str`: `PUT` em `/_apis/wiki/wikis/<wiki>/pages?path=<raiz>/Componentes/<repo>`, com `If-Match` quando a página já existe, e o aviso de fonte no topo do texto.
- `main(argv) -> int`: para cada componente do manifesto, gera as seções, cria a Wiki de código e publica a cópia na Wiki do projeto. Com `--dry-run`, escreve só o texto e mostra o que publicaria.

- [ ] **Step 5: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_wiki_componente.py -v`
Expected: 2 PASS

- [ ] **Step 6: Ensaiar sobre a divisão real**

Rodar `python scripts/wiki_componente.py --manifesto manifesto_exemplo.json --dry-run` apontando para os clones dos nove repositórios.
Expected: para cada um, oito arquivos de texto com o contexto, a porta, a versão e os endpoints lidos do código, e a lista do que publicaria.

- [ ] **Step 7: Commitar**

```bash
git add scripts/modelo_wiki.py scripts/wiki_componente.py tests/test_wiki_componente.py
git commit -m "feat: gera a Wiki de codigo de cada componente e publica na Wiki do projeto"
```

---

### Task 5: publicar_feed.py

**Files:**
- Create: `scripts/publicar_feed.py`
- Create: `tests/test_publicar_feed.py`

**Interfaces:**
- Consumes: `scripts.manifesto.carregar`, `scripts.manifesto.ordem_publicacao`.
- Produces: `publicar_feed.versao_publicada(feed: str, artefato: str, versao: str, token: str) -> bool`, que diz se a versão já está no feed. `publicar_feed.comandos_publicar(c: dict, feed_url: str) -> list[list[str]]`, que devolve os comandos de publicação, sem executar. `publicar_feed.main(argv) -> int`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_publicar_feed.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.manifesto import carregar, ordem_publicacao
from scripts.publicar_feed import comandos_publicar

EXEMPLO = pathlib.Path(__file__).resolve().parents[1] / "manifesto_exemplo.json"

def test_ordem_respeita_dependencias():
    m = carregar(str(EXEMPLO))
    ordem = ordem_publicacao(m)
    assert ordem.index("ITSecurityService") < ordem.index("ERPConsultaWeb")
    assert ordem.index("erp-frontend-shared") < ordem.index("ERPConsultaWeb")

def test_comandos_maven_usa_o_pom_e_o_feed():
    c = carregar(str(EXEMPLO))["componentes"][4]
    cmds = comandos_publicar(c, "https://exemplo/feed/v1")
    texto = " ".join(" ".join(x) for x in cmds)
    assert "deploy" in texto
    assert "https://exemplo/feed/v1" in texto

def test_comandos_npm_usa_publish():
    c = carregar(str(EXEMPLO))["componentes"][3]
    cmds = comandos_publicar(c, "https://exemplo/registry/")
    texto = " ".join(" ".join(x) for x in cmds)
    assert "publish" in texto
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_publicar_feed.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.publicar_feed'`

- [ ] **Step 3: Implementar `scripts/publicar_feed.py`**

- `versao_publicada(feed, artefato, versao, token) -> bool`: `GET` em `https://pkgs.dev.azure.com/<org>/<projeto>/_apis/packaging/feeds/<feed>/packages`, procurando o artefato e a versão. O host é `pkgs.dev.azure.com`, não `dev.azure.com`.
- `comandos_publicar(c, feed_url) -> list[list[str]]`: para `maven-*`, `mvn -B deploy -s <settings> -Dmaven.repo.local=<repo>`; para `npm-pkg`, `npm publish --registry <feed_url>`.
- `main(argv) -> int`: lê o manifesto, percorre `ordem_publicacao`, e para cada componente confere se a versão já existe. Se já existir, avisa que a versão é imutável e sugere a próxima, e não publica. A credencial vem do token AAD, em memória: variável de ambiente para o Maven e arquivo de usuário temporário para o npm, apagado no fim. Com `--dry-run`, mostra a ordem e o que publicaria, sem escrever.

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_publicar_feed.py -v`
Expected: 3 PASS

- [ ] **Step 5: Ensaiar em dry-run contra o feed real**

Run: `python scripts/publicar_feed.py --manifesto manifesto_exemplo.json --dry-run`
Expected: a ordem sai com `erp-frontend-shared` e as bibliotecas antes dos gateways, e cada linha diz que a versão já está no feed ou o que publicaria.

- [ ] **Step 6: Commitar**

```bash
git add scripts/publicar_feed.py tests/test_publicar_feed.py
git commit -m "feat: publica as versoes no feed na ordem das dependencias"
```

---

### Task 6: O SKILL.md e as referências

**Files:**
- Create: `SKILL.md`
- Create: `references/armadilhas.md`
- Create: `references/wiki-componente.md`
- Create: `references/publicacao-feed.md`

**Interfaces:**
- Consumes: as seis fases e os nomes dos quatro scripts, definidos nas tarefas 1 a 5.
- Produces: o ponto de entrada da skill, para o agente que a carrega.

- [ ] **Step 1: Escrever o `SKILL.md`**

Frontmatter:

```yaml
---
name: monorepo-para-repositorios
description: Use ao transformar um monorepo em vários repositórios prontos para o DevOps, um por componente: separar com histórico preservado, limpar rastro de IA, padronizar a Wiki de código de cada repositório, montar a Wiki de Arquitetura e Deploy na Wiki do projeto e publicar as versões no feed de pacotes do Azure Artifacts. Acionar quando o usuário mencionar dividir monorepo, um repositório por serviço, repositório por componente, Wiki de código, publicar no feed, mfg-java, ou organizar repositórios para o time de DevOps.
---
```

Corpo, em português: quando usar e quando não usar; as seis fases e o portão entre elas (nada de passar de uma fase sem conferir a anterior); a tabela dos quatro scripts com o que cada um faz e o que ele devolve; o manifesto como fonte única, com um exemplo curto; a nota de que a skill não varre a si mesma, e por quê; e o aviso de que reescrever histórico exige aviso a quem já clonou.

- [ ] **Step 2: Escrever `references/armadilhas.md`**

A tabela do item 8 da spec, com o sintoma, a causa e o contorno de cada armadilha, mais uma seção "armadilhas do Windows" com o `\r` nos nomes, o `mktree` do PowerShell e o `ENOSPC`.

- [ ] **Step 3: Escrever `references/wiki-componente.md`**

O conteúdo de cada uma das oito seções, com o que o DevOps precisa encontrar em cada uma, e o formato do aviso de fonte que vai no topo da cópia na Wiki do projeto.

- [ ] **Step 4: Escrever `references/publicacao-feed.md`**

A ordem de publicação e por que ela vem do `dependeDe`, a imutabilidade das versões e o que fazer quando a versão já saiu, a conferência do que foi publicado, e o Erro 409 na íntegra.

- [ ] **Step 5: Conferir que a skill não se acusa sozinha**

Run: `python scripts/varrer.py . --historico` na raiz da skill.
Expected: o `varrer.py` acusa a própria skill, porque ela contém as expressões que a busca procura. Isso é o comportamento documentado e esperado: a skill não entra no próprio escopo. Registrar esse resultado na seção "Como a skill é verificada" do `README.md`, para não passar por defeito depois.

- [ ] **Step 6: Commitar**

```bash
git add SKILL.md references/
git commit -m "docs: roteiro da skill e referencias de armadilhas, Wiki e publicacao"
```

---

### Task 7: Publicação no GitHub e instalação local

**Files:**
- Modify: `README.md` (seção de instalação, com o caminho do repositório)
- Create: `~/.config/opencode/skills/monorepo-para-repositorios/` (cópia)

**Interfaces:**
- Consumes: tudo das tarefas 1 a 6.
- Produces: a skill no GitHub e instalada na máquina.

- [ ] **Step 1: Rodar a suíte inteira**

Run: `python -m pytest -v`
Expected: todos os testes PASS

- [ ] **Step 2: Conferir a estrutura**

Run: `python -c "import pathlib; p=pathlib.Path('.'); print(sorted(str(x) for x in p.rglob('*') if x.is_file() and '.git' not in x.parts))"`
Expected: os quatro scripts, o manifesto de exemplo, o `SKILL.md`, as três referências, o `README.md`, o `pyproject.toml` e os quatro arquivos de teste.

- [ ] **Step 3: Criar o repositório e subir**

```bash
git init -b main
git remote add origin https://github.com/AndresLosada21/monorepo-para-repositorios.git
git push -u origin main
```

- [ ] **Step 4: Instalar localmente**

Copiar a pasta para `~/.config/opencode/skills/monorepo-para-repositorios`, sem o `.git` nem o `__pycache__`.

- [ ] **Step 5: Conferir a instalação**

Run: `python ~/.config/opencode/skills/monorepo-para-repositorios/scripts/varrer.py <pasta-qualquer> --historico`
Expected: o script roda da pasta instalada.

- [ ] **Step 6: Commitar o ajuste do README**

```bash
git add README.md
git commit -m "docs: caminho de instalacao e repositorio de origem"
git push
```
