# Roteiro dos alunos — Incremento 0 (3 dias)

**Disciplina:** PCS5039 — Engenharia de Software Orientada a IoT
**Ambiente:** sala com uma porta, um morador e o Rex (cachorro de grande porte); SA, SP (PIR), atuador, lâmpada e interruptor.
**Referência:** o plano do incremento 0 está em `docs/ambiente-simulacao-v02.md`; o da v0dt, no fim deste roteiro. Siga as seções indicadas em cada exercício.

## Antes de começar

```bash
pip install -r requirements.txt
python -m catalogo          # gera saida/ e site/index.html
```

Abra `site/index.html`. Percorra as quatro abas, assista a N01, FP01 e FN01 na aba **Animação** e compare-os na aba **Painel**.

## Dia 1 — Negócio e modelos

### E1. Modelo de negócio (plano §1.2 e §5.1)

1. Leia as regras RN-I0-01 a RN-I0-08 (aba Modelo → Regras).
2. A decisão de tratar o cachorro como ocupante (RN-I0-01) fez de FN05 um falso negativo. **Proponha uma regra alternativa** e diga quais cenários mudariam de tipo e quais métricas piorariam ou melhorariam.
3. Responda: o que deveria acontecer quando o morador **dorme** no sofá? (Pendência PI-01 do plano.)

**Entrega:** uma página com a regra proposta e a análise.

### E2. UML estrutural e comportamental (plano §6)

1. Compare `docs/uml/classes.mmd` com o código (`sim/modelos.py`, `hub/controlador.py`, `sim/dispositivos.py`). Liste divergências de nome, atributo ou multiplicidade.
2. Os diagramas de estados (`estados-ocupacao`, `estados-luz`) cobrem o reinício do hub (F05)? E a lâmpada queimada (F03)? Proponha as transições que faltam.
3. Escolha um cenário de falha e desenhe a sequência correspondente em Mermaid.

**Entrega:** diagramas revisados em `docs/uml/` do grupo e a análise escrita de 3 cenários (o que a verdade, a percepção e a decisão mostram em cada um).

## Dia 2 — Componentes e implementação

Todo controlador implementa a interface `Controlador` (`hub/controlador.py`):

```python
iniciar(config)                  # parâmetros; chamado de novo após reinício do hub
ao_evento(evidencia, agora_ms)   # devolve uma lista de Intencao
ao_tick(agora_ms)                # a cada 100 ms; temporizações
estado()                         # EstadoSala: ocupação, luz, precedência, idade, alertas
```

Regras do contrato: o controlador não lê a verdade, toda intenção declara `causa` e `regra`, e ele não guarda estado fora do próprio objeto.

### E3. Reduzir o falso positivo da porta (FP01, FN04)

O `alunos/grupo_exemplo` já mostra uma solução simples: o SA sozinho não acende; quem acende é o SP. Rode `python -m catalogo` e compare na aba Cenários → Comparação.

1. Explique por que FP01 e FP03 melhoraram e por que o escuro na entrada aumentou (0,4 s → 0,8 s).
2. Implemente uma variante melhor. Ideia: o SA acende só se o SP confirmar em até 3 s, mas sem perder a entrada quando o PIR está em repouso.

### E4. Tempo de apagamento adaptativo (FN01 a FN03, FN05)

1. Implemente um controlador que espere mais quando houve uma passagem pela porta (provável entrada) e nenhuma passagem depois (sem saída).
2. Meça o efeito em FN01, FN03 e FN05 (escuro com ocupante) **e** em N02 (desperdício na saída).

**Entrega do dia 2:** `alunos/grupoN/` com o controlador, passando nas invariantes (`python -m pytest -q`).

## Dia 3 — Integração e testes

### E5. Novos cenários

1. Na aba Cenários → Editor de roteiro, crie 2 cenários novos. Sugestões: o Rex entra correndo atrás do morador (rearme do SA), ou o morador entra com o SP sem resposta.
2. Salve os JSON em `cenarios/roteiros/`. Escreva as asserções em `cenarios/esperado/<ID>.json`, marcando o nível de cada uma: REQUISITO ou CARACTERIZACAO.
3. Rode `python -m catalogo.validar` e `python -m catalogo`.

### E6. Comparação e apresentação

1. Na aba Cenários → Comparação, compare o seu controlador com a referência.
2. Discuta o trade-off **desperdício × escuro com ocupante**. Algum controlador melhora os dois ao mesmo tempo? Em quais cenários?

**Entrega do dia 3:** relatório de 1 página com a tabela comparativa (exportada em CSV) e a apresentação do grupo.

## Avaliação

