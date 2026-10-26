# Plano do ambiente de simulação — v1dt (dois cômodos, passagem e gêmeo)

**Documento:** ambiente-simulacao-v1dt.md
**Versão:** 02 | **Data:** 25/10/2026 (v01, plano, de 25/10/2026)
**Disciplina:** PCS5039 — Engenharia de Software Orientada a IoT (EPUSP)
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP
**Base:** v0dta (tag `v0dta`), guia de convenções v01, rodada de dúvidas v1dt (DQ1-01 a DQ1-23, todas aprovadas em 25/10/2026), V1 v02 e V2/V3 v04.
**Situação:** entregue (tag `v1dt`). Os ajustes feitos na construção estão marcados com ◆ e listados na §14.

---

## Histórico de versões

| Versão | Data | Alterações |
|---|---|---|
| 01 | 25/10/2026 | Plano derivado da rodada de dúvidas aprovada |
| 02 | 25/10/2026 | Entrega: resultados na §14, ajustes de construção (◆) |

---

## Sumário

1. Decisões
2. Objetivo e posição na trilha
3. Escopo e rastreabilidade
4. Arquitetura
5. Regras e parâmetros
6. Planta e dispositivos
7. Registro e vistas por cômodo
8. Cenários
9. Métricas e invariantes
10. Página
11. Exercício e cronograma
12. Critérios de pronto e documentação
13. Decisões (aprovadas)
14. Entrega

---

## 1. Decisões

| ID | Decisão | Origem |
|---|---|---|
| D1-01 | Entra a **cozinha** (3,5 × 4 m), ligada à sala por um vão sem porta | DQ1-01 |
| D1-02 | **Um controlador por cômodo**, com a interface de hoje; coordenação entre cômodos é exercício (E12) | DQ1-02 |
| D1-03 | **Dois arquivos de ambiente**: `cenarios/sala.json` para os 32 cenários anteriores e `cenarios/residencia-v1.json` para os novos; o roteiro indica o ambiente | DQ1-03 |
| D1-04 | Regressão: roteiros e esperados anteriores intocados; DECISAO e ATUACAO dos 32 cenários idênticas às da v0dta (`tests/dados/assinaturas-v0dta.json`) | DQ1-03; guia §8 |
| D1-05 | PI-01 (ocupante dormindo) adiada para a v1dt.1; presença incompatível (RN03, RN17, RF-OPR-06) entra com o visitante, na v1dt.1 | DQ1-13, DQ1-14 |

## 2. Objetivo e posição na trilha

Primeira versão em que a casa tem mais de um cômodo. O aluno passa a ver a **passagem** como fonte de evidência ambígua: o SA do vão não diz a direção (RN09) e é entregue aos dois cômodos. Com a mesma interface de controlador, cada cômodo decide sozinho, e a falta de coordenação aparece em números (por exemplo, "espiar a cozinha pelo vão acende a cozinha"). O gêmeo e o espelho passam a representar a residência inteira, cômodo a cômodo.

## 3. Escopo e rastreabilidade

| Dentro | Fora (versão) |
|---|---|
| Sala e cozinha, vão interno com SA-02, kit completo na cozinha | Detecção do PIR pelo vão (v1dt.1) |
| Controlador por cômodo; parâmetros por cômodo | Coordenador da residência na referência (exercício E12) |
| Morador e Rex circulando entre os cômodos | Mais pessoas, visitante, presença incompatível (v1dt.1) |
| Gêmeo e espelho por cômodo; comando e preferência por cômodo | Ocupante dormindo, PI-01 (v1dt.1) |

| Artefato V1–V3 | Como aparece |
|---|---|
| A14, classe Passagem, RF-COM-05, INV-15 | SA-01 vinculado à porta externa e SA-02 ao vão; o vínculo vem do arquivo de ambiente |
| RN09, RN34 | SA sem direção, entregue aos dois cômodos; Rex sozinho em qualquer cômodo |
| EstadoComodo (V2) | Um estado por cômodo no hub (L) e na plataforma (R) |
| RF-OPR-01 a RF-OPR-07, RF-SYN-01 a RF-SYN-06 | Por cômodo, como na v0dt |
| CV15 (passagens repetidas) | M06 |

## 4. Arquitetura

- **Ambiente** (`sim/residencia.py`): residência com cômodos (retângulo, dispositivos, zonas cegas, controle) e passagens (externa ou interna, com seu SA). `sala.json` é lido como uma residência de um cômodo, com os mesmos identificadores e geradores aleatórios de antes.
- **Motor**: os ocupantes têm cômodo; ações novas `MUDAR_COMODO` (anda até o vão, cruza e entra no outro cômodo) e `ESPIAR` (estímulo no SA do vão sem cruzar). `ENTRAR` e `SAIR` usam a porta externa.
- **Hub**: um controlador e um executor por cômodo; o barramento entrega a cada controlador as evidências dos dispositivos do seu cômodo e as dos SA das passagens que o tocam. As chaves de intenção levam o cômodo quando há mais de um.
- **Gêmeo**: estados, resumo, comandos e configuração por cômodo.
- **Oráculo**: uma **vista por cômodo** do registro (a verdade daquele cômodo, as evidências que lhe foram entregues, suas decisões e o estado remoto dele) avaliada pelo mesmo oráculo; os resultados são somados para a residência. OR-13 e OR-14 são verificadas na residência.

