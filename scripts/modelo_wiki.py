"""Gera as oito secoes da Wiki de codigo de um componente.

A estrutura e a mesma em todos os repositorios, para o DevOps achar a mesma coisa no mesmo lugar.
O conteudo sai do codigo: versao e artefato do pom ou do package.json, contexto e porta do
application.properties, propriedades e segredos, endpoints dos controllers e numero de testes.
"""

ORDEM = ["Visao-geral", "Build", "Configuracao", "Deploy", "Operacao", "API", "Testes", "Versoes"]

TITULOS = {
    "Visao-geral": "Visão geral",
    "Build": "Build",
    "Configuracao": "Configuração",
    "Deploy": "Deploy",
    "Operacao": "Operação",
    "API": "API",
    "Testes": "Testes",
    "Versoes": "Versões",
}


def _tabela(cabecalho: str, linhas: list) -> str:
    if not linhas:
        return ""
    saida = [f"| {cabecalho} |", "|---|---|"]
    for linha in linhas:
        saida.append("| " + " | ".join(str(x) for x in linha) + " |")
    return "\n".join(saida) + "\n"


def _visao(c: dict, d: dict) -> str:
    tipo = {"maven-lib": "biblioteca Java (jar)", "maven-war": "aplicação web (war) para Tomcat 11",
            "maven-jar": "aplicação Spring Boot executável (jar)", "npm-pkg": "pacote npm"}[d["tipo"]]
    linhas = [
        ["Artefato", f"`{d['artefato']}` versão `{d['versao']}`"],
        ["Tipo", tipo],
        ["Quem usa", c.get("descricao", "")],
    ]
    if d.get("dependencias"):
        linhas.append(["Depende de", ", ".join(d["dependencias"])])
    return f"""# {TITULOS['Visao-geral']}

{c.get('descricao', '')}

{_tabela("", linhas)}
A visão do conjunto, a ordem de deploy e o que o time precisa provisionar estão na
[Arquitetura e Deploy](https://dev.azure.com/yamahaind/Digital%20Solution%20MFG%20Run/_wiki/wikis/Digital-Solution-MFG-Run?pagePath=/java/ERP%20Consulta/Arquitetura-e-Deploy).

## Nesta Wiki

1. [Build](Build.md): como gerar e publicar o pacote.
2. [Configuração](Configuracao.md): propriedades, segredos e dependências de ambiente.
3. [Deploy](Deploy.md): onde roda, ordem e conferência.
4. [Operação](Operacao.md): logs, erros conhecidos e retorno de versão.
5. [API](API.md): o que o componente oferece.
6. [Testes](Testes.md): como rodar e o que cobrem.
7. [Versões](Versoes.md): o que mudou em cada versão.
"""


def _build(c: dict, d: dict) -> str:
    if d["tipo"] == "npm-pkg":
        return f"""# {TITULOS['Build']}

## Pré-requisitos

- Node 24 e npm 11.
- Leitura no feed de pacotes do time.

## Comandos

```text
npm ci
npm test
npm run typecheck
```

## O que sai

`{d['arquivo']}`, publicado no feed com o comando `npm publish`.

## Versão

A versão fica no `package.json`. Para mudar, edite o campo `version` e publique.
Versão publicada é imutável: para corrigir, suba a próxima.

## Publicação

```text
npm publish
```

O destino vem do `publishConfig` do `package.json`. A credencial fica no `.npmrc` do usuário
ou no pipeline, nunca no repositório.
"""
    return f"""# {TITULOS['Build']}

## Pré-requisitos

- JDK 25 e Maven 3.9 ou mais novo.
- Leitura no feed de pacotes do time, para as bibliotecas internas.

## Comandos

```text
mvn -B verify
```

## O que sai

`{d['arquivo']}`, em `target/`. O `verify` roda todos os testes; não use `-DskipTests` para
gerar um pacote que vai para algum ambiente.

## Publicação

```text
mvn -B deploy
```

O destino vem do `distributionManagement` do `pom.xml`, que aponta para o feed do time. A
credencial vem do `settings.xml` do usuário ou do pipeline, nunca do repositório. Versão
publicada é imutável: para corrigir, suba a próxima.

## Versão

```text
mvn versions:set -DnewVersion=<nova>
```

Muda contrato de quem usa: versão maior. Acrescenta sem quebrar: versão menor. Só corrige:
último número.
"""


