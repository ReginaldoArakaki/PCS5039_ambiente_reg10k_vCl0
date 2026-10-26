# Guia de convenções — projeto Reg10k e ambiente de simulação PCS5039

**Documento:** guia-convencoes.md
**Versão:** 04 | **Data:** 26/10/2026 (v01 a v03 de 25/10/2026)
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP
**Coordenação:** Reginaldo Arakaki (EPUSP)
**Base:** prática consolidada nas versões v0, v0dt e v0dta do ambiente e nas versões v01 a v04 da V1 e da V2/V3.
**Situação:** em uso. Vale para os documentos da plataforma, os planos de incremento, o código do ambiente e as skills.

---

## Histórico de versões

| Versão | Data | Alterações |
|---|---|---|
| 01 | 25/10/2026 | Primeira versão |
| 02 | 25/10/2026 | Com a v1dt: ambientes (`sala` e `residencia-v1`), prefixos RN-V1 e M, campo `comodo` no registro e nas asserções, chave de intenção por cômodo |
| 04 | 26/10/2026 | Com a nucleo-v1.0: núcleo e repositórios de versão (§2), publicação direta no `main` e tags pelo responsável (§9), autor dos commits |
| 03 | 25/10/2026 | Com a v1dtb: diagrama com sufixo de versão quando a estrutura muda, nomes de classe da V2 com sinônimos no código, ajuste pequeno sem rodada de dúvidas (§6) |

---

## Sumário

1. Princípios
2. Versões do ambiente e dos documentos
3. Identificadores
4. Marcas de origem e de construção
5. Estrutura dos documentos
6. Ciclo de um incremento
7. Cenários, asserções e invariantes
8. Código, registro e regressão
9. Publicação
10. Estilo de escrita

---

## 1. Princípios

| # | Princípio | Consequência prática |
|---|---|---|
| P1 | Uma variável por vez | Cada incremento muda uma dimensão (porte da casa, gêmeo, espelho…). O que já existia vira regressão |
| P2 | A verdade é só do oráculo | O controlador, o gêmeo e o espelho nunca leem a camada VERDADE (OR-06, DTA-03) |
| P3 | Determinação | A mesma semente produz o mesmo registro, byte a byte. Aleatoriedade sempre por gerador nomeado |
| P4 | A página só reproduz | Toda lógica fica no motor Python; a página HTML lê o catálogo e desenha |
| P5 | Proposta antes de pergunta | Toda dúvida vem com uma proposta padrão. Sem objeção, a proposta vale |
| P6 | Plano antes de código; entrega com o que mudou | O plano é aprovado; a entrega diz o que saiu diferente do plano e por quê |
| P7 | Simulação não é medição | Resultados de simulação são sempre apresentados como tais, nunca como desempenho de sistema real |
| P8 | Incerteza honesta não é erro | "Desconhecido" ou "desatualizado" declarados nunca contam como acerto nem como erro de percepção (RN01) |

---

## 2. Versões do ambiente e dos documentos

### 2.1 Ambiente de simulação

O número acompanha o **porte da automação**. Os sufixos indicam o que foi acrescentado sobre esse porte.

| Elemento | Significado | Exemplo |
|---|---|---|
| `vN` | Porte: 0 = 1 cômodo; 1 = 2 cômodos e passagem; 2 = Casa A (4 cômodos); 3 = Casa B (7 cômodos) | `v0`, `v1` |
| `dt` | Gêmeo digital (DTReg10k-L e DTReg10k-R) integrado | `v0dt` |
| letra final | Ajuste de uma versão já entregue, sem mudar o porte | `v0dta` (cômodo espelho) |
| `.n` | Ampliação no mesmo porte (mais pessoas, visitante) | `v1dt.1` |

Cada entrega recebe uma **tag git** com o nome da versão. A trilha vigente é: v0 → v0dt → v0dta → v1dt → v1dt.1 → v2dt → v3dt.

### 2.2 Documentos

