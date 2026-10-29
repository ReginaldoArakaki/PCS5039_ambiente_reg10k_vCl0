---
name: incremento-simulacao
description: Planejar, construir, verificar e entregar um incremento ou ajuste do ambiente de simulação Reg10k da PCS5039 (v1dt, v0dta, v1dt.1…), do plano à entrega com patch.
---

# Incremento do ambiente de simulação Reg10k (PCS5039)

Linha de pesquisa: Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP, coordenação de Reginaldo Arakaki.
Repositório: `ReginaldoArakaki/PCS5039_ambiente_reg10k_vCl0`. Convenções: `docs/guia-convencoes.md` (ler antes de começar; este roteiro não as repete).

Use esta skill quando o responsável pedir um novo incremento (novo porte da casa, gêmeo, mais ocupantes) ou um ajuste de versão entregue (sufixo de letra). O ciclo tem seis etapas e duas paradas para aprovação.

## Etapa 0 — Situar-se (sem falar com o responsável)

1. Ler o guia de convenções, o README e o plano entregue da última versão (`docs/ambiente-simulacao-<versão>.md`).
2. Conferir no git a última tag e se há patches ainda não publicados (o repositório público pode estar atrás do local). Conferir também se cada tag pública aponta para o commit certo. Se houver pendências, a entrega lista os patches na ordem.
3. Ler na V2/V3 vigente (`docs/plataforma/`) os RF, RNF, INV e CF que o incremento vai tocar.
4. Rodar `python -m pytest -q` e `python -m catalogo --sem-site --sementes 0` para partir de um estado verde.

## Etapa 1 — Avaliação (quando o responsável pergunta "qual caminho?")

Resposta curta: recomendação, por quê (com evidência do projeto), o contra-argumento e a mitigação. Aplicar o princípio "uma variável por vez": se o pedido muda duas dimensões, propor a ordem.

## Etapa 2 — Rodada de dúvidas (quando o escopo tem ambiguidades)

- Tabela por tema: ID (DQ-nn ou DQx-nn), pergunta, opções, **proposta**. Bloqueantes primeiro.
- Encerrar com "sem objeção, as propostas valem". Não esperar resposta para dúvidas de baixo custo de reversão.

## Etapa 3 — Plano para aprovação

Arquivo `ambiente-simulacao-<versão>.md`, v01, situação "plano para aprovação", com a estrutura do guia §5.2. Obrigatórios:

- **Regressão declarada:** quais cenários anteriores continuam e com que garantia (assinatura das decisões, roteiros intocados).
- **Rastreabilidade:** cada regra RN-xx cita a RN da V1; cada OR nova cita a INV ou a RN de base; cada cenário cita RF, CF ou CV.
- **Dentro × fora**, com a versão em que cada item fora entra.
- **Diferenças didáticas:** o que o aluno passa a ver e qual exercício (E-n) usa isso.
- **Decisões a confirmar**, cada uma com proposta.

Salvar no projeto Claude (`claude/`) e enviar o arquivo. Na resposta, destacar a decisão que mais pede atenção.

## Etapa 4 — Construção

Ordem, sempre:

1. **Gravar a assinatura da versão de partida** antes de tocar no motor: `python tools/assinaturas.py gravar <versão-de-partida>`. Criar um ramo git com o nome da nova versão.
2. **Núcleo** (sim/, hub/, plataforma/): mudança mínima; contrato do controlador intocado, salvo decisão do plano. Geradores aleatórios nomeados por componente.
3. **Oráculo** (avaliacao/): métricas e OR novas; OR condicional informa `aplica: false`.
4. **Cenários novos**, gerados por script (roteiro + esperado), com asserções de nível REQUISITO para o que vale para qualquer controlador e CARACTERIZACAO para o comportamento da referência. **Não editar roteiros nem esperados de versões anteriores**: asserções novas sobre cenários antigos vão para os testes.
5. **Schemas** (schemas/): todo campo novo de roteiro, esperado, evento, métrica e sala.
6. **Página** (catalogo/template.html, site.py, modelo.json): a página só desenha o que o motor gerou.
7. **UML** (docs/uml/*.mmd → SVG com mmdc e `docs/uml/config.json`). Além dos diagramas novos, **rever os que já existem** (classes, casos de uso, componentes): se a estrutura mudou, criar o diagrama com o sufixo da versão (`classes-v1dt.mmd`) e deixar o antigo como registro da versão anterior, com título que diga a versão; se só cresceu, atualizar no lugar. Registrar cada diagrama em `catalogo/modelo.json`. Generalização (classe geral, como `Comodo`) segue a V2: subclasse só quando o tipo tem atributos ou regras próprias; senão, instâncias da classe geral.
8. **Testes:** regressão por assinatura, invariantes com controlador defeituoso ou registro alterado (a OR tem de falhar quando deve), determinismo por semente.

Durante a construção, anotar cada desvio do plano: vira ◆ na entrega. Desvio que muda uma decisão aprovada exige avisar o responsável antes de seguir.

## Etapa 5 — Verificação (todos os itens, sempre)

- [ ] `python -m pytest -q` verde em 3.12, e numa versão antiga (3.9) quando houver código novo com tipos.
- [ ] `python tools/assinaturas.py comparar <versão-de-partida>` sem "MUDOU" nem "SUMIU" (salvo mudança aprovada no plano).
- [ ] `rm -rf saida && python -m catalogo --sementes 30` sem problemas; `python -m catalogo.validar` sem erros.
- [ ] Página aberta no navegador (Playwright) em todas as abas e cenários, sem erro no console, e também dentro de iframe `srcdoc` com sandbox.
- [ ] Capturas das telas novas examinadas a olho (sobreposição, rótulos cortados, legendas).
- [ ] Resultados da referência conferidos contra a intuição: número estranho é investigado antes da entrega.
- [ ] Diagramas coerentes com a versão: nenhum diagrama vigente usa a estrutura antiga (por exemplo, `grep -l "class Sala" docs/uml/*.mmd` depois de a casa ganhar cômodos) e a contagem de invariantes nos componentes é a atual.

## Etapa 6 — Entrega

1. **Plano entregue**: o mesmo arquivo em v02: situação "entregue", histórico, ◆ nos itens ajustados, resultados (critérios de pronto e medições da referência com a ressalva "simulação, não medição") e a tabela "Ajustes feitos na construção" com o motivo de cada um.
2. **V2/V3**: se a simulação trouxe refinamento do modelo, nova versão com RS-nn na §3.6, pendência PD para a V1 quando couber, referência R-nn ao plano; .md e .docx.
3. **README** e **roteiro dos alunos** (exercício E-n novo, com pesos).
4. **Commit** com autor `ReginaldoArakaki <reginaldo.arakaki@poli.usp.br>`; publicar no `main` (ou **patch** `git format-patch --binary -1` sem acesso de escrita).
5. **Verificar antes de publicar**: testes, assinaturas e catálogo no clone que será enviado; com patch, num clone limpo com `git am`.
6. **Salvar no projeto Claude** o plano entregue e a V2/V3 em .md (se o projeto estiver cheio, avisar e não apagar nada).
7. **Enviar**: patch, página `simulacao-reg10k-<versão>.html`, documentos.

Resposta final ao responsável, nesta ordem e sem recapitular o processo: o que saiu (uma frase), comandos de publicação (`git pull` e `git tag <versão> <hash>` + `git push origin <versão>`, ou os `git am` dos patches pendentes, na pasta `C:\Users\Reginaldo\Documents\GitHub\PCS5039_ambiente_reg10k_vCl0`), o que o aluno passa a ver, o que mudou do plano (◆), o achado mais útil para a aula e o próximo passo combinado.

## Armadilhas conhecidas

- Publicação: com acesso de escrita, a sessão publica o commit no `main`; as **tags não passam** (403) e ficam com o responsável, com o hash na entrega. Sem acesso, entrega por patch. Nunca dizer que publicou o que não subiu: conferir com `git ls-remote origin`.
- Desde a nucleo-v1.0, motor, oráculo e página mudam no núcleo; planta, cenários e dados mudam no repositório da versão (guia §2.1). Asserções com janela de tempo absoluta valem para a semente 42; nos experimentos com várias sementes, prefira métricas ou janelas relativas a um evento.
- Tag criada depois de um `git am` que falhou aponta para o commit anterior: conferir com `git ls-remote --tags origin`.
- Mermaid: `;` quebra diagramas de sequência; setas "→" em rótulos de flowchart podem não renderizar.
- Página: `history.replaceState` falha em iframe `srcdoc`; todo download e cópia precisa de `try/catch`.
- Um evento novo no registro muda os hashes, mas não pode mudar DECISAO nem ATUACAO: é isso que a assinatura confere.
- Métrica que não se aplica ao cenário aparece como "não se aplica", nunca como limite violado.
- "Desconhecido" e "desatualizado" declarados são incerteza honesta, não erro (RN01).
- Planta deslocada ou copiada: as coordenadas são absolutas. Uma zona cega esquecida no lugar antigo (v3dt) deixou a porta de entrada fora da vista do PIR. A referência passou, porque acende pelo SA; só o controlador que depende do SP revelou. Ao montar planta nova, confira os números de **outro** controlador além da referência.
- OR-12 compara as decisões locais com e sem falha de rede. Ação do app que muda a configuração de propósito (comando, preferência, aceite de sugestão) entra em `tem_app` e dispensa o par.
- Experimento de semanas (nucleo-v1.4): cada dia é uma execução, e o modelo passa de um dia para o outro. A rotina do dia sai de (semente, dia), por isso os braços "aceitar" e "recusar" veem os mesmos dias. Compare sempre os braços nos mesmos dias, nunca o antes e o depois de um braço só.
