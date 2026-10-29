# PCS5039 — Ambiente de simulação Reg10k: núcleo (nucleo-v1.4)

Projeto de referência da disciplina **PCS5039 — Engenharia de Software Orientada a IoT** (EPUSP): automação de iluminação residencial em ambiente simulado.

A sala é a do incremento 0: 5 × 4 m com uma porta, dois moradores (uma pessoa e o Rex, um cachorro de grande porte, que também é ocupante), um sensor de passagem (SA) no batente, um sensor de presença PIR (SP) com zona cega, um atuador, uma lâmpada com sensor de efeito e um interruptor. O hub roda um **controlador plugável**: a referência ou o de um grupo.

Desde a **nucleo-v1.0**, este repositório é o **núcleo**: motor, hub, plataforma, oráculo, página, schemas, skills e documentos. As versões da automação (V0 a V4) ficam em **repositórios de versão** que usam o núcleo como submódulo fixado numa tag e guardam só o que é delas: planta, cenários, controladores dos alunos, experimentos e dados (ver [`docs/plano-versoes-paralelas.md`](docs/plano-versoes-paralelas.md)). Até a migração, o núcleo mantém os 46 cenários de v0 a v1dtb como conjunto de regressão.

A **v0dt** acrescenta o gêmeo digital (DTReg10k) sem mudar a sala: o **DTReg10k-L** no hub, o **DTReg10k-R** na plataforma, um **canal** simulado entre os dois (atraso, perda, duplicação e desconexão) e o **app** do titular (consulta, comando remoto e preferência de apagamento). O número da versão acompanha o porte da automação e o sufixo `dt` indica o gêmeo: v0 → v0dt → v0dta → **v1dt** (2 cômodos) → v1dt.1 → …

A **v1dt** passa a uma residência com **sala e cozinha** ligadas por um vão sem porta (`cenarios/residencia-v1.json`). Cada cômodo tem o seu controlador (a mesma interface da v0), os seus parâmetros e o seu atuador; o SA do vão não diz a direção e vai aos dois controladores. O gêmeo e o espelho representam a casa cômodo a cômodo. Os 32 cenários anteriores continuam no ambiente de um cômodo (`cenarios/sala.json`), com as decisões idênticas às da v0dta.

A **v1dtb** (ajuste "b") atualiza a documentação para a residência. Os diagramas `classes-v1dt` e `componentes-v1dt` são novos. No `classes-v1dt`, `Comodo` é a classe geral, e sala e cozinha são instâncias dela, como na V2. Os casos de uso ganharam passar entre cômodos e espiar pelo vão. `EstadoComodo` e `ConfigComodo` passam a ser sinônimos de `EstadoSala` e `ConfigSala`, e os controladores escritos na v0 continuam funcionando. O roteiro de uso das skills está em `docs/roteiro-skills.md`.

A **v1dta** (ajuste "a" da v1dt) muda só a página: na aba Animação, a casa real ocupa o palco e o **gêmeo digital (DT) fica em miniatura** ao lado; o botão "Gêmeo digital (DT)", ou um clique na miniatura, troca os dois de lugar. O vão entre sala e cozinha passa a ser desenhado como abertura na parede, e a página abre no primeiro cenário da versão mais nova (M01). Decisões, atuações e métricas são as mesmas da v1dt (assinaturas em `tests/dados/assinaturas-v1dt.json`).

A **v0dta** (ajuste "a" da v0dt) acrescenta o **cômodo espelho**: a sala desenhada só com o que o gêmeo sabe, ao lado da sala real, com **amostras** (início, meio e fim) e a **fidelidade do espelho**, que separa a causa de cada diferença em percepção, sincronização ou "não afirma".