| Elemento | Regra |
|---|---|
| Versão do documento | Dois dígitos: `v01`, `v02`… no nome do arquivo e no cabeçalho |
| Plano de incremento | `ambiente-simulacao-<versão>.md`. v01 = plano para aprovação; v02 = entregue (o mesmo arquivo, atualizado) |
| Documentos da plataforma | `v1-business-drivers-plataforma-reg10k-vNN` e `V2 e V3 requisitos funcionais e não funcionais plataforma reg10k-vNN`, em .md e .docx |
| No repositório | `docs/plataforma/` guarda só a versão vigente (o histórico fica no git) |
| Histórico | Todo documento a partir da v02 tem a tabela "Histórico de versões" logo após o cabeçalho |

---

### 2.1 Núcleo e repositórios de versão (desde a nucleo-v1.0)

| Repositório | Guarda | Tag |
|---|---|---|
| Núcleo (este) | Motor, hub, plataforma, oráculo, página, schemas, experimentos, skills, guia, V1 e V2/V3; conjunto de regressão | `nucleo-vX.Y` |
| `reg10k-V0` … `reg10k-V4` | Planta, cenários, alunos, `experimentos/familias.json`, `dados/`, `versao.json`; núcleo em `nucleo/` (submódulo) | Nome da versão (`v1dt.1`, `v2dt`…) |

Mudança de motor, oráculo ou página é feita no núcleo; cada versão sobe a tag do núcleo quando quiser. Dado de artigo só sai de tags congeladas (o manifesto registra os commits).

---

## 3. Identificadores

### 3.1 Plataforma (V1 a V3)

| Prefixo | Elemento | Formato | Documento |
|---|---|---|---|
| BD | Direcionador de negócio | BD01 | V1 |
| MP, MT | Macroprocesso e governança | MP1–MP4, MT | V1 |
| RN | Regra de negócio | RN01 | V1 |
| RNP | Requisito de negócio da plataforma | RNP-MP3-02 | V1 |
| CV | Cenário de validação | CV04 | V1 |
| PS | Parâmetro de serviço | PS01 (validade do comando, 30 s) | V1 |
| A, D, I | Decisão aprovada, dúvida, interpretação | A13, D09, I03 | V1 e V2/V3 |
| RF | Requisito funcional | RF-<módulo>-nn: RF-SYN-04 | V2/V3 |
| RNF | Requisito não funcional | RNF-<característica>-nn: RNF-DES-01 | V2/V3 |
| INV | Invariante de informação (OCL) | INV-14 | V2 |
| OC, I- | Objeto computacional e interface | OC-05, I-CMD | V3 |
| CF | Cenário funcional | CF04 | V3 |
| PD | Pendência da modelagem | PD08 | V2/V3 |
| RS | Refinamento trazido pela simulação | RS-07 | V2/V3 §3.6 |
| R | Referência | R13 (V1 v02), R15 (plano v0dt), R16 (plano v0dta) | Todos |

Módulos de RF: ADE, KIT, COM, OPR, SYN, ACO, GOV. Características de RNF (ISO/IEC 25010:2023): DES, CON, SEG, PRI, USA, EVO, CMP, LEG.

### 3.2 Ambiente de simulação

| Prefixo | Elemento | Formato |
|---|---|---|
| RN-I0, RN-DT, RN-V1 | Regra do incremento | RN-I0-05, RN-DT-09, RN-V1-01 (a regra cita a RN da V1 de origem) |
| DI, DT-, DTA- | Decisão de orientação do plano | DT-02, DTA-03 |
| DQ, DQA | Decisão a confirmar no plano (com proposta) | DQ-04, DQA-04 |
| PI | Pendência do incremento | PI-01 |
| CP | Critério de pronto | CP-DT-05, CP-DTA-01 |
| OR | Invariante do oráculo | OR-01 a OR-14 (numeração contínua entre versões) |
| E | Exercício dos alunos | E1–E11 (numeração contínua entre versões) |
| Cenários | Prefixo + dois dígitos | N, FP, FN, F (v0); DT (gêmeo, v0dt); M (residência com vários cômodos, v1dt); o tipo fica no campo `tipo` |
| Asserções | A1, A2… (comportamento); E1… (espelho); INV (invariantes) | dentro de cada `esperado/<ID>.json` |

Um identificador nunca é reaproveitado com outro significado. Item removido some do documento seguinte, com nota no histórico.

---

## 4. Marcas de origem e de construção