## 5. Regras e parâmetros

| ID | Regra | Origem |
|---|---|---|
| RN-V1-01 | O SA de uma passagem interna é evidência para os dois cômodos que ela liga, sem direção | RN09; A14 |
| RN-V1-02 | Cada cômodo tem seu controlador, seus parâmetros e seu atuador; a decisão de um cômodo nunca atua em outro | RF-OPR-01; DQ1-02 |
| RN-V1-03 | Comando remoto e preferência indicam o cômodo; validade, chave e precedência como na v0dt | RN-DT-05, RN-DT-07, RN-DT-09 |
| RN-V1-04 | O gêmeo mantém um EstadoComodo por cômodo; a atualidade é por cômodo | RN-DT-04; EstadoComodo (V2) |

Parâmetros: os da v0dt, por cômodo; T_apagamento de 60 s na sala e na cozinha.

## 6. Planta e dispositivos

| Elemento | Sala | Cozinha |
|---|---|---|
| Área | x 0–5 m, y 0–4 m | x 5–8,5 m, y 0–4 m |
| Passagens | Porta externa (x 0,5–1,4 m, y 0) com SA-01; vão interno | Vão interno (x 5 m, y 2,6–3,5 m) com SA-02 |
| SP | SP-01 no canto nordeste, zona cega Z1 | SP-02 no canto sudeste, sem zona cega |
| Lâmpada, atuador, interruptor | LAMP-01, ATU-01, INT-01 | LAMP-02, ATU-02, INT-02 (ao lado do vão) |

## 7. Registro e vistas por cômodo

Os eventos ganham o campo `comodo` (ou `comodos`, para o SA de passagem). A verdade registra `OCUPANTES` com a lista por cômodo e `CRUZOU_PASSAGEM` com origem e destino. A vista por cômodo traduz o cruzamento do vão em entrada no cômodo de destino e saída do de origem, para que as métricas da v0 (atraso percebido, desperdício por saída) valham por cômodo.

## 8. Cenários

Regressão: os 32 cenários da v0, v0dt e v0dta, intocados. Novos (prefixo M, ambiente `residencia-v1`):

| ID | Cenário | Tipo | Rastreia |
|---|---|---|---|
| M01 | Morador vai da sala à cozinha e volta | NORMAL | RN-V1-01; RF-OPR-01 |
| M02 | Entra pela rua e vai direto à cozinha | NORMAL | RF-OPR-01 |
| M03 | Espia a cozinha pelo vão sem entrar | FALSO_POSITIVO | RN09; RN-V1-01 |
| M04 | Rex sozinho na cozinha, morador na sala | NORMAL | RN34 |
| M05 | Morador parado na cozinha | FALSO_NEGATIVO | RF-OPR-01 |
| M06 | Morador e Rex cruzam o vão juntos (rearme do SA-02) | NORMAL | CV15 |
| M07 | SA-02 falha | FALHA | RN01 |
| M08 | SP da cozinha sem resposta | FALHA | RN01; RN-I0-04 |
| M09 | Interruptor da cozinha | NORMAL | RF-OPR-02 |
| M10 | Sai pela rua com a cozinha acesa e vazia | NORMAL | RF-OPR-01; PS05 |
| M11 | Comando remoto acende a cozinha | GEMEO_DIGITAL | RN-V1-03; RF-OPR-03 |
| M12 | Preferência só da cozinha | GEMEO_DIGITAL | RN-V1-03; RF-OPR-07 |
| M13 | Desconexão com circulação entre cômodos | GEMEO_DIGITAL | RN-V1-04; RF-SYN-04 |
| M14 | Espelho da residência (amostras) | GEMEO_DIGITAL | RN-V1-04 |

## 9. Métricas e invariantes

Métricas da v0dta por cômodo e somadas para a residência (tempos somados, em cômodo·segundo; máximos e p95 pelo maior entre os cômodos). ◆ Nas asserções, `comodo` indica o cômodo; sem ele, métricas valem para a residência e os demais tipos, para a sala.

| ID | Verificação | Base |
|---|---|---|
| OR-13 | O SA de uma passagem interna é entregue aos dois controladores; nenhum controlador recebe evidência de dispositivo de outro cômodo | RN-V1-01; RN09 |
| OR-14 | Toda intenção de um cômodo vai ao atuador desse cômodo | RN-V1-02 |

## 10. Página

