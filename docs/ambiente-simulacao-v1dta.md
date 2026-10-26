# Ambiente de simulação Reg10k — ajuste v1dta

**Versão do documento:** v02 · **Situação:** entregue · **Base:** v1dt · **Responsável:** Reginaldo Arakaki (EPUSP)

Linha de pesquisa: Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP.

| Versão | Data | Mudança |
|---|---|---|
| v01 | 25/10/2026 | Pedido do responsável ao ver a página da v1dt: incluir sala e cozinha no visual e ter o gêmeo em miniatura, com botão para ver o DT |
| v02 | 25/10/2026 | Entregue |

## 1. Motivo

Ao abrir a página da v1dt, o responsável não via a cozinha ligada à sala. Havia três causas:

1. A página abria no N01, que é um cenário v0 de um cômodo só.
2. O vão aparecia como uma linha tracejada sobre a parede, sem parecer uma abertura, e o rótulo ficava sobre a parede.
3. A casa real e o espelho ficavam um embaixo do outro, e o espelho só aparecia depois de rolar a página.

## 2. O que muda (só a página)

| Item | Antes (v1dt) | Depois (v1dta) |
|---|---|---|
| Palco da aba Animação | Casa real e espelho empilhados (dois cômodos) ou lado a lado (um cômodo) | Uma planta grande no palco e a outra em **miniatura** na coluna da direita. A chave "Casa real \| Gêmeo digital (DT)", o clique na miniatura ou o botão "⤢ ampliar" trocam as duas de lugar. |
| Visão do gêmeo (R/L) | Chave junto do título do espelho | Fica na barra do palco e vale para o gêmeo, esteja ele grande ou em miniatura |
| Vão entre sala e cozinha | Linha sobre a parede | A parede é recortada no vão: o piso e a luz dos dois cômodos aparecem pela abertura. Há batentes nas pontas, e o feixe do SA-02 fica no meio. Rótulo dentro da cozinha, com contorno claro |
| Cenário inicial | N01 (v0) | Primeiro cenário da versão mais nova (M01) |
| Botão "ver" das amostras do espelho | Abria a animação | Abre a animação com o gêmeo no palco |
| Altura | Sem limite | O palco tem no máximo 64% da altura da janela e a miniatura no máximo 320 px, para tudo caber sem rolar |

Fica fora: o motor, o oráculo, os cenários, os schemas e o modelo, que não mudam. Nos cenários de um cômodo, a planta continua mostrando só a sala, porque eles rodam no ambiente `sala.json`.

## 3. Regressão

- As decisões e atuações dos 46 cenários × 2 controladores são idênticas às da v1dt: `python tools/assinaturas.py comparar v1dt` dá 92 iguais, 0 mudaram.
- 202 testes passam.
- O catálogo com 30 sementes não acusa problemas, e os JSON são válidos.
- A página foi testada no navegador nas 92 execuções, com o gêmeo grande e em miniatura, sem erros no console. Também foi testada num iframe `srcdoc` com sandbox.

## 4. O que o aluno passa a ver

- A casa real e o gêmeo digital ficam na mesma tela, sem precisar rolar.
- Comparar a verdade com o que o gêmeo sabe é questão de um clique. Isso prepara a separação entre a "casa" e o "DT" que a plataforma terá numa aba própria.
- O vão aparece como passagem entre os dois cômodos. Fica visível que o SA-02 está no meio dele e que serve aos dois cômodos (RN-V1-02).

## 5. Ajustes feitos na construção

| Item | Motivo |
|---|---|
| ◆ O vão é desenhado com uma máscara recortando a parede, e não com um retângulo por cima | O retângulo escuro por cima ainda parecia uma parede. Com o recorte, o piso e a luz dos dois cômodos aparecem pela abertura. |
| ◆ A grade larga e o limite de altura valem também para os cenários de um cômodo | Com a miniatura, a sala única ficava grande demais no palco |
