# Plano das versões paralelas V0–V4 e do núcleo Reg10k

**Versão do documento:** v02 | **Data:** 26/10/2026 | **Situação:** aprovado; Fase 1 (nucleo-v1.0) entregue
**Responsável:** Reginaldo Arakaki (EPUSP)
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP
**Base:** repositório `PCS5039_ambiente_reg10k_vCl0` na v1dtb; guia de convenções v03; trilha do plano do ambiente (v02, §2.1)

| Versão | Data | Mudança |
|---|---|---|
| v01 | 26/10/2026 | Primeira versão, com as decisões de 26/10: núcleo e repositórios de versão, V4 como plataforma inicial, nomes |
| v02 | 26/10/2026 | Aprovado (as propostas da §9 valem); acesso ao GitHub resolvido; Fase 1 entregue (§11), com ◆ nos ajustes |

---

## 1. Objetivo

Ter as cinco versões da automação **disponíveis ao mesmo tempo**. Cada uma gera dados reprodutíveis e comparáveis entre si para os artigos em construção, entre eles o do CIACA 2027 sobre o exercício do gêmeo digital na disciplina.

A comparação entre versões só vale se a única diferença entre elas for o objeto estudado: o porte da casa ou o número de residências. Por isso, o motor, o oráculo e o protocolo de medição são **um só**, e cada versão traz só o que é dela.

## 2. Decisões tomadas (26/10/2026)

| ID | Decisão |
|---|---|
| D-PV-01 | **Núcleo único e repositórios de versão finos.** O núcleo tem motor, hub, plataforma, oráculo, página, skills e guia. Cada versão tem a planta, os cenários, os controladores de referência, os experimentos e os dados, e depende do núcleo por tag. |
| D-PV-02 | **V4 é a plataforma digital inicial, para estudo.** Começa com uma residência de cada tipo e cresce junto com as versões: uma casa de 1 cômodo, uma de 2 cômodos e uma com moradores diversos; depois a Casa A e a Casa B. |
| D-PV-03 | **Nomes.** O repositório atual vira o núcleo; as versões ganham repositórios próprios, com o nome da versão. |

## 3. Repositórios

| Repositório | Conteúdo | Depende de |
|---|---|---|
| `reg10k-nucleo` (o atual `PCS5039_ambiente_reg10k_vCl0`, renomeado; o GitHub mantém o endereço antigo redirecionando) | `sim/`, `hub/`, `plataforma/`, `avaliacao/`, `catalogo/` (executor e página), `experimentos/` (novo), `schemas/`, `tools/`, skills, guia, V1 e V2/V3, regressão congelada | — |
| `reg10k-V0` | Ambiente `sala` e os 32 cenários v0 a v0dta | núcleo, por tag |
| `reg10k-V1` | Ambiente `residencia-v1` e os 14 cenários M; a v1dt.1 entra aqui | núcleo, por tag |
| `reg10k-V2` | Casa A (4 cômodos) | núcleo, por tag |
| `reg10k-V3` | Casa B (7 cômodos) e aprendizado do gêmeo | núcleo, por tag |
| `reg10k-V4` | Plataforma com várias residências (frota) | núcleo, por tag; as plantas das outras versões, por tag |

**Estrutura comum de um repositório de versão:**

```
ambiente/        planta(s) em JSON
cenarios/        roteiros/ e esperado/
alunos/          controladores dos alunos (◆ mesmo nome de pacote da v0: `alunos.<grupo>`)
experimentos/    protocolo da versão (famílias, sementes, modos)
dados/           CSV gerados + manifesto (tags do núcleo e da versão, hash dos arquivos)
docs/            plano da versão, resultados, UML da versão
site/            página gerada
nucleo/          ◆ núcleo como submódulo git, fixado numa tag
versao.json      nome, título e tag do núcleo
```

**Regra de estabilidade:** cada versão fixa a tag do núcleo. Dados de artigo são sempre gerados de tags congeladas (núcleo e versão), e cada conjunto publicado recebe uma release, com DOI se desejado (integração GitHub–Zenodo).

## 4. Mapeamento das versões

| Versão | Casa | Origem | Situação | Conceito novo |
|---|---|---|---|---|
| V0 | 1 cômodo (sala), 1 morador e o Rex | v0, v0dt, v0dta | Pronta; falta migrar | Ciclo completo; percepção ≠ verdade; gêmeo e espelho |
| V1 | 2 cômodos e o vão | v1dt (a, b); v1dt.1: mais pessoas e visitante | Pronta; v1dt.1 a fazer | Passagem interna; um controlador por cômodo; ocupação múltipla |
| V2 | Casa A, 4 cômodos | v2dt | A fazer | Escala; parâmetros por cômodo; passagens nas duas direções |
| V3 | Casa B, 7 cômodos | v3dt | A fazer | Modelo comportamental do gêmeo; sugestões com aceite |
| V4 | Plataforma com N residências | nova | A fazer | Várias residências no gêmeo remoto; isolamento entre residências; carga e atualidade por residência |

