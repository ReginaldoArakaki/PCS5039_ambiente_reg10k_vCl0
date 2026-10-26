# Plano de ajuste — v0dta (espelho visual do gêmeo digital)

**Documento:** ambiente-simulacao-v0dta.md
**Versão:** 02 | **Data:** 24/10/2026 (v01, plano, de 24/10/2026)
**Disciplina:** PCS5039 — Engenharia de Software Orientada a IoT (EPUSP)
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP
**Base:** v0dt entregue (tag `v0dt`), plano v0dt v02 e V2/V3 v03.
**Situação:** entregue. Plano aprovado com as propostas DQA-01 a DQA-06 e implementado no repositório (tag `v0dta`). Os ajustes feitos na construção estão marcados com ◆ e listados na §11.

---

## Histórico de versões

| Versão | Data | Alterações |
|---|---|---|
| 01 | 24/10/2026 | Plano para aprovação |
| 02 | 24/10/2026 | Entrega: DQA-01 a DQA-06 aprovadas; "não afirma" passa a incluir a incerteza declarada; resultados na §11 |

---

## 1. O que muda e por quê

A v0dt já registra o que o gêmeo sabe, mas só como texto e faixas na linha do tempo. A **v0dta** (a v0dt com o ajuste "a") desenha esse conhecimento como um **cômodo espelho**: uma segunda planta da sala, montada apenas com o que o gêmeo recebeu, ao lado da sala real.

O espelho **não é uma cópia da sala real**, e é aí que está o valor didático. As diferenças entre as duas plantas são exatamente os limites do sistema:

| Na sala real (verdade) | No cômodo espelho (gêmeo) | Por quê |
|---|---|---|
| Morador e Rex com posição e identidade | Uma "mancha de presença" sem identidade nem posição | SA e SP não identificam pessoa, cachorro, direção ou contagem (RN09, RN34) |
| Lâmpada acesa ou apagada de fato | Estado da luz segundo o gêmeo, com o nível de evidência (efeito observado, execução relatada, desconhecido) | RN02: intenção, execução e efeito são distintos |
| O que acontece agora | O que o gêmeo sabia há *n* segundos, com a idade visível | Atualidade (PS06, PS11) |
| Interação física: porta, interruptor | Interação remota: comando e preferência pelo app | O titular só age no espelho pelo app (RN-DT-05, RN-DT-09) |
| Sempre disponível | Congelado e hachurado quando a sessão cai | RN-DT-04 |

As **amostras** são retratos lado a lado (sala real × espelho), com os dados de cada lado, em três momentos de cada execução: **início, meio e fim**. Elas servem para relatórios, para a correção dos exercícios e para comparar controladores e versões sem precisar assistir à animação.

---

## 2. Decisões que orientam o ajuste

| ID | Decisão | Origem |
|---|---|---|
| DTA-01 | O espelho é uma **projeção somente leitura** do gêmeo. A página não simula nada: toda a lógica continua no motor Python | Princípio da v0 (página só reproduz) |
| DTA-02 | Há dois espelhos possíveis: o do hub (DTReg10k-L) e o da plataforma (DTReg10k-R). O padrão é o **R**, que é o que o titular vê; o L fica numa chave de alternância | DT-02 da v0dt |
| DTA-03 | O espelho só usa dados que chegaram ao gêmeo. Nada da camada VERDADE entra nele (estende a OR-06 à página) | OR-06 |
| DTA-04 | Interação no espelho é a do app: o espelho mostra comandos e preferências como ações do titular, nunca como interruptor | RN-DT-09 |
| DTA-05 | Os 32 cenários da v0dt são regressão: decisões, atuações e asserções não mudam | DT-05 da v0dt |

---

## 3. Ajustes no motor (pequenos)

Hoje o DTReg10k-R só registra o estado consolidado (ocupação, luz, precedência, alertas). Para desenhar sensores e evidências no espelho, ele precisa registrar também o que recebeu.

| Ajuste | Onde | Efeito |
|---|---|---|
| A1. Registrar as evidências recebidas: `PLATAFORMA/EVIDENCIA_RECEBIDA` com origem (SA-01, SP-01, INT-01), tipo, instante de origem e de recepção | `plataforma/plataforma.py` | O espelho pisca o SA e acende o cone do SP quando a evidência **chega**, não quando acontece |
| A2. Registrar os resultados de atuação recebidos, com o nível | Idem | O espelho mostra a lâmpada com o nível de evidência |
| A3. Gerar as **amostras** de cada execução: `saida/<cenário>/<controlador>/<semente>/espelho/amostras.json` e três SVG (`inicio.svg`, `meio.svg`, `fim.svg`) | Novo `avaliacao/espelho.py` | Retratos que abrem em qualquer navegador e entram em relatório |
| A4. Métrica de **fidelidade do espelho**, decomposta | `avaliacao/oraculo.py` | Ver §5 |

