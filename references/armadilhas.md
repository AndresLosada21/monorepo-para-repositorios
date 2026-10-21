# Armadilhas

O que já deu errado durante a divisão real e o contorno. Cada linha é um sintoma que o
operador encontra e o que fazer.

## Reescrita de histórico

| Sintoma | Causa | Contorno |
|---|---|---|
| Os nomes de arquivo ganha um caractere invisível no fim e a árvore não abre | `core.autocrlf` ligado converte a quebra de linha e o caractere entra no nome | `core.autocrlf=false` em **toda** operação de histórico, e um `git config` só para a máquina que faz a reescrita |
| O histórico não vem do monorepo | o remoto do `git fetch` é o repositório de destino, que está vazio | o monorepo entra como remoto separado (`monorepo`) e o destino como `origin`; o `filter-repo` roda sobre `refs/remotes/monorepo/<branch>` |
| A branch é criada, mas a pasta fica vazia | criar o ref não popula a árvore de trabalho | `git checkout` da branch nova depois de criá-la |
| A versão e o feed não chegam ao commit | faltava o `git add` e o `commit` | o script faz os dois, e a remoção dos arquivos de apoio é um commit à parte |
| A separação termina verde, sem separar nada | o código de retorno dos comandos era ignorado | todo comando é conferido, e a falha sai com código 1 |
| A branch não sobe no destino | o `push` só existia no caminho de `--dry-run` | o fluxo real faz o push, e `--sem-publicar` dispensa |
| `Cannot read mailmap` | o `filter-repo` resolve o caminho relativo ao repositório, e os arquivos de apoio estavam no diretório pai | `mailmap` e `replace-text.txt` vão **dentro** do repositório |
| Os arquivos de apoio viram rastro | o `mailmap` tem a identidade de ferramenta e o `replace-text` tem as expressões que a fase 6 procura | eles são removidos do índice depois da reescrita, em commit à parte |
| A tag antiga continua apontando para o commit antigo | o `filter-branch` não reescreve as tags sem pedir | sempre com `--tag-name-filter cat` (o `filter-repo`, que a skill usa, reescreve as tags por conta própria) |
| A substituição de texto não pega a frase inteira | o `git filter-repo` não aceita regex multilinha no `--replace-text`, e o `regex:` dele não ancora em `^` e `$` | usar `glob:` no arquivo de regras, que casa linha a linha |
| A frase de instrução continua no arquivo | o `replace-text` troca o **conteúdo**; o nome da pasta é outro assunto | para renomear a pasta, `--path-rename`, que já vem na separação |
| A árvore fica com o nome corrompido ao gravar | `git mktree` alimentado pelo PowerShell acrescenta `\r` | `git read-tree` seguido de `git update-index --cacheinfo`, que grava os bytes do arquivo |
| O `--path` não filtra a pasta do componente | o glob `pasta/**` não casa; o que funciona é o diretório | `--path <pasta>/` junto de `--path-rename <pasta>/:` |
| Depois do `filter-repo` a branch sumiu | ele reescreve a branch e a deixa só como `refs/remotes/monorepo/<branch>` | criar a branch nova a partir de lá |
| O push é recusado por não ser *fast-forward* | a branch nova não tem o histórico antigo como ancestral | commit de merge: `git commit-tree` com os dois pais, o novo e o antigo. O push passa e nada se perde |
| Quem já clonou vê o código antigo | a reescrita mudou os identificadores | avisar no pull request e na Wiki: `git fetch` e `git reset --hard` |

## Azure DevOps

| Sintoma | Causa | Contorno |
|---|---|---|
| Apagar repositório responde `TF401027` | `DeleteRepository` só o administrador de projeto tem | pedir a alguém do grupo, ou pedir a desativação do repositório em vez da exclusão |
| A listagem de pacotes do feed devolve `404` | a API de pacotes fica em `feeds.dev.azure.com`, não em `pkgs.dev.azure.com` | usar `feeds.dev.azure.com/_apis/Packaging/Feeds/<feed>/Packages` para consultar e `pkgs.dev.azure.com` para baixar |
| O `npm publish` falha com `need auth` | o `.npmrc` estava com a chave `https://host/path`; o npm procura `//host/path` | a linha do `.npmrc` começa com `//` e não com `https://` |
| `npm` ou `mvn` não são encontrados | no Windows o executável é `nome.cmd`, e o `CreateProcess` não consulta o `PATHEXT` | resolver com `shutil.which` e acrescentar `.cmd` quando o sistema é Windows |
| A cópia da Wiki do projeto não muda | a página precisa de `If-Match` com o `ETag` da versão atual | `GET` para pegar o `ETag` e `PUT` com o cabeçalho |
| `az devops invoke` ignora o corpo no `PATCH` | a extensão não envia corpo em alguns verbos | usar `urllib` com o token AAD, que é o mesmo token do `az` |
| `az repos pr show` não aceita `--project` nem `--repository` | a versão instalada não tem esses parâmetros | `az repos pr list` com os filtros |
| `az devops wiki create` falha ao recriar | já existe uma Wiki de código com esse nome | listar antes e reaproveitar |
| Task não pode ser criada já em `Closed` | o processo recusa | criar em `New` e promover depois |
| A identidade não tem permissão de leitura nos pacotes | falta `Manage permissions` no namespace | pedir ao administrador do projeto |

## Windows

| Sintoma | Causa | Contorno |
|---|---|---|
| `npm ci` falha com `ENOSPC` | disco cheio | `npm cache clean --force` e conferir o espaço antes da prova; os clones de teste ocupam muito |
| O `az` não encontra o token | a sessão expirou | `az login`, e o token do Azure DevOps sai de `az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798` |
| O `az` não encontra o feed | a extensão do Azure CLI não tem o recurso de pacote | usar a API REST com o token AAD |

## A varredura

| Sintoma | Causa | Contorno |
|---|---|---|
| Acusa `OCTOPUS`, `CURSORES`, `GEMINIANO` | dado de negócio que contém o nome de uma ferramenta | os padrões usam limite de palavra; se ainda assim acusar, use `--excecao` |
| Acusa `cursor: pointer` | CSS comum | `cursor` ficou fora do padrão |
| Acusa `skill` ou `ledger` | palavra corrente em código | ficaram fora do padrão; o teste prova que a varredura ainda acha rastro de verdade |
| Acusa `generated by the JavaTM Architecture` | código gerado por ferramenta de Java, legítimo | o padrão ignora gerador legítimo de JAXB e JAX-WS |
| Acusa `kernel, window system` | frase sobre sistema operacional | `kernel` ficou fora do padrão |
| Não acusa nada no repositório que tem rastro | o rastro está no histórico, não na árvore | rodar com `--historico` |
| A exclusão não vale | a exceção foi dada relativa ao repositório | o caminho relativo ao repositório também vale |
| A pasta que não é repositório sai como "limpa" | sem repositório git não há histórico para varrer | o script avisa e devolve código 2 |
| O teste de autor falha quando `GIT_AUTHOR_NAME` está no ambiente | o Git usa a variável antes do `user.name` do repositório | o teste passa um ambiente limpo ao Git |

## A skill e ela mesma

O `varrer.py` procura nomes de ferramenta e o vocabulário do trabalho com agente. A skill
contém essas expressões por natureza, então ela **não entra no próprio escopo**: rodar a
varredura na raiz da skill acusa a própria skill. É o comportamento esperado.