**Uma variável por vez (P1), entre as versões e dentro delas.**
- V0 → V1 → V2 → V3 muda só o porte da casa.
- Dentro de uma versão, cada incremento muda uma dimensão. Por exemplo, a v1dt.1 muda só os moradores.
- A V4 não muda casa nenhuma: reúne as casas já validadas. A diferença dela é a plataforma atender várias residências.

### 4.1 V4: plataforma inicial

| Etapa | Residências | Disponível quando |
|---|---|---|
| V4.0 | R1: casa de 1 cômodo (planta da V0) · R2: casa de 2 cômodos (planta da V1) · R3: casa de 2 cômodos com moradores diversos | Núcleo com várias residências e a v1dt.1 prontos |
| V4.1 | + Casa A | V2 pronta |
| V4.2 | + Casa B | V3 pronta |

O que a V4 estuda, com rastreio para a V2/V3:
- **Isolamento entre residências:** nenhuma evidência, estado ou comando de uma residência aparece em outra. É a nova invariante OR-15, que estende a OR-13 da casa para a plataforma (RN de privacidade e papéis da V1).
- **Roteamento:** comando remoto e preferência vão só à residência certa (extensão de RN-DT-09).
- **Atualidade e divergência por residência**, com queda de rede numa residência e as outras normais.
- **Carga da plataforma:** eventos por segundo e tamanho das filas por residência. É um ensaio inicial, não a escala das 10.000 casas, e os números saem com a ressalva de que são simulação.
- **Visão do titular e do gestor:** cada titular só vê a sua residência; o gestor vê indicadores agregados, sem os hábitos individuais (V1 §2.1).

## 5. Protocolo de experimentos (módulo `experimentos/` no núcleo)

Mesmas **famílias de cenários** em todas as versões, instanciadas pela planta de cada uma:

| Família | O que mede | Exemplo na V0 | Exemplo na V1 |
|---|---|---|---|
| F1 Entrar e sair | Atraso para acender e desperdício na saída | N01, N02 | M01, M02 |
| F2 Permanência parada | Escuro com ocupante (falso negativo) | FN01 | M05 |
| F3 Passagem sem entrar | Acendimento indevido (falso positivo) | FP01 | M03 |
| F4 Falha de dispositivo | Detecção, alerta e degradação | F01–F06 | M07, M08 |
| F5 Queda de rede | Atualidade, divergência e reconciliação | DT05, DT07 | M13 |
| F6 Comando remoto e preferência | Validade, idempotência e roteamento | DT01–DT04 | M11, M12 |
| F7 Espelho | Fidelidade do gêmeo ao longo do tempo | Amostras do espelho em DT01–DT12 | M14 |

- **Sementes:** 30 por cenário, nos modos ideal e realista e no canal realista.
- **Saída:** um CSV por versão, com uma linha por execução: `versao, tag_nucleo, tag_versao, residencia, n_comodos, n_moradores, familia, cenario, controlador, semente, modo` mais as métricas do oráculo. O CSV vem com um manifesto (tags e hash dos arquivos), para o dado do artigo ser reprodutível.
- **Gerador de família por planta** (◆ entra com a V2, que é a primeira a precisar dele): dada a planta, o gerador cria os roteiros de F1 a F7 nos cômodos e passagens dela. A V2 e a V3 nascem com a bateria completa, sem escrever os cenários um a um.
- **Ressalva P7** em todo resultado: simulação, não medição.

## 6. Mudanças no núcleo

| ID | Mudança | Necessária para |
|---|---|---|
| N1 | ◆ Lançador `reg10k.py` e núcleo como submódulo; executor, validação, assinaturas e experimentos aceitam a raiz de uma versão (`--raiz` ou `REG10K_RAIZ`) | Todas as versões |
| N2 | Regressão congelada: os 46 cenários atuais e as 92 assinaturas ficam no núcleo como dados de teste. Um teste de compatibilidade roda cada versão na tag fixada. | Garantia de comparabilidade |
| N3 | Página genérica: passagens em qualquer parede e planta de N cômodos com rolagem e zoom | V2, V3 |
| N4 | `experimentos/`: famílias, gerador por planta, CSV e manifesto | Dados dos artigos |
| N5 | Novos tipos de morador (criança, idoso, visitante) e ocupação múltipla (vêm da v1dt.1) | V1 (v1dt.1), V4 |
| N6 | Plataforma com várias residências: `Plataforma` com uma representação por residência, canal por hub, OR-15, página da frota | V4 |
| N7 | Aprendizado do gêmeo (modelo comportamental e sugestões com aceite) | V3 |