Os ajustes A1 e A2 só acrescentam eventos na camada PLATAFORMA. Os hashes dos registros mudam, mas as camadas DECISAO e ATUACAO ficam idênticas, e a OR-12 e os testes confirmam isso.

---

## 4. Amostras: início, meio e fim

### 4.1 Instantes

| Amostra | Instante padrão | Ajuste |
|---|---|---|
| Início | Primeira ação do roteiro + 5 s | Mostra o espelho saindo de "sem evidência" |
| Meio | Metade da duração | — |
| Fim | Duração − 1 s | Mostra o estado final e a fila |

O roteiro pode trocar os instantes padrão por momentos de interesse, com o campo opcional `amostras_ms` (por exemplo, DT05 em 30 s, 300 s e 665 s: antes, durante e logo depois da queda).

### 4.2 Conteúdo de cada amostra

| Lado | Visual | Dados |
|---|---|---|
| Sala real | Planta com morador, Rex, luz física, SA e SP | Quem está na sala, luz física |
| Espelho (R ou L) | Planta do gêmeo: mancha de presença, luz com o nível de evidência, últimos sinais de SA e SP, selo de atualidade, conexão | Ocupação, luz, idade, atualidade, conexão, versão de configuração, último comando do app |
| Rodapé | Selo **confere**, **diverge** ou **não afirma** (desatualizado) | Classificação da diferença (§5) |

---

## 5. Fidelidade do espelho

A diferença entre a sala real e o espelho tem duas causas que os alunos precisam separar:

| Métrica | Definição | Causa que isola |
|---|---|---|
| `espelho_fiel_s` | Tempo em que o espelho R está atual e confere com a verdade (ocupação e luz) | — |
| `erro_de_percepcao_s` | Tempo em que o hub (L) já diverge da verdade | Sensores e controlador (FN, FP) |
| `erro_de_sincronizacao_s` | Tempo em que o L confere com a verdade, mas o R ainda não confere com o L | Canal e plataforma |
| `espelho_nao_afirma_s` ◆ | Tempo com o R desatualizado, sem evidência, com a plataforma fora ou com a ocupação declarada **desconhecida** | Conexão ou incerteza declarada (RN01) |

As quatro somam a duração do cenário. Exemplo esperado:
- **FN01:** o erro aparece como **percepção**.
- **DT05:** aparece como **não afirma**.
- **DT08:** aparece como **sincronização**, em fatias curtas.

Nenhuma dessas métricas vira requisito nesta versão: elas são de caracterização.

---

## 6. Página

| Aba | Ajuste |
|---|---|
| Animação | A planta real e o **cômodo espelho** lado a lado e sincronizados pelo mesmo cursor de tempo, com chave R/L. O espelho congela e é hachurado sem sessão. Comandos do app aparecem no espelho como toque no ícone do app |
| Painel | Faixa "Fidelidade do espelho", colorida pelas quatro classes da §5 |
| Cenários | Galeria de **amostras** (início, meio e fim) por cenário e controlador, lado a lado, com exportação dos SVG |
| Modelo | Tabela "real × espelho" (§1) e as métricas de fidelidade |

---

## 7. Cenários e testes

| Item | Conteúdo |
|---|---|
| Regressão | Os 32 cenários; DECISAO e ATUACAO idênticas às da v0dt (teste novo compara as assinaturas com a tag `v0dt`) |
| Amostras | `amostras_ms` em DT05, DT06, DT08 e DT10; padrão nos demais |
| Asserção nova | Tipo `espelho`: no instante *t*, a classe do espelho (por exemplo, DT05 em 300 s: "não afirma"). ◆ Entra só nos cenários DT; nos da v0 a verificação fica nos testes, para não alterar os arquivos de regressão |
| Testes novos | O espelho nunca usa a verdade (DTA-03); as quatro classes somam a duração; cada execução gera 3 amostras SVG válidas |

---

## 8. Exercício e cronograma (1 dia)

| Ex. | Atividade |
|---|---|
| E11 | Para 3 cenários (um FN, um de falha de rede, um do app), use as amostras para explicar cada diferença entre a sala real e o espelho e classifique a causa como percepção, sincronização ou conexão. Proponha uma mudança (no controlador, no canal ou na exibição) que aumente o tempo de espelho fiel, e meça |

| Período | Atividade |
|---|---|
| Manhã | Apresentação do espelho e das amostras; E11 nos cenários indicados |
| Tarde | Mudança proposta, medição e comparação das amostras antes × depois |

---

## 9. Critérios de pronto

| # | Critério |
|---|---|
| CP-DTA-01 | 32 cenários com DECISAO e ATUACAO idênticas às da v0dt |
| CP-DTA-02 | Espelho R e L na animação, sincronizado com a sala real, sem nenhum dado da verdade |
| CP-DTA-03 | 3 amostras SVG e `amostras.json` por execução; galeria na página |
| CP-DTA-04 | Métricas de fidelidade com as quatro classes somando a duração |
| CP-DTA-05 | Schemas, testes e integração contínua verdes; tag `v0dta` |
| CP-DTA-06 | Documentação: este plano entregue, README, roteiro (E11) e nota na V2/V3 §3.6 (espelho como visão de RepresentacaoRemota) |

