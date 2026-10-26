# PCS5039 — Ambiente de simulação Reg10k (v0dta)

Projeto de referência da disciplina **PCS5039 — Engenharia de Software Orientada a IoT** (EPUSP): automação de iluminação residencial em ambiente simulado.

A sala é a do incremento 0: 5 × 4 m com uma porta, dois moradores (uma pessoa e o Rex, um cachorro de grande porte, que também é ocupante), um sensor de passagem (SA) no batente, um sensor de presença PIR (SP) com zona cega, um atuador, uma lâmpada com sensor de efeito e um interruptor. O hub roda um **controlador plugável**: a referência ou o de um grupo.

A **v0dt** acrescenta o gêmeo digital (DTReg10k) sem mudar a sala: o **DTReg10k-L** no hub, o **DTReg10k-R** na plataforma, um **canal** simulado entre os dois (atraso, perda, duplicação e desconexão) e o **app** do titular (consulta, comando remoto e preferência de apagamento). O número da versão acompanha o porte da automação e o sufixo `dt` indica o gêmeo: v0 → v0dt → v1dt (2 cômodos) → …

A **v0dta** (ajuste "a" da v0dt) acrescenta o **cômodo espelho**: a sala desenhada só com o que o gêmeo sabe, ao lado da sala real, com **amostras** (início, meio e fim) e a **fidelidade do espelho**, que separa a causa de cada diferença em percepção, sincronização ou "não afirma".

| Documento | Conteúdo |
|---|---|
| [`docs/ambiente-simulacao-v0dta.md`](docs/ambiente-simulacao-v0dta.md) | Plano e entrega da v0dta (cômodo espelho) |
| [`docs/ambiente-simulacao-v0dt.md`](docs/ambiente-simulacao-v0dt.md) | Plano e entrega da v0dt (gêmeo digital) |
| [`docs/ambiente-simulacao-v02.md`](docs/ambiente-simulacao-v02.md) | Plano do incremento 0 (sala, dispositivos, controlador) |
| [`docs/roteiro-alunos.md`](docs/roteiro-alunos.md) | Exercícios E1–E6 (v0), E7–E10 (v0dt) e E11 (v0dta) |
| [`docs/plataforma/`](docs/plataforma/) | V1 Business Drivers v02 e V2/V3 Requisitos v04 da plataforma Reg10k |

Os documentos da plataforma que este ambiente realiza estão em [`docs/plataforma/`](docs/plataforma/): a V1 Business Drivers (v02) e os requisitos das visões V2 e V3 (v02), no referencial RM-ODP adaptado.

## Começo rápido

Requer Python 3.11 ou superior (testado de 3.9 a 3.13). **Rode todos os comandos dentro da pasta do projeto**; fora dela, o Python responde `No module named sim` (ou `catalogo`).

```bash
cd PCS5039_ambiente_reg10k_vCl0
pip install -r requirements.txt

python -m sim --cenario N01                                   # um cenário com a referência
python -m sim --cenario FP01 --controlador alunos.grupo_exemplo
python -m sim --cenario DT05                                  # gêmeo: desconexão de 10 min
python -m catalogo                                            # todos os cenários e controladores + página
python -m pytest -q                                           # testes
python -m catalogo.validar                                    # valida todos os JSON contra os schemas
```

Depois de `python -m catalogo`, abra **`site/index.html`** com duplo clique. A página funciona sem servidor e sem internet.

## A página

| Aba | O que mostra |
|---|---|
| **Modelo** | Diagramas UML, regras RN-I0, parâmetros, dispositivos (modo ideal e realista), rastreabilidade com V1–V3, métricas e invariantes |
| **Cenários** | Galeria de **amostras do espelho** (início, meio, fim) por cenário e controlador, com download do SVG; os 32 cenários (filtro por versão: v0 de regressão ou v0dt) com o resultado de cada controlador, asserções, comparação entre controladores e o **editor de roteiro** (inclui ações do app e falhas de rede) |
| **Animação** | A sala real e o **cômodo espelho** lado a lado (chave plataforma R ou hub L), a faixa hub ↔ plataforma ↔ app e três pontos de vista: o que **acontece**, o que o **hub acha** (L) e o que a **plataforma acha** (R, com idade e selo atual ou desatualizado) |
| **Painel** | Linha do tempo verdade × SA × SP × hub (L) × decisões × lâmpada × plataforma (R) × canal × app × fidelidade do espelho, métricas, asserções, invariantes e o registro de eventos (exporta CSV; imprime em PDF) |

O endereço guarda a seleção: `site/index.html#painel/FN01/referencia`.

## Como o ambiente funciona

```
roteiro JSON ─► Simulador (mundo + dispositivos + falhas) ─► evidências ─► Hub ─► Controlador plugável
                     │                                                       │  (DTReg10k-L)
                     │                                          Agente de sincronização (fila persistente)
                     │                                                       │ ▲
                     │                                                 Canal simulado (atraso, perda, duplicação, queda)
                     │                                                       ▼ │
                     │                                  Plataforma: DTReg10k-R, comandos, configuração ◄─► App
                     │                                                       │
                     └──────────── camada VERDADE ──────► Registro JSONL ◄───┘ 8 camadas
                                                               │
                                                     Oráculo (métricas, OR-01 a OR-12, asserções) ─► catálogo ─► página
```