A abertura de cada mudança segue a skill `incremento-simulacao`. Mudança no núcleo ganha tag `nucleo-vX.Y`, e cada versão sobe de tag quando quiser. Nenhuma versão é obrigada a acompanhar o núcleo.

## 7. Ordem e paralelismo

| Fase | O que | Em paralelo? | Estimativa |
|---|---|---|---|
| 0 | Acesso ao GitHub; publicar a v1dtb no repositório atual; identidade dos commits | — | ✔ 26/10 |
| 1 | Núcleo: N1, N2, N4 e a parte mínima de N3; tag `nucleo-v1.0` | Não (é a base) | ✔ 26/10 (§11) |
| 2a | V0 e V1: migrar os cenários; mesmas assinaturas, como prova de que a migração não mudou nada | Sim | 1 dia |
| 2b | V1: v1dt.1, com N5 no núcleo | Sim | 2 dias |
| 2c | V2: Casa A, com o resto de N3 | Sim | 2 dias |
| 2d | V4.0: N6 no núcleo, com R1, R2 e R3 | Sim; depende de 2b para R3 | 2–3 dias |
| 3 | V3: Casa B e N7 | Depois de 2c | 3 dias |
| 4 | Rodada de experimentos com tags congeladas; release dos dados | — | 1 dia por artigo |

"Em paralelo" quer dizer que as versões ficam disponíveis ao mesmo tempo e não dependem umas das outras. A construção continua passando por uma revisão de cada vez. As estimativas valem para o meu ritmo de construção; cada versão nova tem a sua parada de aprovação.

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Mudança no núcleo altera, sem ninguém notar, o resultado de uma versão já usada em artigo | Versão fixa a tag; teste de compatibilidade (N2); dados só de tags congeladas |
| Seis repositórios para uma pessoa manter | Repositórios de versão só com dados; CI igual em todos, gerada pelo núcleo; skill com a rotina |
| Escopo da V4 crescer rumo às 10.000 casas | V4.0 limitada a 3 residências; escala vira estudo próprio, com a ressalva P7 |
| Turmas usando o repositório antigo durante a migração | O GitHub redireciona o endereço antigo; a página e o roteiro dos alunos apontam o repositório da versão da semana |

## 9. Decisões a confirmar

| ID | Pergunta | Proposta |
|---|---|---|
| DQ-PV-01 | Composição da Casa A e da Casa B | Casa A: sala, cozinha, quarto e banheiro, com corredor curto. Casa B: Casa A + 2 quartos + área de serviço (7). Dimensões típicas, um SP e um atuador por cômodo, um SA por passagem (H04 da V1). |
| DQ-PV-02 | Moradores da R3 (casa diversa da V4) | Planta da V1, com 2 adultos, 1 criança, 1 idoso, o Rex e visitante ocasional. É a mesma diversidade da v1dt.1, para não haver tipo de morador que só exista na V4. |
| DQ-PV-03 | Onde os alunos entregam os controladores | No repositório da versão da semana (`controladores/alunos/`). O núcleo não recebe código de aluno. |
| DQ-PV-04 | Licença, necessária para release e DOI | Código MIT; dados e documentos CC BY 4.0 |
| DQ-PV-05 | Conta dona dos repositórios | ReginaldoArakaki; ver §10 |
| DQ-PV-06 | Os documentos da plataforma (V1, V2/V3) ficam no núcleo? | Sim, em `docs/plataforma/`; cada versão cita a revisão que usa |

Sem objeção, as propostas valem.

## 10. Acesso ao GitHub e identidade dos commits

**Situação em 26/10:** resolvido. A conta ReginaldoArakaki está ligada ao Claude com escrita no repositório. A sessão publica commits no `main`, mas o ambiente recusa tags (403): as tags ficam com o responsável. A sequência v0dta → v1dtb foi publicada com o autor novo. O texto abaixo fica como registro.


- **Identidade dos commits:** autor `ReginaldoArakaki <reginaldo.arakaki@poli.usp.br>`. Os commits ainda não publicados (v0dta a v1dtb) são refeitos com essa identidade antes de ir ao GitHub.
- **Acesso de escrita:** a conta do GitHub ligada ao Claude é a **RegUsp**, que pode publicar nos repositórios RegUsp, mas não nos da conta ReginaldoArakaki. Há dois caminhos:
  1. Na conta ReginaldoArakaki, convidar a RegUsp como colaboradora com permissão de escrita, em cada repositório (Settings → Collaborators), e aceitar o convite pela conta RegUsp.
  2. Ligar ao Claude a conta ReginaldoArakaki: nas Configurações do claude.ai, em Conectores, reconectar o GitHub com essa conta.