| Marca | Significado | Onde |
|---|---|---|
| **A** | Aprovado (decisão do responsável) | Tabelas de requisitos, regras, decisões |
| **F** | Fonte (vem de documento de referência) | Idem |
| **P** | Proposta (aguarda aprovação) | Idem |
| **N** | Nova nesta versão, sem correspondente na fonte | Idem |
| **I** | Interpretação (leitura nossa de algo ambíguo) | Idem |
| ◆ | Ajuste feito na construção, diferente do plano aprovado | Plano entregue (v02) e lista final de ajustes |

---

## 5. Estrutura dos documentos

### 5.1 Cabeçalho (todos)

```
# <Título>

**Documento:** <nome do arquivo>
**Versão:** NN | **Data:** dd/mm/aaaa (versões anteriores, se houver)
**Disciplina:** PCS5039 — Engenharia de Software Orientada a IoT (EPUSP)      ← planos de incremento
**Linha de pesquisa:** Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP
**Base:** <versões e documentos de que este depende>
**Situação:** plano para aprovação | entregue | modelagem para validação | em uso
```

Depois: `## Histórico de versões` (a partir da v02), `## Sumário`, seções numeradas e `## Referências` por último.

### 5.2 Plano de incremento

| § | Seção | Conteúdo |
|---|---|---|
| 1 | Decisões e nomenclatura | Decisões de orientação (DT-, DTA-) e o lugar na trilha |
| 2 | Objetivo e posição na trilha | O que o aluno passa a ver; conceitos novos |
| 3 | Escopo e rastreabilidade | Dentro × fora (com a versão em que entra); RF, RNF, INV, CF, CV realizados |
| 4 | Arquitetura | Componentes (Mermaid), fluxos, mudança no contrato do controlador |
| 5 | Regras e parâmetros | RN-xx com origem; parâmetros com valor padrão e fonte |
| 6–7 | Elementos novos | Canal, app, camadas do registro etc. |
| 8 | Cenários | Regressão + novos, com esperado e rastreio |
| 9 | Métricas e invariantes | Definição e limite; OR novas com a base V2 |
| 10 | Página | Ajustes por aba |
| 11 | Exercícios e cronograma | E-n, técnica, cenários-alvo; dias |
| 12 | Critérios de pronto e documentação | CP-xx; documentos atualizados na entrega |
| 13 | Decisões a confirmar | DQ-xx, cada uma com proposta |

Na entrega (v02): Situação "entregue", histórico, ◆ nos itens ajustados, seção de resultados (critérios de pronto, medições da referência com a ressalva P7) e tabela "Ajustes feitos na construção".

### 5.3 Rodada de dúvidas

Tabela com ID, pergunta, opções e **proposta**, agrupada por tema. As dúvidas que bloqueiam vêm primeiro. A rodada termina com "sem objeção, as propostas valem".

---

## 6. Ciclo de um incremento

| Etapa | Saída | Quem aprova |
|---|---|---|
| 1. Avaliação | Recomendação curta (o que entra, o que fica de fora, por quê) | Responsável |
| 2. Dúvidas | Rodada de dúvidas com propostas | Responsável (ou silêncio = propostas) |
| 3. Plano | `ambiente-simulacao-<versão>.md` v01 | Responsável |
| 4. Construção | Código, cenários, schemas, página, testes | — |
| 5. Verificação | Testes, catálogo, validação JSON, página no navegador e em iframe, regressão por assinatura | — |
| 6. Entrega | Plano v02, V2/V3 nova versão (se houver RS), README, roteiro, patch testado em cópia limpa | Responsável publica |

Duração de referência: incremento novo, 2 dias; ajuste (letra), 1 dia.

Ajuste pequeno (letra) pedido pelo responsável com escopo claro pode pular as etapas 2 e 3: o pedido vale como aprovação, e o plano sai direto em v02 (entregue), com o motivo do ajuste na §1.

---

## 7. Cenários, asserções e invariantes