def _configuracao(c: dict, d: dict) -> str:
    partes = [f"# {TITULOS['Configuracao']}", ""]
    if d.get("propriedades"):
        partes.append("## Propriedades")
        partes.append("")
        partes.append(_tabela("Propriedade | Valor no pacote | Precisa definir por ambiente? | Para que serve",
                               d["propriedades"]))
    else:
        partes.append("## Propriedades\n\nSem propriedades próprias em execução.")
        partes.append("")
    if d.get("segredos"):
        partes.append("## Segredos")
        partes.append("")
        partes.append("Defina como variável de ambiente do processo, nunca em arquivo:")
        partes.append("")
        partes.append(_tabela("Variável | O que é", d["segredos"]))
    else:
        partes.append("## Segredos\n\nNão usa segredo próprio.")
        partes.append("")
    if d["tipo"] in ("maven-war", "maven-jar"):
        partes.append("## Webservices do SGA e do SGC\n")
        partes.append("Vêm do `middleware`. Se o ambiente não usar os endereços padrão, informe por\n"
                     "propriedade da JVM no Tomcat (`-Dmiddleware.ws.acess-url=...`,\n"
                     "`-Dmiddleware.ws.connection-url=...`). A tabela completa está na Wiki do `Middleware`.")
        partes.append("")
    return "\n".join(partes)


def _deploy(c: dict, d: dict) -> str:
    if d["tipo"] == "npm-pkg":
        return f"""# {TITULOS['Deploy']}

Pacote de tela: não é implantado sozinho. Entra no bundle do ERP Consulta e do Searchit Admin
no momento do build deles.

Publique a versão nova no feed **antes** de gerar os pacotes que a consomem.
"""
    partes = [f"# {TITULOS['Deploy']}", ""]
    if d["tipo"] == "maven-war":
        partes += [
            "## Onde roda",
            "",
            f"- **{d.get('ambiente', 'Tomcat 11')}** com **JDK 25**.",
            f"- Contexto `{d['contexto']}`: o arquivo `target/{d['arquivo']}` vai para `webapps/` com o nome "
            f"**`{d['contexto'].strip('/')}.war`**. O nome do arquivo define o contexto no Tomcat.",
            f"- Porta do servidor: `{d.get('porta', '')}`.",
            "",
        ]
    else:
        partes += [
            "## Onde roda",
            "",
            f"- Processo próprio com **JDK 25**: `java -jar {d['arquivo']}`.",
            f"- Porta `{d.get('porta', '')}`, contexto `{d.get('contexto', '')}`.",
            "",
        ]
    partes += ["## Antes de implantar", ""]
    if d.get("dependencias"):
        partes.append(f"- As dependências já publicadas no feed: {', '.join(d['dependencias'])}.")
    partes.append("- Os segredos da página Configuração definidos no ambiente.")
    partes.append("- A ordem entre componentes está na [Arquitetura e Deploy](https://dev.azure.com/yamahaind/Digital%20Solution%20MFG%20Run/_wiki/wikis/Digital-Solution-MFG-Run?pagePath=/java/ERP%20Consulta/Arquitetura-e-Deploy).")
    partes += ["", "## Conferência depois de implantar", ""]
    if d.get("endpoints"):
        partes.append(_tabela("Método | Endereço | O que deve responder", d["endpoints"]))
    else:
        partes.append("Confira a página de API: cada recurso listado precisa responder.")
    partes += [
        "",
        "## Voltar à versão anterior",
        "",
        "Implante de novo o pacote da versão anterior, que o feed guarda. Se a versão nova "
        "trouxe segredo ou propriedade novos, eles podem ficar: a versão anterior os ignora.",
        "",
    ]
    return "\n".join(partes)


