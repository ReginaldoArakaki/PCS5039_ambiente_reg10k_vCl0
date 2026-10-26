# Roteiro de uso das skills — ambiente Reg10k

**Versão:** 01 | **Data:** 25/10/2026 | **Responsável:** Reginaldo Arakaki (EPUSP)
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP

Uma **skill** é um roteiro de trabalho que o Claude carrega quando a tarefa pede. Ela registra o jeito combinado de fazer: as etapas, as paradas para aprovação, as verificações e o formato da entrega. Assim, cada versão do ambiente é feita do mesmo modo, sem precisar repetir as instruções a cada conversa.

## 1. Skills disponíveis

| Skill | Onde está | Para quê | Situação |
|---|---|---|---|
| `incremento-simulacao` | `.claude/skills/incremento-simulacao/SKILL.md` no repositório, com cópia salva na conta do Claude | Planejar, construir, verificar e entregar um incremento (v1dt.1, v2dt…) ou um ajuste (v1dta, v1dtb…) | Em uso desde a v1dt |
| Rodada de dúvidas | — | Montar a tabela DQ com propostas, bloqueantes primeiro | Planejada |
| V1 e V2/V3 | — | Revisar as visões RM-ODP, numerar RS, PD e R, gerar .md e .docx | Planejada |
| Verificação e publicação | — | Testes, página, clone limpo, patches e tags | Planejada (hoje faz parte de `incremento-simulacao`) |
| Documento .docx | — | Gerar os .docx da V1 e da V2/V3 com o estilo do projeto (hoje é feito por scripts de apoio fora do repositório) | Planejada |

O guia `docs/guia-convencoes.md` é a base de todas as skills. Elas apontam para ele em vez de repetir o que ele diz.

## 2. Como pedir

Basta escrever o pedido. O Claude reconhece que é um incremento ou um ajuste e carrega a skill. Para forçar o uso, comece a mensagem com o nome dela:

```
/incremento-simulacao v1dt.1: ocupante dormindo no quarto (PI-01)
/incremento-simulacao v1dtc: legenda da planta com os IDs dos dispositivos
```

O que ajuda a skill a acertar de primeira:

- **Nome da versão** seguindo o guia (§2). Número novo para porte maior (`v2dt`), ponto para variação no mesmo porte (`v1dt.1`), letra para ajuste (`v1dta`).
- **O que muda e o que não pode mudar.** Por exemplo: "as decisões dos cenários antigos não podem mudar".
- **Material de apoio** anexado ou citado: respostas de dúvidas, um print da tela, um trecho da V2/V3.

## 3. O caminho de um pedido

| Etapa | O que o Claude faz | O que você faz |
|---|---|---|
| 0. Situar-se | Lê o guia, o README e o último plano. Confere tags e patches pendentes. Roda os testes. | Nada |
| 1. Avaliação | Só quando você pergunta "qual caminho?": recomendação, contra-argumento e mitigação | Decide |
| 2. Dúvidas | Tabela DQ com uma proposta para cada dúvida | **Parada:** responde, ou diz "OK" para aceitar as propostas |
| 3. Plano | `ambiente-simulacao-<versão>.md` v01: regressão, rastreabilidade, dentro × fora, o que o aluno vê | **Parada:** aprova ou pede ajuste |
| 4. Construção | Grava a assinatura da versão de partida e faz núcleo, oráculo, cenários, schemas, página, UML e testes, nessa ordem | Nada; o Claude avisa se precisar mudar algo já aprovado |
| 5. Verificação | Testes (3.12 e 3.9), assinaturas, catálogo com 30 sementes, página no navegador e em iframe, prints examinados | Nada |
| 6. Entrega | Plano v02 com ◆, V2/V3 nova se houver RS, README, roteiro dos alunos, commit, patch testado em clone limpo, cópia no projeto | Aplica os patches e publica (comandos na resposta) |

Num ajuste pequeno de escopo claro, as etapas 2 e 3 podem ser puladas: o seu pedido vale como aprovação (guia §6).

## 4. Como as skills foram usadas até aqui

| Etapa | v1dt (sala e cozinha) | v1dta (gêmeo em miniatura) | v1dtb (documentação) |
|---|---|---|---|
| 0 | Sim | Sim (testes e assinaturas) | Sim |
| 1 | Feita antes de existir a skill: a análise "v1dt ou parada para skills" | Não se aplica | Não se aplica |
| 2 | `duvidas-v1dt.md`, 23 dúvidas, todas "OK" | Pulada: pedido direto | Pulada: pedido direto |
| 3 | Plano v01 aprovado com as dúvidas | Pulada; plano já em v02 | Sem plano próprio: o registro está neste roteiro e no README |
| 4 | Completa. **Faltou rever os diagramas que já existiam** (classes, casos de uso, componentes), que continuaram com a sala única. | Só a página | Diagramas revistos e nomes gerais no código |
| 5 | Completa | Completa | Completa |
| 6 | Completa | Completa (sem V2/V3: nenhum RS novo) | Completa |

A falha da v1dt na etapa 4 virou regra. A skill e o guia (§10) agora mandam rever os diagramas existentes e verificar se algum ainda usa a estrutura antiga.

## 5. Como manter as skills

- Quando um pedido revelar uma lacuna, como a dos diagramas, peça para atualizar a skill. O Claude propõe o texto novo num cartão de revisão, e você salva na conta. A cópia do repositório vai no patch seguinte.
- A cópia da conta é a que o Claude usa nas conversas. A do repositório serve de registro e para quem clonar o projeto. As duas devem ter o mesmo texto.
- Cada skill deve ser curta e apontar para o guia. Se uma regra vale para mais de uma skill, ela fica no guia.
