# Skill "monorepo-para-repositorios" — desenho

Data: 21/10/2026 · Situação: aprovado pelo responsável (escopo: ciclo completo, com scripts; destino: repositório no GitHub, instalado também em `~/.config/opencode/skills/`)

## 1. Objetivo

Transformar um monorepo em N repositórios prontos para o time de DevOps consumir: um repositório por componente, com histórico preservado, sem rastro de IA, com Wiki de código padronizada e com as versões publicadas no feed de pacotes.

O caso que motivou a skill foi a divisão da família ERPConsulta (8 componentes Java + 1 pacote de telas) em nove repositórios do projeto "Digital Solution MFG Run", com Wiki de código em cada um, Wiki de Arquitetura e Deploy no projeto e publicação das versões 2.0.0 no feed `mfg-java`.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Escopo | Ciclo completo: separar, limpar, documentar, publicar |
| Destino | Repositório `AndresLosada21/monorepo-para-repositorios` no GitHub, com a skill também instalada em `~/.config/opencode/skills/` |
| Automação | Scripts que fazem o trabalho; o `SKILL.md` diz quando e como rodar cada um |
| Autoverificação | A skill não varre a si mesma; isso fica escrito no `SKILL.md` e no `references/armadilhas.md` |
| Idioma | Português do Brasil, com os termos de ferramenta em inglês (Git, Azure DevOps, Maven, npm) |
| Público | O time de DevOps da Yamaha, não só o autor |

## 3. Estrutura

```
monorepo-para-repositorios/
├── SKILL.md                      o roteiro: quando usar, as seis fases, os portões
├── README.md                     o que é, como instalar, visão geral
├── manifesto_exemplo.json        exemplo completo, com os doze casos resolvidos
├── scripts/
│   ├── varrer.py                 varre árvore, histórico, autores e mensagens
│   ├── separar.py                separa o monorepo em repositórios, com histórico
│   ├── wiki_componente.py         gera as oito seções e publica a Wiki de código
│   └── publicar_feed.py          publica Maven e npm no feed, na ordem do dependeDe
└── references/
    ├── armadilhas.md             o que dá errado e como contornar
    ├── wiki-componente.md        as oito seções e o que o DevOps precisa em cada uma
    └── publicacao-feed.md        ordem, imutabilidade, o que fazer quando a versão já saiu
```

## 4. O manifesto

Fonte única do que fazer. Todo script lê o manifesto; nenhum script carrega o caso do ERP Consulta.

```json
{
  "projeto": "Digital Solution MFG Run",
  "org": "yamahaind",
  "feed": "mfg-java",
  "monorepo": {
    "url": "https://dev.azure.com/yamahaind/Digital Solution MFG Run/_git/ERPConsulta",
    "branch": "main"
  },
  "wiki": {
    "raiz": "/Java/ERP Consulta",
    "paginaArquitetura": "Arquitetura e Deploy"
  },
  "componentes": [
    {
      "repo": "neway-lib",
      "caminho": "libs/neway-lib",
      "artefato": "br.com.neway:neway-lib",
      "tipo": "maven-lib",
      "versao": "1.0.0",
      "publica": false,
      "dependeDe": [],
      "descricao": "Biblioteca base dos sistemas Java da casa."
    }
  ]
}
```

Campos por componente:

| Campo | Para que serve |
|---|---|
| `repo` | Nome do repositório no Azure DevOps |
| `caminho` | Pasta de origem dentro do monorepo |
| `artefato` | GAV (Maven) ou nome do pacote (npm) |
| `tipo` | `maven-lib`, `maven-war`, `maven-jar` ou `npm-pkg` |
| `versao` | Versão a declarar no `pom.xml` ou `package.json` |
| `publica` | Se o componente vai para o feed |
| `dependeDe` | Outros componentes de que este depende; define a ordem de build e de publicação |
| `descricao` | Uma frase, usada na Wiki de código |

`dependeDe` é o que substitui o conhecimento que estava na minha cabeça: a ordem de publicação no feed e a ordem de build na prova saem do grafo.

## 5. Fases

Cada fase é um comando separado, com `--dry-run` e saída do que faria. Nada de "executar tudo de uma vez". A fase seguinte só roda depois que a anterior foi conferida.