def _operacao(c: dict, d: dict) -> str:
    log = ("`logs/catalina.<data>.log` e `logs/localhost.<data>.log` do Tomcat"
           if d["tipo"] == "maven-war" else "a saída padrão do processo")
    return f"""# {TITULOS['Operacao']}

## Logs

{log}. O nível do pacote `br.com.yamaha` está em `DEBUG`; em produção, pode ser reduzido sem
recompilar com `-Dlogging.level.br.com.yamaha=INFO`.

## Erros conhecidos

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| O serviço não sobe, e o log fala do segredo | Variável de segredo ausente ou curta | definir a variável e reiniciar |
| Toda chamada responde 401 | chaves diferentes entre os serviços que validam a credencial | usar o mesmo valor nos dois |
| 403 para um usuário que deveria entrar | usuário sem perfil no sistema no SGA | conceder o perfil no SGA |
| A consulta falha com erro de conexão | cadastro da conexão no SGC do ambiente | conferir o SGC; o pacote não guarda endereço de banco |
| Tela em branco | pacote gerado com `-Dskip.frontend=true` | gerar de novo sem essa opção |
"""


def _api(c: dict, d: dict) -> str:
    if d["tipo"] == "npm-pkg":
        return f"""# {TITULOS['API']}

Tudo sai de `{d['artefato']}`:

| Exportação | Para que serve |
|---|---|
| `createHttpClient`, `userMessage` | chamadas com credencial e tradução de erro |
| `createSessionStore` | sessão com renovação automática |
| `AppShell`, `LoginPage` | moldura da aplicação e tela de entrada |
| `ResultTable`, `buildTotalsRow` | grade com filtros, ordenação e totais |
| `buildCsv`, `downloadCsv` | exportação CSV |
| `createI18n`, `messages` | textos em pt-BR e inglês |
| `THEMES`, `useErpTheme`, `ThemePicker` | temas |

Estilos: `@use '@erp/shared/styles/shell';` no SCSS da aplicação, depois do `@carbon/react`.
"""
    if d.get("endpoints"):
        linhas = "\n".join("| {} | `{}` | {} |".format(m, rota, o_que)
                           for m, rota, o_que in d["endpoints"])
        return ("# " + TITULOS["API"] + "\n\n"
                "| Método | Caminho | O que faz |\n|---|---|---|\n" + linhas + "\n")
    return f"""# {TITULOS['API']}

Este componente não expõe endpoint. O que ele oferece:

| Tipo | O que |
|---|---|
| Artefato | `{d['artefato']}` |
| Contexto | `{d.get('contexto', '')}` |
"""


def _testes(c: dict, d: dict) -> str:
    if d["tipo"] == "npm-pkg":
        comando = "npm test"
    else:
        comando = "mvn -B verify"
    return f"""# {TITULOS['Testes']}

{d.get('testes', 'Testes a definir.')}

```text
{comando}
```

As respostas de referência dos testes ficam em `src/test/resources/contratos`, dentro do
próprio repositório, para que o teste não dependa de outro caminho.
"""


def _versoes(c: dict, d: dict) -> str:
    return f"""# {TITULOS['Versoes']}

| Versão | O que mudou |
|---|---|
| {d['versao']} | Versão atual, publicada no feed do time. |
"""


def gerar_secoes(c: dict, d: dict) -> dict:
    """As oito secoes, na ordem, a partir do manifesto e dos dados lidos do codigo."""
    secoes = {
        "Visao-geral": _visao(c, d),
        "Build": _build(c, d),
        "Configuracao": _configuracao(c, d),
        "Deploy": _deploy(c, d),
        "Operacao": _operacao(c, d),
        "API": _api(c, d),
        "Testes": _testes(c, d),
        "Versoes": _versoes(c, d),
    }
    return {nome: secoes[nome] for nome in ORDEM}