- **Três camadas** permitem medir acerto: a **verdade** (quem está na sala, se a lâmpada emite luz), a **percepção** (o que os sensores relatam) e a **decisão** (o que o controlador faz). O controlador nunca recebe a verdade (invariante OR-06).
- O registro segue as classes da V2 (`Evidencia`, `Intencao`, `ResultadoAtuacao`, `EstadoComodo`). Na v0dt entram as camadas **REDE** (sessão, perdas, duplicações) e **PLATAFORMA** (estado do DTReg10k-R, comandos, configuração e app).
- O canal, a plataforma e o agente usam geradores aleatórios próprios: ligar ou derrubar a rede não muda o que acontece na sala. A invariante **OR-12** confere isso por execução pareada (o mesmo roteiro sem a falha de rede deve produzir as mesmas decisões locais).
- A simulação avança em passos de 100 ms e é **determinística por semente**: a mesma semente produz o mesmo `eventos.jsonl`, byte a byte.
- O **modo realista** acrescenta ruído e falhas aleatórias. O catálogo roda cada cenário realista com 30 sementes e mostra a distribuição.

## Cenários

| Tipo | Cenários |
|---|---|
| Normais | N01 entra · N02 sai · N03 anda 10 min · N04 interruptor · N05 cachorro entra · N06 morador sai e o cachorro fica |
| Falsos positivos | FP01 passa pela porta sem entrar · FP02 corrente de ar no PIR · FP03 disparo espúrio do SA |
| Falsos negativos | FN01 lê parado · FN02 TV com microgestos · FN03 zona cega · FN04 entrada rápida e o SA falha · FN05 cachorro dormindo |
| Falhas | F01 SP sem resposta · F02 bateria baixa · F03 lâmpada queimada · F04 atuador travado · F05 hub reinicia · F06 relógio salta |
| Gêmeo digital (v0dt) | DT01 comando remoto acende · DT02 comando com o hub desconectado · DT03 rede lenta, comando vencido · DT04 canal duplica o comando · DT05 desconexão de 10 min · DT06 preferência com o hub offline · DT07 plataforma fora 5 min · DT08 canal realista 30 min · DT09 comando durante precedência manual · DT10 hub reinicia · DT11 relógio salta · DT12 Rex sozinho, consulta pelo app |

Os 20 cenários da v0 são **regressão**: rodam na v0dt sem alteração.

Cada cenário tem um roteiro em `cenarios/roteiros/` e asserções em `cenarios/esperado/`, no formato dado/quando/então, com dois níveis:

- **REQUISITO** vale para qualquer controlador; falhar reprova.
- **CARACTERIZACAO** descreve o comportamento da referência, inclusive suas limitações conhecidas. Em outro controlador, "difere" é informação, não falha. Por exemplo, o `grupo_exemplo` "difere" em FP01 porque não acende mais por engano.

## Como um grupo pluga o próprio controlador

1. Copie `alunos/grupo_exemplo/` para `alunos/grupoN/`.
2. Implemente a interface `Controlador` (`hub/controlador.py`), seja do zero ou herdando de `ControladorReferencia`.
3. Exporte a classe com o nome `Controlador` em `alunos/grupoN/__init__.py` e dê a ela um atributo `nome`.
4. Rode `python -m catalogo`. O controlador entra automaticamente na tabela, na comparação e nos testes.

O controlador **reprova** se violar alguma invariante (OR-01 a OR-12) ou alguma asserção de nível REQUISITO.

Na v0dt chegam duas evidências novas pelo mesmo `ao_evento`, com origem `PLATAFORMA`: `COMANDO_REMOTO` (já validado quanto à validade e à duplicidade; toda intenção devolvida responde ao comando e lista vazia é recusa) e `CONFIGURACAO` (o `ConfigSala` recebido em `iniciar` já vem atualizado). Um controlador da v0 que ignore o comando remoto continua respeitando as invariantes, mas falha nos requisitos de DT01 e DT04.

## Estrutura

```
sim/          simulador: mundo, dispositivos, falhas, motor (python -m sim)
hub/          barramento, registro JSONL, interface Controlador, referência e agente de sincronização (DTReg10k-L)
plataforma/   canal simulado e plataforma (DTReg10k-R, comandos, configuração, app)
avaliacao/    oráculo: métricas, invariantes OR-01..12, asserções; espelho.py: amostras e SVG do cômodo espelho
catalogo/     execução do catálogo, validação de schemas, geração da página (python -m catalogo)
alunos/       controladores dos grupos
cenarios/     sala.json, roteiros/ e esperado/
schemas/      JSON Schema de sala, roteiro, esperado, evento, métricas e catálogo
docs/         plano, roteiro dos alunos e diagramas UML (docs/uml/*.mmd e *.svg)
tests/        pytest
site/         index.html gerado
saida/        gerado: catalogo.json e saida/<cenário>/<controlador>/<semente>/{eventos.jsonl, metricas.json, espelho/}
```

## Diagramas

As fontes Mermaid ficam em `docs/uml/*.mmd`. Para regerar os SVG embutidos na página:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i docs/uml/classes.mmd -o docs/uml/classes.svg -c docs/uml/config.json -b white
```

## Integração contínua

A cada envio, o GitHub Actions (`.github/workflows/ci.yml`) roda os testes, valida os JSON, executa o catálogo com 30 sementes (modo realista e canal realista) e publica `site/index.html` e `saida/catalogo.json` como artefato. A execução falha se a referência não passar em todas as asserções, se algum controlador violar invariantes ou se alguma execução não for determinística.
