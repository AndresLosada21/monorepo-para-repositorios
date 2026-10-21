---
name: monorepo-para-repositorios
description: Use ao transformar um monorepo em vários repositórios prontos para o DevOps, um por componente: separar com histórico preservado, limpar rastro de IA, padronizar a Wiki de código de cada repositório, montar a Wiki de Arquitetura e Deploy na Wiki do projeto e publicar as versões no feed de pacotes do Azure Artifacts. Acionar quando o usuário mencionar dividir monorepo, um repositório por serviço, repositório por componente, Wiki de código, publicar no feed, mfg-java, ou organizar repositórios para o time de DevOps.
---

# monorepo-para-repositorios

Use esta skill para transformar um monorepo em vários repositórios que o time de DevOps possa
consumir: um repositório por componente, com histórico preservado, sem rastro de IA, com a
documentação de build, configuração e deploy de cada um, e com as versões publicadas no feed.

## Quando usar

- Um monorepo precisa virar um repositório por serviço, por biblioteca ou por aplicação.
- O DevOps pede repositórios prontos: com build independente, documentação e versão publicada.
- Há rastro de IA em repositórios já publicados e ele precisa sair.

## Quando não usar

- O projeto já tem um repositório por componente e o que falta é pipeline ou deploy: isso é
  GitOps, do time de DevOps.
- Para escrever, revisar ou importar itens de backlog: use `yamaha-azure-devops-cli` e
  `engenharia-de-requisitos-yamaha`.
- Para mexer em tela React + Carbon: use `yamaha-carbon-ui`.

## O manifesto

Tudo vem de um manifesto JSON que descreve o que fazer. Nenhum script carrega o caso de um
projeto específico. Copie `manifesto_exemplo.json` e ajuste.

| Campo | Para que serve |
|---|---|
| `projeto`, `org`, `feed` | Onde fica, na organização e em qual feed |
| `monorepo.url`, `monorepo.branch` | De onde vem o código |
| `wiki.raiz` | Onde a Wiki do projeto recebe as cópias |
| `componentes[]` | Um por repositório: `repo`, `caminho`, `artefato`, `tipo`, `versao`, `publica`, `dependeDe`, `descricao` |

O `dependeDe` define a ordem de build e de publicação. Sai do grafo, não da cabeça de quem opera.

## As seis fases

Cada fase é um comando separado, com `--dry-run`. **Não passe de uma fase sem conferir a anterior.**

### 1. Diagnóstico (só leitura)

Responde o que existe, o que já está no feed e quem depende de quem.

```text
python scripts/manifesto.py --manifesto m.json --validar
python scripts/varrer.py <repo> --historico
```

### 2. Separação (escreve)

```text
python scripts/separar.py --manifesto m.json --destino <pasta> [--apenas <repo>] [--dry-run] [--sim]
```

Para cada componente: reescreve o histórico com `git filter-repo` (a pasta vira a raiz, o autor
passa a ser o responsável, o texto é limpo), declara a versão e o feed no `pom.xml` ou
`package.json`, cria o repositório e sobe a branch `reorganizacao/repositorio-independente`.

**Confira a branch padrão depois.** A branch padrão do repositório novo precisa ser a do código
novo. Se não der para trocar sem *force push*, o script usa commit de merge, que preserva o
histórico antigo e permite push normal.

### 3. Prova (só leitura)

Cada repositório, sozinho, com o repositório Maven local vazio:

```text
mvn -B verify -Dmaven.repo.local=<vazio> -s settings-feed.xml
```

É a mesma prova que o DevOps vai fazer. Se não compila sozinho, o componente ainda está preso
ao monorepo.

### 4. Documentação (escreve)

```text
python scripts/wiki_componente.py --manifesto m.json --repositorios <pasta> [--dry-run]
```

Gera as oito seções da Wiki de código em `docs/wiki` de cada repositório, cria a Wiki de código
no Azure e publica a cópia na Wiki do projeto, com o aviso de fonte no topo.

### 5. Publicação (escreve)

```text
python scripts/publicar_feed.py --manifesto m.json --repositorios <pasta> [--dry-run]
```

Publica na ordem do `dependeDe`. Versão publicada é imutável: o script confere antes e, se a
versão já existir, avisa que a próxima é a saída.

### 6. Limpeza de rastro (escreve, quando pedida)

```text
python scripts/varrer.py <repo> --historico
```

Se acusar, reescreva o histórico: autor pelo responsável (`git filter-repo --mailmap`), texto
substituído em todos os commits (`--replace-text`, e uma segunda passada com `--tree-filter`
quando a substituição precisar ser multilinha) e a pasta fora (`--path`). Depois rode a
varredura de novo: o que sobrou aparece.

## A skill não varre a si mesma

O `varrer.py` procura nomes de ferramenta e o vocabulário do trabalho com agente. A skill contém
essas expressões por natureza, então ela **não entra no próprio escopo**. Rodar o `varrer.py` na
raiz da skill vai acusar a própria skill: isso é o comportamento esperado e documentado, não
defeito.

## Antes de reescrever histórico

Reescrever histórico muda os identificadores dos commits. Quem já clonou precisa de
`git fetch` e `git reset --hard`. Avise no pull request e na Wiki.

## O que a skill não faz

- Não implementa os componentes: o conteúdo é do caso, não da ferramenta.
- Não cria pipeline, não faz deploy, não monta GitOps: isso é do DevOps.
- Não cria item de backlog: use `yamaha-azure-devops-cli`.

## Referências

| Documento | Quando abrir |
|---|---|
| `references/armadilhas.md` | quando algo dá errado de jeito estranho |
| `references/wiki-componente.md` | quando for ajustar o conteúdo das oito seções |
| `references/publicacao-feed.md` | quando for publicar no feed |