| Documento | Conteúdo |
|---|---|
| [`docs/guia-convencoes.md`](docs/guia-convencoes.md) | Guia de convenções: versões, identificadores, marcas, estrutura dos documentos, ciclo de incremento e publicação |
| [`docs/ambiente-simulacao-v1dt.md`](docs/ambiente-simulacao-v1dt.md) | Plano e entrega da v1dt (sala, cozinha e passagem) |
| [`docs/ambiente-simulacao-v1dta.md`](docs/ambiente-simulacao-v1dta.md) | Ajuste v1dta (gêmeo em miniatura, vão como abertura) |
| [`docs/plano-versoes-paralelas.md`](docs/plano-versoes-paralelas.md) | Plano das versões paralelas V0–V4 e do núcleo (com a entrega da nucleo-v1.0) |
| [`docs/roteiro-skills.md`](docs/roteiro-skills.md) | Roteiro de uso das skills (como pedir, paradas, histórico de uso) |
| [`docs/ambiente-simulacao-v0dta.md`](docs/ambiente-simulacao-v0dta.md) | Plano e entrega da v0dta (cômodo espelho) |
| [`docs/ambiente-simulacao-v0dt.md`](docs/ambiente-simulacao-v0dt.md) | Plano e entrega da v0dt (gêmeo digital) |
| [`docs/ambiente-simulacao-v02.md`](docs/ambiente-simulacao-v02.md) | Plano do incremento 0 (sala, dispositivos, controlador) |
| [`docs/roteiro-alunos.md`](docs/roteiro-alunos.md) | Exercícios E1–E6 (v0), E7–E10 (v0dt), E11 (v0dta), E12 (v1dt), E13 (v2dt, Casa A) e E14 (v1dt.1, dormir × ler parado) |
| [`docs/plataforma/`](docs/plataforma/) | V1 Business Drivers v02 e V2/V3 Requisitos v05 da plataforma Reg10k |

Os documentos da plataforma que este ambiente realiza estão em [`docs/plataforma/`](docs/plataforma/): a V1 Business Drivers (v02) e os requisitos das visões V2 e V3 (v02), no referencial RM-ODP adaptado.

## Começo rápido

Requer Python 3.11 ou superior (testado de 3.9 a 3.13). **Rode todos os comandos dentro da pasta do projeto**; fora dela, o Python responde `No module named sim` (ou `catalogo`).

```bash
cd PCS5039_ambiente_reg10k_vCl0
pip install -r requirements.txt

python -m sim --cenario N01                                   # um cenário com a referência
python -m sim --cenario FP01 --controlador alunos.grupo_exemplo
python -m sim --cenario DT05                                  # gêmeo: desconexão de 10 min
python -m sim --cenario M03                                   # v1dt: espiar a cozinha pelo vão
python -m catalogo                                            # todos os cenários e controladores + página
python -m pytest -q                                           # testes
python -m catalogo.validar                                    # valida todos os JSON contra os schemas
```

Depois de `python -m catalogo`, abra **`site/index.html`** com duplo clique. A página funciona sem servidor e sem internet.

## Repositórios de versão e experimentos (nucleo-v1.0)

Montar a pasta de um repositório de versão a partir do núcleo:

```
python tools/nova_versao.py ../reg10k-V0 --nome V0 --titulo "uma sala, com gêmeo digital e espelho" --ambientes sala
```

Dentro do repositório de versão, com o núcleo em `nucleo/` (submódulo):

```
python nucleo/reg10k.py catalogo                 # catálogo e site/index.html da versão
python nucleo/reg10k.py sim --cenario N01
python nucleo/reg10k.py validar
python nucleo/reg10k.py experimentos --sementes 30 --processos 4
python nucleo/reg10k.py assinaturas gravar V0
python nucleo/reg10k.py aprendizado --sementes 10    # nucleo-v1.4: 14 dias de treino + 7 de teste
```

No próprio núcleo, os mesmos comandos valem com `python -m catalogo`, `python -m experimentos` etc.; `--raiz PASTA` aponta para outra versão.

A **nucleo-v1.1** traz o **gerador de cenários por planta** (`python nucleo/reg10k.py gerador --ambiente <planta> --versao <versão>`): as famílias F1 a F7 com os mesmos episódios em qualquer casa, para comparar versões. Traz também as **asserções com janela relativa a um evento** (campo `apos`, por exemplo "acende até 1 s depois de entrar"), que valem em qualquer semente, e corrige o desperdício por saída: o período agora termina quando alguém volta ao cômodo antes de a luz apagar.

A **nucleo-v1.3** (para a v1dt.1) traz **ocupantes diversos** (perfis adulto, criança e idoso, que mudam só o movimento, e o visitante, sem papel no app), o **ocupante dormindo** (ações `DORMIR` e `ACORDAR`; quem dorme quer escuro, então apagar não é indevido, e a métrica `luz_com_todos_dormindo_s` mede o contrário) e o **detector de presença incompatível** do hub (suspeita verificada a cada 5 min, conciliada com passagem tardia, enviada como evento de fronteira "presença não explicada", nunca "invasão"; invariante OR-15). O gerador ganha as famílias F8 (um sai e outro fica) e F9 (dormir), e o comparador normaliza por cômodo as métricas somadas.

