# SDD ledger — plan: C:\Users\carlos\Desktop\Projetos-Yamaha\ERPConsulta\skill-monorepo-para-repositorios\planejamento\2026-10-21-skill-monorepo-plano.md

Spec: planejamento/2026-10-21-skill-monorepo-design.md
Workspace: <repo>/.superpowers/sdd/2026-10-21-skill-monorepo-plano/

Pre-flight: shared interfaces
- Task 1 produz `scripts/manifesto.py` (carregar, validar, ordem_publicacao) → Tasks 3 e 5 consomem `carregar` e `validar`; Task 5 consome `ordem_publicacao`. Nomes conferidos no bloco Interfaces de cada tarefa: batem.
- Task 2 produz `scripts/varrer.py` com `varredura(pasta, excecoes) -> list[str]` e `main(argv) -> int` → Task 3 não consome; Task 6 cita o script. Sem conflito.
- Task 3 produz `scripts/separar.py` com `gerar_comandos`, `conferir_caminhos`, `verificar_branch_padrao`, `escrever_pom_independente`, `escrever_package_independente`, `commitar_com_merge`, `main` → nenhuma outra tarefa consome. Sem conflito.
- Task 4 produz `scripts/modelo_wiki.py` (gerar_secoes, ORDEM) e `scripts/wiki_componente.py` (publicar_projeto, main) → nenhuma outra tarefa consome. Sem conflito.
- Task 5 produz `scripts/publicar_feed.py` com `versao_publicada`, `comandos_publicar`, `main` → nenhuma outra tarefa consome. Sem conflito.

Ruling: o plano assume um repositório Git com histórico para a branch da skill, mas o diretório de trabalho
(`planejamento/`) não é um repositório e a Tarefa 7 previa criar o repositório só no fim. Criei o repositório
`skill-monorepo-para-repositorios` antes da Tarefa 1, com o plano e a spec dentro dele, para que o ledger e os
briefs tenham onde morar e para que a Tarefa 7 vire só a publicação no GitHub e a instalação local.
Custo se estiver errado: um `git init` a mais, sem efeito no conteúdo entregue.