- **Criação dos repositórios:** a sessão não cria repositórios. Você cria os cinco repositórios vazios e renomeia o atual; a partir daí, as publicações podem ser feitas daqui.

## 11. Entrega da Fase 1: nucleo-v1.0

### 11.1 O que entrou

| ID | Entrega |
|---|---|
| N1 | `catalogo.executar.configurar_raiz()`: a pasta de uma versão traz `cenarios/`, `ambiente/`, `alunos/`, `saida/`, `site/` e `versao.json`; o que faltar cai no núcleo. `--raiz` em `catalogo`, `sim`, `validar`, `assinaturas` e `experimentos`; variável `REG10K_RAIZ`. Lançador `reg10k.py` para rodar o núcleo de dentro de um repositório de versão. Título e subtítulo da página vêm da versão. Licença MIT no núcleo |
| N2 | `tools/nova_versao.py` monta um repositório de versão (ambientes, cenários, grupo de exemplo, famílias, README, CI com submódulo, licenças MIT e CC BY 4.0). Teste: a V1 montada e rodada de fora tem as **mesmas 28 assinaturas** do núcleo; a V0, as mesmas 64 |
| N3 (mínimo) | Página com passagem interna em parede vertical **ou horizontal** e porta externa nas duas orientações; ocupantes lidos do ambiente do cenário. Ambiente de teste com 4 cômodos (`tests/dados/residencia-teste-4.json`, não é a Casa A): as 14 invariantes passam |
| N4 | `experimentos/`: famílias F1–F7, mapeamento padrão do conjunto de regressão, execução com sementes e modos, processos em paralelo, CSV com uma linha por execução e manifesto (commits, sementes, hash das entradas, ressalva P7) |
| Schemas | Campo `versao` dos roteiros e das métricas aceita qualquer nome da trilha (`v2dt`, `v1dt.1`…), e não mais uma lista fechada |

### 11.2 Verificação

- 210 testes em Python 3.12 e 3.9; regressão: 92 assinaturas iguais às da v1dt.
- Catálogo com 30 sementes sem problemas; JSON válidos.
- Página do núcleo, da V1 montada e do teste de 4 cômodos abertas no navegador em todas as execuções, sem erro; página do núcleo também em iframe com sandbox.
- Rodada completa de experimentos do núcleo: 1.380 execuções (46 cenários, 30 sementes, referência) em 47 s com 4 processos.

### 11.3 Achado: asserções com janela de tempo absoluta

Na rodada de 30 sementes, 1 de 1.380 execuções falhou um requisito: o M01 com a semente 25. O morador anda ao acaso antes de ir ao vão e, nessa semente, cruza aos 44,1 s, quando a asserção A1 exige a cozinha acesa entre 40 e 44 s. O controlador não errou: o atraso percebido foi de 0,4 s. As janelas absolutas dos esperados foram calibradas para a semente 42.

**Consequência para os artigos:** nos experimentos com várias sementes, a taxa de requisitos atendidos mistura limitações do controlador com a fragilidade das janelas. A análise deve usar as métricas (atraso percebido, desperdício por saída), e os cenários gerados para a V2 e a V3 devem ter janelas relativas ao evento (por exemplo, "até 4 s depois do cruzamento"). Os esperados das versões entregues não mudam.

### 11.4 Ajustes feitos na construção (◆)

| Item | Motivo |
|---|---|
| Núcleo como **submódulo git** fixado na tag, em vez de pacote instalado com `pip` | O executor usa recursos que ficam fora dos pacotes Python (schemas, modelo da página, diagramas). Com o submódulo, o núcleo inteiro fica na versão fixada, e o commit exato vai para o manifesto |
| Pasta `alunos/`, em vez de `controladores/`, nos repositórios de versão | Os controladores dos alunos continuam com o mesmo nome de pacote (`alunos.<grupo>`), sem mudar o que já foi escrito |
| Gerador de cenários por planta adiado para a V2 | É a primeira versão que precisa dele; a V0 e a V1 já têm os cenários |
| Schemas sem lista fechada de versões | Cada versão nova teria de mudar o núcleo só para ser aceita |

### 11.5 Próximo passo

Fase 2a: criar `reg10k-V0` e `reg10k-V1` (repositórios vazios, criados pelo responsável), montá-los com `tools/nova_versao.py --submodulo`, gravar as assinaturas de cada um e publicar. Em seguida, em paralelo: v1dt.1 (V1), Casa A (V2) e V4.0.