### Fase 1 — Diagnóstico (só leitura)

Responde: o que existe no monorepo, quais componentes já têm repositório, o que já está publicado no feed, e quem depende de quem. Não escreve nada.

### Fase 2 — Separação (escrita)

Para cada componente: clona o monorepo, reescreve o histórico com `git filter-repo` (renomeando a pasta para a raiz, trocando o autor e substituindo o texto), declara a versão e o feed no `pom.xml` ou `package.json`, cria o repositório, sobe a branch e abre o pull request.

Depois confere a **branch padrão** de cada repositório: precisa ser a branch com o código novo. O caso do `neway-lib` mostrou o que acontece quando não se confere — a branch padrão ficou com o código antigo e quem clonou recebia a versão errada.

Quando a branch padrão precisa ser trocada e não há permissão de *force push*, a fase usa um commit de merge que junta o histórico antigo como segundo pai. Assim o push é normal e nada se perde.

### Fase 3 — Prova (só leitura)

Cada repositório é clonado do zero, com o repositório Maven local vazio, e compila e passa nos testes baixando as dependências internas pelo feed. Para npm, o `npm ci` contra o feed. É a mesma prova que o DevOps vai fazer.

### Fase 4 — Documentação (escrita)

Para cada componente: gera as oito seções da Wiki de código na pasta `docs/wiki` do repositório, cria a Wiki de código no Azure (mapeada para `/docs/wiki`) e publica na Wiki do projeto uma cópia com o aviso de fonte.

### Fase 5 — Publicação (escrita)

Publica Maven e npm no feed na ordem do `dependeDe`. Registra o que foi publicado, com data e versão.

### Fase 6 — Limpeza de rastro (escrita, quando pedida)

Roda o `varrer.py` em todos os repositórios e, se houver achado, reescreve o histórico: autor pelo responsável, substituição do texto em todos os commits, remoção de pastas e de arquivos que não devem ficar.

## 6. As oito seções da Wiki de código

Estrutura idêntica em todos os repositórios, para o DevOps achar a mesma coisa no mesmo lugar.

1. **Visão geral** — o que é, quem usa, de quem depende, de quem é dependido.
2. **Build** — pré-requisitos, comando exato, o que sai, como publicar, como mudar a versão.
3. **Configuração** — propriedades, variáveis de ambiente, JNDI, segredos pelo nome.
4. **Deploy** — onde roda, contexto, porta, ordem, conferência depois de subir.
5. **Operação** — logs, erros conhecidos e o que significam, como voltar à versão anterior.
6. **API** — o que o componente oferece, com exemplo.
7. **Testes** — como rodar, o que cobrem, onde ficam as respostas de referência.
8. **Versões** — o que mudou em cada versão.

O `references/wiki-componente.md` traz o conteúdo de cada seção e a lista do que o DevOps precisa encontrar em cada uma.

## 7. Scripts

### `varrer.py`

Varre, no repositório indicado:
- a árvore atual (caminho e conteúdo);
- o histórico inteiro (todas as versões de cada arquivo);
- os autores e committers de cada commit;
- as mensagens de commit.

Sai com código 1 se encontrar rastro. Aceita uma lista de exceções por arquivo, para o caso de um repositório que legitimamente fale de "IA" no texto de negócio.

**Não varre a si mesmo.** O `SKILL.md` diz isso e o `references/armadilhas.md` registra o motivo: a skill contém, por natureza, as expressões que a busca procura.

### `separar.py`

Lê o manifesto. Para cada componente:
- clona o monorepo;
- roda `git filter-repo` com `--path-rename` (a pasta vira a raiz), `--mailmap` (autor pelo responsável) e `--replace-text` (limpeza de texto);
- declara a versão e o feed no `pom.xml` ou `package.json`;
- cria o repositório, se não existir;
- sobe a branch e abre o pull request;
- confere a branch padrão e, se precisar, faz o commit de merge.

Tem `--somente-separar`, `--sem-publicar` e `--dry-run`.

### `wiki_componente.py`

