# PCS5039 — Ambiente de simulação Reg10k (Incremento 0)

Projeto de referência da disciplina **PCS5039 — Engenharia de Software Orientada a IoT** (EPUSP): automação de iluminação residencial em ambiente simulado.

O incremento 0 tem uma sala de 5 × 4 m com uma porta, dois moradores (uma pessoa e o Rex, um cachorro de grande porte, que também é ocupante), um sensor de passagem (SA) no batente, um sensor de presença PIR (SP) com zona cega, um atuador, uma lâmpada com sensor de efeito e um interruptor. O hub roda um **controlador plugável**: a referência ou o de um grupo.

O plano completo está em [`docs/ambiente-simulacao-v01.md`](docs/ambiente-simulacao-v01.md) e o roteiro dos alunos em [`docs/roteiro-alunos.md`](docs/roteiro-alunos.md).

## Começo rápido

Requer Python 3.11 ou superior (testado de 3.9 a 3.13). **Rode todos os comandos dentro da pasta do projeto**; fora dela, o Python responde `No module named sim` (ou `catalogo`).

```bash
cd PCS5039_ambiente_reg10k_v0
pip install -r requirements.txt

python -m sim --cenario N01                                   # um cenário com a referência
python -m sim --cenario FP01 --controlador alunos.grupo_exemplo
python -m catalogo                                            # todos os cenários e controladores + página
python -m pytest -q                                           # testes
python -m catalogo.validar                                    # valida todos os JSON contra os schemas
```

Depois de `python -m catalogo`, abra **`site/index.html`** com duplo clique. A página funciona sem servidor e sem internet.

## A página

| Aba | O que mostra |
|---|---|
| **Modelo** | Diagramas UML, regras RN-I0, parâmetros, dispositivos (modo ideal e realista), rastreabilidade com V1–V3, métricas e invariantes |
| **Cenários** | Os 20 cenários com o resultado de cada controlador, detalhes e asserções, comparação entre controladores e o **editor de roteiro** |
| **Animação** | A planta da sala com morador, cachorro, sensores e luz, ao lado do que a verdade, os sensores e o controle "acham" a cada instante |
| **Painel** | Linha do tempo verdade × SA × SP × ocupação inferida × decisões × luz, métricas, asserções, invariantes e o registro de eventos (exporta CSV; imprime em PDF) |

O endereço guarda a seleção: `site/index.html#painel/FN01/referencia`.

## Como o ambiente funciona

```
roteiro JSON ─► Simulador (mundo + dispositivos + falhas) ─► evidências ─► Hub ─► Controlador plugável
                     │                                                       │
                     └──────────── camada VERDADE ──────► Registro JSONL ◄───┘ percepção, decisão, atuação, estado
                                                               │
                                                     Oráculo (métricas, invariantes, asserções) ─► catálogo ─► página
```

- **Três camadas** permitem medir acerto: a **verdade** (quem está na sala, se a lâmpada emite luz), a **percepção** (o que os sensores relatam) e a **decisão** (o que o controlador faz). O controlador nunca recebe a verdade (invariante OR-06).
- O registro segue as classes da V2 (`Evidencia`, `Intencao`, `ResultadoAtuacao`, `EstadoComodo`) para que o gêmeo digital do incremento 3 o leia sem mudanças.
- A simulação avança em passos de 100 ms e é **determinística por semente**: a mesma semente produz o mesmo `eventos.jsonl`, byte a byte.
- O **modo realista** acrescenta ruído e falhas aleatórias. O catálogo roda cada cenário realista com 30 sementes e mostra a distribuição.

## Cenários

| Tipo | Cenários |
|---|---|
| Normais | N01 entra · N02 sai · N03 anda 10 min · N04 interruptor · N05 cachorro entra · N06 morador sai e o cachorro fica |
| Falsos positivos | FP01 passa pela porta sem entrar · FP02 corrente de ar no PIR · FP03 disparo espúrio do SA |
| Falsos negativos | FN01 lê parado · FN02 TV com microgestos · FN03 zona cega · FN04 entrada rápida e o SA falha · FN05 cachorro dormindo |
| Falhas | F01 SP sem resposta · F02 bateria baixa · F03 lâmpada queimada · F04 atuador travado · F05 hub reinicia · F06 relógio salta |

Cada cenário tem um roteiro em `cenarios/roteiros/` e asserções em `cenarios/esperado/`, no formato dado/quando/então, com dois níveis:

- **REQUISITO** vale para qualquer controlador; falhar reprova.
- **CARACTERIZACAO** descreve o comportamento da referência, inclusive suas limitações conhecidas. Em outro controlador, "difere" é informação, não falha. Por exemplo, o `grupo_exemplo` "difere" em FP01 porque não acende mais por engano.

## Como um grupo pluga o próprio controlador

1. Copie `alunos/grupo_exemplo/` para `alunos/grupoN/`.
2. Implemente a interface `Controlador` (`hub/controlador.py`), seja do zero ou herdando de `ControladorReferencia`.
3. Exporte a classe com o nome `Controlador` em `alunos/grupoN/__init__.py` e dê a ela um atributo `nome`.
4. Rode `python -m catalogo`. O controlador entra automaticamente na tabela, na comparação e nos testes.

O controlador **reprova** se violar alguma invariante (OR-01 a OR-06) ou alguma asserção de nível REQUISITO.

## Estrutura

```
sim/          simulador: mundo, dispositivos, falhas, motor (python -m sim)
hub/          barramento, registro JSONL, interface Controlador e referência
avaliacao/    oráculo: métricas, invariantes OR-01..06, asserções
catalogo/     execução do catálogo, validação de schemas, geração da página (python -m catalogo)
alunos/       controladores dos grupos
cenarios/     sala.json, roteiros/ e esperado/
schemas/      JSON Schema de sala, roteiro, esperado, evento, métricas e catálogo
docs/         plano, roteiro dos alunos e diagramas UML (docs/uml/*.mmd e *.svg)
tests/        pytest
site/         index.html gerado
saida/        gerado: catalogo.json e saida/<cenário>/<controlador>/<semente>/{eventos.jsonl, metricas.json}
```

## Diagramas

As fontes Mermaid ficam em `docs/uml/*.mmd`. Para regerar os SVG embutidos na página:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i docs/uml/classes.mmd -o docs/uml/classes.svg -c docs/uml/config.json -b white
```

## Integração contínua

A cada envio, o GitHub Actions (`.github/workflows/ci.yml`) roda os testes, valida os JSON, executa o catálogo com 30 sementes e publica `site/index.html` e `saida/catalogo.json` como artefato. A execução falha se a referência não passar em todas as asserções, se algum controlador violar invariantes ou se alguma execução não for determinística.
