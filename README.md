# monorepo-para-repositorios

Skill que transforma um monorepo em vários repositórios prontos para o time de DevOps: um repositório por componente, com histórico preservado, sem rastro de IA, com Wiki de código padronizada e com as versões publicadas no feed de pacotes.

O caso que motivou a skill foi a divisão da família ERPConsulta em nove repositórios do projeto "Digital Solution MFG Run", com Wiki de código em cada um, Wiki de Arquitetura e Deploy na Wiki do projeto e publicação das versões no feed `mfg-java`.

## Como funciona

Tudo se origina de um **manifesto JSON** que descreve o que fazer. Nenhum script carrega o caso de um projeto específico.

```json
{
  "projeto": "Digital Solution MFG Run",
  "org": "yamahaind",
  "feed": "mfg-java",
  "responsavel": { "nome": "Quem assina os commits", "email": "pessoa@exemplo" },
  "monorepo": { "url": "...", "branch": "main" },
  "wiki": { "raiz": "/Java/ERP Consulta", "identificador": "...", "link_arquitetura": "..." },
  "ambiente": { "servidor": "Tomcat 11", "java": "JDK 25", "build": "Maven 3.9" },
  "componentes": [
    {
      "repo": "ITSecurityService",
      "caminho": "apps/it-security-service",
      "artefato": "br.com.yamaha:itSecurityService",
      "tipo": "maven-war",
      "versao": "2.0.0",
      "publica": true,
      "dependeDe": ["neway-lib", "Middleware", "FinancialDcreModel"],
      "descricao": "Serviço de entrada: autentica no SGA e emite a credencial de acesso."
    }
  ]
}
```

O campo `dependeDe` é o que define a ordem de build e a ordem de publicação no feed: sai do grafo, não da cabeça de quem opera. O `responsavel` é quem assina os commits separados.

## Fases

| Fase | O que faz | Escreve? |
|---|---|---|
| 1. Diagnóstico | O que existe, o que já está no feed, quem depende de quem | não |
| 2. Separação | Um repositório por componente, com histórico preservado | sim |
| 3. Prova | Cada repositório compila sozinho, com repositório local vazio | não |
| 4. Documentação | Wiki de código em cada repositório e cópia na Wiki do projeto | sim |
| 5. Publicação | As versões no feed, na ordem das dependências | sim |
| 6. Limpeza | Tira o que sobrou de rastro de IA, reescrevendo o histórico | sim |

Cada fase é um comando separado, com `--dry-run`. Nada de passar de uma fase sem conferir a anterior.

## Scripts

| Script | Para que serve |
|---|---|
| `scripts/manifesto.py` | Lê e valida o manifesto; calcula a ordem de publicação |
| `scripts/varrer.py` | Acha rastro de IA na árvore, no histórico, nos autores e nas mensagens |
| `scripts/separar.py` | Separa o monorepo em repositórios, reescrevendo o histórico |
| `scripts/modelo_wiki.py` | As oito seções da Wiki de código, com o texto de cada uma |
| `scripts/wiki_componente.py` | Gera a Wiki de código de cada componente e publica a cópia na Wiki do projeto |
| `scripts/publicar_feed.py` | Publica Maven e npm no feed, na ordem das dependências |

## Instalação

Copiar a pasta para `~/.config/opencode/skills/monorepo-para-repositorios`:

```bash
cp -r . ~/.config/opencode/skills/monorepo-para-repositorios
```

O `SKILL.md` é o ponto de entrada: ele diz quando usar a skill, em que ordem rodar as fases e o que conferir em cada uma.

## A skill não varre a si mesma

O `varrer.py` procura nomes de ferramenta e o vocabulário do trabalho com agente. A skill contém essas expressões por natureza, então ela **não entra no próprio escopo** da varredura. Isso é comportamento esperado e documentado, não defeito: ao rodar `varrer.py` na raiz da skill, ela vai se acusar (178 achados na versão em que este texto foi escrito). O `references/armadilhas.md` registra o motivo.

## Testes

```bash
python -m pytest -v
```

Cada script tem seu teste, e o `separar.py` foi ensaiado num monorepo de teste com três
componentes: cada repositório saiu com só o conteúdo do seu componente e o histórico do commit
que o tocou.

## Documentação

| Documento | Conteúdo |
|---|---|
| `SKILL.md` | O roteiro: quando usar, as fases, os portões, os scripts |
| `references/armadilhas.md` | O que dá errado e como contornar |
| `references/wiki-componente.md` | As oito seções e o que o DevOps precisa em cada uma |
| `references/publicacao-feed.md` | Ordem, imutabilidade das versões, o que fazer quando a versão já saiu |
| `manifesto_exemplo.json` | Exemplo completo, com os nove componentes de um caso real |