---

## 10. Decisões (aprovadas em 24/10/2026)

Todas as propostas foram aprovadas como estavam.

| ID | Pergunta | Proposta |
|---|---|---|
| DQA-01 | O que é uma "amostra"? | Retrato lado a lado (sala real × espelho) com os dados dos dois lados, em início, meio e fim; o roteiro pode indicar outros instantes |
| DQA-02 | O espelho padrão é o da plataforma (R) ou o do hub (L)? | R por padrão, com chave para L |
| DQA-03 | O espelho mostra os ocupantes? | Não: só uma mancha de presença, sem identidade, posição ou contagem (RN09). Desenhar o morador no espelho seria usar a verdade |
| DQA-04 | O espelho é interativo (clicar na lâmpada do espelho envia comando)? | Não nesta versão: a página só reproduz. Os comandos do app vêm do roteiro e aparecem no espelho. Interação ao vivo exigiria simular no navegador ou um servidor, e fica como opção para uma versão futura |
| DQA-05 | Métricas de fidelidade como requisito ou caracterização? | Caracterização nesta versão |
| DQA-06 | Duração | 1 dia, sem cenário novo além das asserções `espelho` |

---

## 11. Entrega

### 11.1 Critérios de pronto

| Critério | Resultado |
|---|---|
| CP-DTA-01 | As camadas DECISAO e ATUACAO dos 32 cenários, com os dois controladores, são idênticas às da v0dt: o teste compara com assinaturas gravadas na tag `v0dt` (`tests/dados/assinaturas-v0dt.json`) |
| CP-DTA-02 | Cômodo espelho na animação, ao lado da sala real e com o mesmo cursor, com chave plataforma (R) ou hub (L); um teste confere que o lado do espelho não contém nenhum dado da verdade |
| CP-DTA-03 | 3 amostras SVG e `amostras.json` por execução em `saida/<cenário>/<controlador>/42/espelho/`; galeria na aba Cenários, com os mesmos SVG (R e L), download e "ver na animação" |
| CP-DTA-04 | As quatro classes somam a duração em todos os cenários (teste) |
| CP-DTA-05 | 165 testes passam; JSON válidos; página sem erros no navegador e no visualizador embutido |
| CP-DTA-06 | Este plano entregue, README, roteiro (E11), diagrama `espelho-v0dta` e nota na V2/V3 v04 |

### 11.2 Fidelidade do espelho (referência, semente 42)

| Cenário | Fiel | Percepção | Sincronização | Não afirma | Leitura |
|---|---|---|---|---|---|
| N01 | 95,5% | 0,2 s | 0 s | 5,2 s | Só o início, antes da primeira evidência |
| N02 | 66,4% | ~60 s | 0 s | ~5 s | A espera de 60 s após a saída é erro de percepção por projeto (T_apagamento) |
| FN01 | 15,0% | 759,8 s | 0 s | 5,2 s | Morador parado: o hub acha a sala vazia |
| FN05 | 4,7% | 1.424,6 s | 0 s | 5,2 s | Rex dormindo: mesmo efeito |
| F01 | 24,9% | 0,2 s | 0 s | 225,0 s | SP mudo: o hub declara "desconhecida", e o espelho não afirma em vez de errar |
| F03 | 0% | 174,8 s | 0 s | 5,2 s | Lâmpada queimada: o hub acha que está acesa |
| DT05 | 32,1% | 0,2 s | 0 s | 611,3 s | Enlace fora: o espelho não afirma |
| DT07 | 28,9% | 29,9 s | 0 s | 311,3 s | Plataforma fora |
| DT08 | 92,5% | 121,6 s | 0,1 s | 13,3 s | Canal realista: a sincronização quase não aparece; o que pesa é a espera após as saídas |

O resultado mais útil para a aula: com o canal realista, o erro de **sincronização** é de décimos de segundo, enquanto o de **percepção** (sensores, controlador e T_apagamento) é de minutos. O gargalo da fidelidade está na sala, não na rede.

### 11.3 Ajustes feitos na construção (◆)

| Ajuste | Motivo |
|---|---|
| "Não afirma" inclui a ocupação declarada desconhecida | Com o SP mudo (F01) ou no começo de cada cenário, o hub declara que não sabe (RN01). Contar isso como erro de percepção puniria a incerteza honesta |
| Asserções `espelho` só nos cenários DT | Os arquivos da v0 continuam intocados (regressão) |
| Galeria com os SVG gerados pelo Python, embutidos na página | Uma única fonte para os retratos da página e dos relatórios |