Lê o manifesto. Para cada componente:
- gera as oito seções em `docs/wiki`, a partir do que está no código (contexto e porta do `application.properties`, propriedades, endpoints dos controllers, versão do `pom.xml`);
- cria a Wiki de código no Azure, mapeada para `/docs/wiki`;
- publica na Wiki do projeto a cópia, com o aviso de fonte no topo;
- mantém a ordem das páginas.

### `publicar_feed.py`

Lê o manifesto. Publica Maven e npm no feed, na ordem do `dependeDe`, com a credencial só em memória. Antes de publicar, confere se a versão já existe, porque no feed não há como sobrescrever.

## 8. Referências

### `references/armadilhas.md`

O que deu errado durante a divisão real, e o contorno:

| Armadilha | Contorno |
|---|---|
| `core.autocrlf` ligado faz o nome de arquivo ganhar `\r` e a árvore ficar corrompida | `core.autocrlf=false` em toda operação de histórico |
| `git filter-branch` não reescreve as tags sem `--tag-name-filter cat` | sempre com a opção |
| `git filter-repo` não aceita regex multilinha no `--replace-text` | segunda passada com `--tree-filter` |
| `mktree` alimentado pelo PowerShell grava `\r` nos nomes | `read-tree` + `update-index --cacheinfo` |
| `git push --mirror` não combina com refspec | espelho para publicar tudo, ou refspec para um branch |
| `az devops invoke` ignora o corpo em PATCH e PUT | `urllib` com token AAD |
| A API de pacotes fica em `feeds.dev.azure.com`, não em `dev.azure.com` | usar o host certo |
| `az repos pr show` não aceita `--project` nem `--repository` | `az repos pr list` com os filtros |
| Versão publicada no feed é imutável | conferir antes; se já saiu, subir a próxima |
| `DeleteRepository` só o administrador de projeto tem | pedir a alguém do grupo, ou pedir a desativação |
| Token AAD é o do recurso `499b84ac-1321-427f-aa17-267ca6975798` | `http.extraHeader` no Git, variável de ambiente no Maven e no npm |
| Task do Azure Boards não aceita criação já em `Closed` | criar em `New` e promover |
| `npm ci` falha com `ENOSPC` em disco cheio | conferir espaço antes da prova |

### `references/wiki-componente.md`

O conteúdo de cada uma das oito seções e a lista do que o DevOps precisa encontrar em cada uma.

### `references/publicacao-feed.md`

A ordem de publicação, a imutabilidade das versões, o que fazer quando a versão já saiu e como conferir o que foi publicado.

## 9. O que fica fora

- Implementação dos componentes, o conteúdo do ERP Consulta e as textos das Wikis: são do caso, não da ferramenta.
- Pipelines, deploy, GitOps e orquestração: são do DevOps.
- A criação dos work items no Azure Boards: já é coberta pela skill `yamaha-azure-devops-cli`.

## 10. Como a skill é verificada

- Cada script roda em `--dry-run` sobre o caso do ERP Consulta e produz a lista do que faria.
- O `varrer.py` roda nos nove repositórios da divisão real e não acusa nenhum deles.
- O `separar.py` roda em um monorepo de teste, com três componentes, e produz três repositórios com histórico preservado e branch padrão correta.
- O `wiki_componente.py` roda sobre a divisão real e reproduz as oito seções já publicadas.
- O `publicar_feed.py` roda em `--dry-run` e mostra a ordem que usaria.

## 11. Riscos

| Risco | Tratamento |
|---|---|
| Reescrita de histórico em repositório já clonado por outra pessoa | Todo push que reescreve histórico avisa no comentário e na Wiki: `git fetch` e `git reset --hard` |
| Publicar versão errada no feed | `publicar_feed.py` confere a versão antes de publicar e a ordem vem do `dependeDe` |
| A branch padrão ficar com o código antigo | A fase de separação confere a branch padrão de cada repositório e corrige |
| A skill perder utilidade por acoplar no caso do ERP Consulta | Nada de caso no código: o ERP Consulta aparece só no manifesto de exemplo |
| O `varrer.py` acusar a si mesmo ou acusar texto de negócio legítimo | Lista de exceções por arquivo; a skill não entra no próprio escopo |