A **nucleo-v1.4** (para a v3dt.1) traz o **aprendizado do gêmeo com aceite do titular**. O roteiro pode ter **hora do dia** (`hora_inicio`, relógio de parede do hub; sem ela, nada muda). O **gêmeo remoto** (DTReg10k-R) aprende só com o que recebe do hub um **perfil agregado por cômodo e hora**: apagamentos com alguém dentro, reações logo depois e imobilidade longa. Ele não guarda nada por ocupante e retém 30 dias (`plataforma/aprendizado.py`). Com esse perfil, **sugere** T_apagamento por cômodo e faixa horária, com a evidência e o efeito esperado. A sugestão só vale depois do **aceite no app** (`APP_ACEITAR` / `APP_RECUSAR`), que cria uma versão de configuração pendente até o hub confirmar (RN-DT-07). O hub troca o T_apagamento na entrada e na saída de cada faixa (`FAIXA_APLICADA`), sem mudar o contrato do controlador. A ação `LER` é a do ocupante parado e acordado, que acena quando a luz apaga. A invariante nova **OR-17** confere que nada aprendido é aplicado sem aceite, que recusa é respeitada e que não há dado por ocupante; a OR-16 fica reservada para a V4. O protocolo de semanas (`python nucleo/reg10k.py aprendizado`) gera a rotina da família dia a dia a partir de um JSON da versão (`experimentos/rotina.py`) e compara, nos mesmos dias e sementes, os braços "aceitar" e "recusar", por cômodo e hora.

A **nucleo-v1.2** traz o **comparador entre versões** (`python nucleo/reg10k.py comparar <CSV da V0> <CSV da V1> <CSV da V2>`), que resume por família, versão e controlador só os cenários gerados por planta, os únicos equivalentes entre as casas. Corrige também a validação do catálogo nas versões sem a sala da v0.

O **protocolo de experimentos** (`experimentos/`) roda as famílias F1 a F7 (uso normal, permanência parada, passagem sem entrar, falha de dispositivo, queda de rede, comando remoto, espelho) com N sementes e grava um CSV com uma linha por execução e um **manifesto** com o commit do núcleo e da versão, as sementes e o hash de cada entrada. Cada versão diz quais cenários entram em cada família em `experimentos/familias.json`. Resultados de simulação, não de medição.

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
| Residência (v1dt) | M01 sala ↔ cozinha · M02 rua → cozinha · M03 espiar a cozinha · M04 Rex sozinho na cozinha · M05 parado na cozinha · M06 dois cruzam o vão juntos · M07 SA do vão falha · M08 SP da cozinha mudo · M09 interruptor da cozinha · M10 sai com a cozinha acesa · M11 comando remoto na cozinha · M12 preferência só da cozinha · M13 desconexão com circulação · M14 espelho da residência |
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

O controlador **reprova** se violar alguma invariante (OR-01 a OR-14) ou alguma asserção de nível REQUISITO.

Na residência (v1dt), o hub cria um controlador por cômodo e entrega a cada um só as evidências do seu cômodo e as do SA das passagens que o tocam (OR-13); as evidências de passagem trazem `passagem` e `comodos` nos dados. Inferir de que lado veio a pessoa é responsabilidade do controlador (exercício E12).

Na v0dt chegam duas evidências novas pelo mesmo `ao_evento`, com origem `PLATAFORMA`: `COMANDO_REMOTO` (já validado quanto à validade e à duplicidade; toda intenção devolvida responde ao comando e lista vazia é recusa) e `CONFIGURACAO` (o `ConfigSala` recebido em `iniciar` já vem atualizado). Um controlador da v0 que ignore o comando remoto continua respeitando as invariantes, mas falha nos requisitos de DT01 e DT04.

## Estrutura

```
sim/          simulador: residência (cômodos e passagens), mundo, dispositivos, falhas, motor (python -m sim)
hub/          barramento, registro JSONL, interface Controlador, referência e agente de sincronização (DTReg10k-L)
plataforma/   canal simulado e plataforma (DTReg10k-R, comandos, configuração, app)
avaliacao/    oráculo: métricas, invariantes OR-01..14, asserções; residencia.py: vistas por cômodo; espelho.py: amostras e SVG
catalogo/     execução do catálogo, validação de schemas, geração da página (python -m catalogo)
alunos/       controladores dos grupos
cenarios/     sala.json (v0), residencia-v1.json (v1dt), roteiros/ e esperado/
schemas/      JSON Schema de sala, roteiro, esperado, evento, métricas e catálogo
docs/         plano, roteiro dos alunos e diagramas UML (docs/uml/*.mmd e *.svg)
tests/        pytest (tests/dados: assinaturas de regressão por versão)
tools/        assinaturas.py (regressão das decisões), consolidar.py (código num único Markdown), cenarios_v1dt.py (gera M01–M14)
.claude/skills/  skills do Laboratório de Digital Twin (incremento-simulacao)
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