Animação com a residência inteira (real e espelho); painel com seletor de cômodo; galeria de amostras da residência.

## 11. Exercício e cronograma

E12: coordenador de cômodos que infere a direção da passagem (SA-02 seguido do SP de um dos lados) e reduz o falso positivo de M03 sem piorar M01 e M02. Dois dias.

## 12. Critérios de pronto e documentação

| # | Critério |
|---|---|
| CP-V1-01 | Assinatura dos 32 cenários anteriores idêntica à da v0dta |
| CP-V1-02 ◆ | M01–M14 aprovados com a referência; resultado do `grupo_exemplo` registrado (ver §14.3) |
| CP-V1-03 | OR-01 a OR-14 respeitadas em todas as execuções |
| CP-V1-04 | Schemas, testes, catálogo, página (navegador e iframe) verdes |
| CP-V1-05 | Plano entregue, README, roteiro (E12), V2/V3 com os refinamentos, tag `v1dt` |

## 13. Decisões (aprovadas)
14. Entrega

DQ1-01 a DQ1-23, conforme a rodada de dúvidas respondida em 25/10/2026, sem alteração.

---

## 14. Entrega

### 14.1 Critérios de pronto

| Critério | Resultado |
|---|---|
| CP-V1-01 | DECISAO e ATUACAO dos 32 cenários anteriores, com os dois controladores, idênticas às da v0dta (`python tools/assinaturas.py comparar v0dta`: 64 iguais) |
| CP-V1-02 | M01–M14 aprovados com a referência; o `grupo_exemplo` passa em 13 de 14 (§14.3) |
| CP-V1-03 | OR-01 a OR-14 respeitadas nas 92 execuções; testes com registro alterado mostram que OR-13 e OR-14 falham quando devem |
| CP-V1-04 | 202 testes (Python 3.9 e 3.12), schemas (inclusive `residencia.schema.json`), catálogo em cerca de 50 s, página sem erros no navegador e em iframe com sandbox |
| CP-V1-05 | Este plano entregue, README, roteiro (E12), guia de convenções v02 e V2/V3 v05 |

### 14.2 Resultados da referência (simulação, não medição)

| Cenário | O que mostra | Números |
|---|---|---|
| M01 | A luz segue o morador entre os cômodos | atraso percebido máx. 400 ms; cômodo esvaziado apaga em ~66 s |
| M03 | Espiar a cozinha acende a cozinha (limitação caracterizada) | 60 s de desperdício na cozinha |
| M05 | Morador parado na cozinha (falso negativo da v0, agora na cozinha) | 222 s de escuro com ocupante |
| M08 | SP da cozinha mudo: a cozinha "não afirma" e nunca apaga por silêncio | 92,5 s de desperdício na cozinha; a sala segue normal |
| M12 | Preferência só da cozinha (120 s) | cozinha acesa 85 s depois de vazia; sala apaga em 60 s |
| M13 | Desconexão com circulação: divergência registrada só na sala | reconciliação em 100 ms |
| M14 | Espelho da residência | sala fiel; cozinha com erro de percepção depois que o Rex deita |

### 14.3 Achado para a aula: coordenação entre cômodos

O `grupo_exemplo` (o SA sozinho não acende; espera o SP confirmar) resolve o falso positivo de M03 (0 s de desperdício contra 60 s da referência), mas na passagem pelo vão o PIR do outro lado demora a confirmar, e o atraso percebido sobe para **1,7 s**: ele reprova em M01 (limite de 1 s). Na v0, a mesma estratégia custava só 0,8 s, porque o morador entrava pela porta já em frente ao PIR. Com dois cômodos e um controlador por cômodo, nenhuma das duas estratégias simples atende os dois critérios: é o problema do E12 (coordenar os cômodos para inferir a direção da passagem).

### 14.4 Ajustes feitos na construção (◆)

| Ajuste | Motivo |
|---|---|
| CP-V1-02 passa a exigir só a referência; o `grupo_exemplo` tem o resultado registrado | A reprovação dele em M01 é o achado do incremento (§14.3), não um defeito do ambiente |
| Chave de intenção com o cômodo (`I-cozinha-1-0001`) só na residência | Com um cômodo, a chave da v0 se mantém, e a assinatura de regressão não muda |
| Asserções com `comodo`; sem ele, métricas da residência e demais tipos da sala | Os esperados da v0 continuam válidos sem edição |
| Falhas com `dispositivo` ou `comodo` (por exemplo, `SA_PERDE_PROXIMA` no `SA-02`) | Escolher o alvo da falha numa casa com vários dispositivos do mesmo tipo |
| Cenários M gerados por `tools/cenarios_v1dt.py` | Guia de convenções §7: cenários gerados por script |
| Na página, casa real e casa espelho empilhadas; painel com seletor "todos" ou um cômodo | A planta de 8,5 m não cabe lado a lado com legibilidade |