| Regra | Detalhe |
|---|---|
| Roteiro | `cenarios/roteiros/<ID>.json`: id, versao, titulo, tipo, modo, duracao_ms, descricao, comportamento_ideal, comportamento_referencia, estado_inicial, acoes, falhas, requisitos, regras; opcionais: ambiente, rede, controle, controle_comodos, amostras_ms |
| Ambiente | `cenarios/sala.json` (um cômodo, formato da v0) ou `cenarios/residencia-*.json` (cômodos e passagens); o roteiro indica com `ambiente` |
| Cômodo nas asserções | `"comodo"` em `entao` escolhe o cômodo; sem ele, métricas valem para a residência e os demais tipos, para o primeiro cômodo |
| Esperado | `cenarios/esperado/<ID>.json`: asserções dado/quando/então com `nivel` |
| REQUISITO | Vale para qualquer controlador; falhar reprova |
| CARACTERIZACAO | Descreve a referência, inclusive limitações; em outro controlador, "difere" é informação |
| Regressão | Roteiros e esperados de versões anteriores **não são editados**. Asserções novas sobre cenários antigos vão para os testes |
| Invariantes | OR-nn verificadas em toda execução; cada uma cita a INV ou a RN de base. OR que depende de condição informa `aplica: false` quando não se aplica |
| Modos | IDEAL valida a lógica; REALISTA tem distribuição em 30 sementes no catálogo |

---

## 8. Código, registro e regressão

| Regra | Detalhe |
|---|---|
| Camadas do registro | VERDADE, PERCEPCAO, DECISAO, ATUACAO, ESTADO, SISTEMA, REDE, PLATAFORMA. Camada nova só por decisão de plano. Eventos de um cômodo levam `comodo`; evidências levam `comodos` (a quem foram entregues) |
| Chaves de intenção | `I-<boot>-<n>` com um cômodo; `I-<cômodo>-<boot>-<n>` com vários |
| Nomes | Domínio em português, como na V2 (`Evidencia`, `Intencao`, `ResultadoAtuacao`) |
| Contrato do controlador | `iniciar`, `ao_evento`, `ao_tick`, `estado`. Evidência nova entra pelo `ao_evento`; o contrato não muda sem decisão explícita |
| Geradores aleatórios | Um por componente, nomeado (`random.Random(f"{semente}:{roteiro}:{nome}")`) |
| Regressão por assinatura | Antes de mexer no motor: `python tools/assinaturas.py gravar <versão>`. O teste compara DECISAO e ATUACAO de todos os cenários e controladores |
| Python | 3.9 a 3.13; `from __future__ import annotations` em todo módulo com tipos |
| Testes | `python -m pytest -q`; todo defeito que o oráculo deve pegar tem um teste com controlador defeituoso ou registro alterado |

---

## 9. Publicação

| Passo | Comando ou regra |
|---|---|
| Commit | Autor: `ReginaldoArakaki <reginaldo.arakaki@poli.usp.br>`; mensagem com resumo e lista do que entrou |
| Publicação | A sessão do Claude tem escrita no repositório e publica o commit no `main` depois da verificação. **Tags não passam** pelo ambiente da sessão (erro 403): o responsável cria a tag com o hash informado na entrega e a envia |
| Patch (alternativa) | `git format-patch --binary -1`, quando a sessão não tiver acesso de escrita |
| Verificação | Testes, assinaturas e catálogo no clone publicado antes do envio; com patch, num clone limpo com `git am` |
| Instruções ao responsável | Pasta local `C:\Users\Reginaldo\Documents\GitHub\PCS5039_ambiente_reg10k_vCl0`; `git pull`, `git tag <versão> <hash>`, `git push origin <versão>` |
| Projeto no Claude | Planos e documentos em md salvos em `claude/` |
| Código consolidado | `python tools/consolidar.py --ref <tag>` |

---

## 10. Estilo de escrita

- Português do Brasil, frases curtas, voz ativa. Termos técnicos em português quando houver equivalente estabelecido.
- Tabelas para tudo o que se compara ou se rastreia; prosa para o raciocínio.
- Cada número diz de onde vem; resultado de simulação traz a ressalva P7.
- Diagramas em Mermaid; fontes em `docs/uml/*.mmd`, SVG gerado ao lado.
- Diagrama cuja estrutura muda numa versão ganha o sufixo dela (`classes-v1dt`); o anterior fica, com a versão no título. Nomes de classe seguem a V2 (`Comodo`, `EstadoComodo`); nomes antigos do código ficam como sinônimos enquanto houver controladores de alunos que os usam.
- Na resposta ao responsável: o que saiu, o que mudou do plano, como publicar e o próximo passo, sem recapitular o processo.
