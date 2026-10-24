# Roteiro dos alunos — Incremento 0 (3 dias)

**Disciplina:** PCS5039 — Engenharia de Software Orientada a IoT
**Ambiente:** sala com uma porta, um morador e o Rex (cachorro de grande porte); SA, SP (PIR), atuador, lâmpada e interruptor.
**Referência:** o plano está em `docs/ambiente-simulacao-v02.md`. Siga as seções indicadas em cada exercício.

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