| Item | Peso sugerido |
|---|---|
| E1 e E2: modelos e análise | 30% |
| E3 ou E4: controlador (invariantes respeitadas, requisitos aprovados) | 35% |
| E5: cenários novos com asserções válidas | 15% |
| E6: análise comparativa e apresentação | 20% |

O critério de ranking por métrica ou de análise escrita é a pendência PI-03 do plano.

---

# Roteiro dos alunos — v0dt: gêmeo digital (2 dias)

**Ambiente:** a mesma sala, o mesmo morador e o mesmo Rex. Entram o DTReg10k-L (hub), o DTReg10k-R (plataforma), o canal simulado e o app do titular.
**Referência:** `docs/ambiente-simulacao-v0dt.md`. Os 20 cenários da v0 continuam no catálogo como regressão.

## Antes de começar

```bash
python -m catalogo          # agora com 32 cenários
python -m sim --cenario DT05
```

Na aba **Animação**, abra DT05 e observe lado a lado o que **acontece**, o que o **hub acha** e o que a **plataforma acha**. Na aba **Painel**, veja as faixas "plataforma (R)", "Canal" e "App".

O contrato do controlador não mudou. Duas evidências novas chegam pelo `ao_evento`, com origem `PLATAFORMA`:

| Evidência | Dados | O que fazer |
|---|---|---|
| `COMANDO_REMOTO` | `acao`, `chave_remota`, `solicitante` | Já chega dentro da validade e sem duplicata. Toda intenção devolvida responde ao comando; lista vazia é recusa. Siga a RN-DT-09: abaixo da manual, acima da automática |
| `CONFIGURACAO` | `versao`, `t_apagamento_ms` | O `ConfigSala` recebido em `iniciar` já vem atualizado; use o novo valor |

Quem herda de `ControladorReferencia` já trata as duas.

## Dia 1 — Modelos e componentes

### E7. Três pontos de vista (plano v0dt §4, §5 e §7)

1. Para DT05, descreva o que a verdade, o DTReg10k-L e o DTReg10k-R mostram **antes**, **durante** e **depois** da queda do enlace. Em que instante o R deixa de ser "atual"? Por que ele registra uma divergência na volta, e quem tem a autoridade para resolvê-la (RN27)?
2. Desenhe em Mermaid a sequência de DT06 (preferência alterada com o hub offline), do toque no app até a luz apagar em 120 s.
3. Compare `docs/uml/componentes-v0dt.mmd` com o código (`hub/sincronizacao.py`, `plataforma/`). Liste as divergências.

### E8. Honestidade da informação no app (DT02, DT05, DT07, DT10)

1. O app mostra o último estado com idade e o selo "desatualizado". Proponha uma política alternativa de exibição (por exemplo, esconder a ocupação após 5 min sem sessão, ou mostrar a "última evidência conhecida" com destaque) e escreva-a como regra.
2. Num ramo git do grupo, implemente a política em `plataforma/plataforma.py` (métodos `_atualizar` e `app_consulta`) e rode DT02, DT05, DT07 e DT10 com `python -m sim --cenario <ID>`. A invariante **OR-08** continua respeitada? Os testes (`python -m pytest -q`) continuam passando?

**Entrega do dia 1:** análise de DT05, sequência de DT06 e a regra de exibição proposta.

## Dia 2 — Integração e testes

### E9. Cenários de rede

1. No editor de roteiro, crie 2 cenários com o ator `app` e falhas de rede. Sugestões: quedas curtas e repetidas do enlace (a espera de reconexão dobra a cada tentativa); duas preferências seguidas com o hub offline (a primeira fica SUBSTITUIDA); comando remoto com a plataforma fora do ar.
2. Escreva as asserções com os tipos novos: `gemeo`, `comando`, `config` e `app_consulta`.
3. Rode `python -m catalogo.validar` e `python -m catalogo`. Em que cenários a execução pareada (OR-12) se aplica, e por quê?

### E10 (opcional, bônus). Aprendizado mínimo

1. Gere 3 semanas simuladas de rotina do morador (roteiros longos ou uma sequência de roteiros).
2. A partir do registro, calcule o perfil horário de ocupação e sugira um T_apagamento por faixa de horário.
3. A sugestão só vale depois de aceita (simule com `APP_PREFERENCIA`, RN-DT-07). Meça o efeito em FN01 e FN02: o escuro com ocupante cai? O desperdício sobe quanto?

**Entrega do dia 2:** política do app aprovada nas invariantes, cenários novos no catálogo e a discussão da OR-12.

## Avaliação da v0dt

| Item | Peso sugerido |
|---|---|
| E7: modelos e análise dos três pontos de vista | 35% |
| E8: política do app (OR-08 respeitada, requisitos aprovados) | 35% |
| E9: cenários de rede com asserções válidas | 30% |
| E10: aprendizado mínimo | bônus de até 15% |
