# A Wiki de código de um componente

A mesma estrutura nos nove repositórios, para o DevOps achar a mesma coisa no mesmo lugar.
O texto é gerado por `scripts/modelo_wiki.py` a partir do manifesto e do código.

## As oito seções

### 1. Visão geral

O que é o componente, o artefato e a versão, quem usa e de quem ele depende. É a primeira
coisa que o DevOps lê, e a que decide se ele entende o componente.

O que precisa estar: o GAV exato e a versão publicada, e a lista de dependências com as
versões. Sem isso, ninguém sabe o que pode ser implantado junto.

### 2. Build

Pré-requisitos, o comando, o que sai e como publicar.

O que precisa estar: a versão do JDK e do Maven (ou do Node e do npm), o comando exato, o nome
do arquivo gerado, o comando de publicação e a regra de versionamento. A regra importa:
versão publicada é imutável, e quem vai corrigir precisa saber que a próxima é a saída.

### 3. Configuração

Propriedades, segredos e dependências de ambiente.

O que precisa estar: cada propriedade com o valor no pacote e se precisa ser definida por
ambiente, e cada segredo pelo **nome da variável** — nunca pelo valor. As tabelas vêm do
`application.properties` ou do `application.yml` do próprio componente.

### 4. Deploy

Onde roda, contexto, porta, ordem e conferência.

O que precisa estar: o servidor e a versão do runtime, o contexto e como o arquivo define o
contexto no Tomcat, a porta, a ordem em relação aos outros componentes, e a tabela de
conferência depois de subir: método, endereço e o que deve responder. A tabela é o que
distingue "no ar" de "funcionando".

### 5. Operação

Logs, erros conhecidos e retorno de versão.

O que precisa estar: onde ficam os logs, a tabela de sintoma, causa provável e o que fazer, e
como voltar à versão anterior. A tabela de erros evita que cada incidente vire investigação
de novo.

### 6. API

O que o componente oferece.

Para aplicação: método, caminho e o que faz. Para biblioteca e pacote: a lista de exportações
com o que cada uma serve.

### 7. Testes

Como rodar, o que cobrem e onde ficam as respostas de referência.

O que precisa estar: o comando, o número de testes e onde estão as respostas de referência.
Elas ficam **dentro do próprio repositório** (`src/test/resources/contratos`), para o teste não
depender de outro caminho.

### 8. Versões

O que mudou em cada versão.

O que precisa estar: a versão atual e o que mudou nela. A linha da versão anterior fica, para
saber o que a atual conserta.

## A cópia na Wiki do projeto

A Wiki de cada repositório é a fonte. A Wiki do projeto recebe uma cópia, com o aviso no topo:

> Cópia da documentação do repositório **<repo>** (branch `<branch>`, commit `<commit>`). Para
> alterar, mude `docs/wiki` no repositório e publique de novo.

O script `scripts/wiki_componente.py` gera a cópia e publica. O aviso importa: sem ele,
alguém edita a cópia, o próximo `publish` sobrescreve, e a alteração se perde.

## A Wiki de Arquitetura e Deploy

Fica na Wiki do projeto, na raiz apontada por `wiki.raiz`, e é a página que responde o que
ninguém consegue responder olhando um repositório só: o mapa dos componentes, as dependências,
a ordem de publicação e de deploy, os ambientes, os segredos e o que o DevOps precisa
provisionar.
