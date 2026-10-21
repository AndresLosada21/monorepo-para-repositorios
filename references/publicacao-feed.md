# Publicação no feed

O feed de pacotes é o Azure Artifacts, no projeto da organização. A artefato publicado é o que
os outros sistemas consomem; o repositório é onde o código vive.

## A ordem vem do grafo

A ordem de publicação sai de `dependeDe` no manifesto, não de uma lista escrita à mão. O
`scripts/publicar_feed.py` calcula a ordem e imprime:

```text
ordem de publicacao: erp-frontend-shared -> ITSecurityService -> SearchitService -> SearchitGateway -> ERPConsultaWeb
```

A ordem importa porque o serviço que consome uma biblioteca precisa que ela já esteja no feed:
o build dele baixa por versão, e se a versão não estiver lá, o build quebra.

## Versão publicada é imutável

O feed não aceita sobrescrever. Tentar de novo devolve:

```text
409 Conflict - The feed 'mfg-java' already contains file 'itSecurityService-2.0.0.pom'
in package 'br.com.yamaha:itSecurityService:2.0.0'
```

Por isso o script confere antes de publicar. Se a versão já existe, ele avisa que a próxima é a
saída e não tenta contornar. Contornar exigiria apagar a versão do feed, o que o feed não
permite de forma limpa.

Quando a versão nova sai porque a anterior foi publicada com uma dependência errada, a
correção é subir a próxima. É o preço de publicar cedo demais: **a versão que sai, sai.**

## Conferir o que já está no feed

A API de pacotes fica em `feeds.dev.azure.com`:

```text
GET https://feeds.dev.azure.com/<org>/<projeto>/_apis/Packaging/Feeds/<feed>/Packages?api-version=7.1
```

O host `pkgs.dev.azure.com` serve o artefato para download, mas nao responde a essa consulta:
devolve `404`. Já o token é o mesmo do Azure DevOps, o que sai de
`az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798`.

## A credencial fica só em memória

| Passo | Onde a credencial vai |
|---|---|
| Maven | variável de ambiente `MAVEN_FEED_USER` e `MAVEN_FEED_TOKEN`, lidas por um `settings.xml` temporário |
| npm | arquivo de usuário do npm temporário, apontado por `NPM_CONFIG_USERCONFIG` |
| Git | cabeçalho `http.extraHeader` no comando do git |

O `settings.xml` e o `.npmrc` temporários são apagados no fim. Nada disso entra no
repositório, e nada disso entra no histórico.

## O que o script faz, na ordem

1. Calcula a ordem a partir de `dependeDe`.
2. Consulta o feed e marca o que já está publicado.
3. Para cada componente, na ordem:
   - se a versão já existe, pula e avisa;
   - se falta, gera o `settings.xml` ou o `.npmrc` temporário;
   - publica;
   - apaga o arquivo temporário.

Com `--dry-run`, o passo 2 acontece e o passo 3 não: o operador vê a ordem e o que já está no
feed antes de escrever qualquer coisa.

## Depois de publicar

- A Wiki do componente passa a citar a versão publicada, e a cópia na Wiki do projeto é
  regerada.
- A página Arquitetura e Deploy da Wiki do projeto passa a listar as versões no feed.
- A branch do repositório recebe a tag da versão, seguindo a convenção do projeto.

## O que costuma dar errado

| Sintoma | Causa | Contorno |
|---|---|---|
| `401` na publicação | token expirado ou de outro recurso | `az login` e refazer o token |
| `409` | a versão já foi publicada | subir a próxima versão |
| `400` com o nome do pacote | o `package.json` ainda está `private`, ou falta o `publishConfig` | rodar o `separar.py`, que corrige os dois |
| O build do consumidor não acha a biblioteca | a versão não está no feed, ou o `pom.xml` do consumidor ainda aponta para `SNAPSHOT` | conferir a ordem e a versão no `pom.xml` |
