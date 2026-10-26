"""Gera os roteiros e as asserções M01–M14 da v1dt (plano v1dt §8).

Uso, dentro da pasta do projeto:
    python tools/cenarios_v1dt.py

Os cenários usam o ambiente `cenarios/residencia-v1.json` (sala e cozinha).
As asserções sobre um cômodo levam `"comodo"`; sem ele, métricas valem para a
residência (soma dos cômodos) e o resto, para a sala.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
R, C = "REQUISITO", "CARACTERIZACAO"
CEN: list = []


def a(id_, nivel, dado, quando, entao):
    return {"id": id_, "nivel": nivel, "dado": dado, "quando": quando, "entao": entao}


INV = a("INV", R, "qualquer execução", "o cenário termina", {"tipo": "invariantes"})
m = lambda nome, **k: {"tipo": "metrica", "nome": nome, **k}
luz = lambda comodo, valor, **k: {"tipo": "luz", "comodo": comodo, "valor": valor, **k}
cte = lambda comodo, valor, a0, a1: {"tipo": "luz_constante", "comodo": comodo, "valor": valor, "entre_ms": [a0, a1]}


def ac(t, quem, acao, **k):
    return {"t_ms": t, "ocupante": quem, "acao": acao, **k}


ent = lambda t, q="morador": ac(t, q, "ENTRAR")
sai = lambda t, q="morador": ac(t, q, "SAIR")
mud = lambda t, para, q="morador", **k: ac(t, q, "MUDAR_COMODO", para=para, **k)
ale = lambda t, dur, q="morador": ac(t, q, "ANDAR_ALEATORIO", duracao_ms=dur)
anda = lambda t, ate, q="morador": ac(t, q, "ANDAR", ate=list(ate))
PORTA = (0.95, 1.0)


def cen(id_, tipo, titulo, dur, desc, ideal, ref, acoes, falhas, req, regras, ass, **extra):
    r = {"id": id_, "versao": "v1dt", "ambiente": "residencia-v1", "titulo": titulo, "tipo": tipo, "modo": "IDEAL",
         "duracao_ms": dur, "descricao": desc, "comportamento_ideal": ideal, "comportamento_referencia": ref,
         "estado_inicial": {"ocupantes_na_sala": [], "luz": "APAGADA"}, "acoes": acoes, "falhas": falhas,
         "requisitos": req, "regras": regras, **extra}
    e = {"cenario": id_, "modo": "IDEAL", "semente_referencia": 42, "requisitos": req, "assercoes": ass + [INV]}
    CEN.append((r, e))


cen("M01", "NORMAL", "Morador vai da sala à cozinha e volta", 240_000,
    "O morador entra, anda na sala, passa pelo vão para a cozinha em t=40 s e volta para a sala em t=120 s.",
    "A luz acompanha o morador: acende no cômodo em que ele entra e apaga no que ficou vazio.",
    "O SA do vão chega aos dois controladores: acende a cozinha e renova o tempo da sala; a sala apaga 60 s depois.",
    [ent(5_000), ale(10_000, 25_000), mud(40_000, "cozinha"), ale(45_000, 70_000), mud(120_000, "sala"), ale(125_000, 110_000)],
    [], ["RF-OPR-01", "RNF-DES-03"], ["RN-V1-01", "RN-V1-02"],
    [a("A1", R, "cozinha escura", "o morador cruza o vão", luz("cozinha", "ACESA", desde_ms=40_000, ate_ms=44_000)),
     a("A2", R, "cozinha vazia e acesa", "o morador já voltou para a sala", luz("cozinha", "APAGADA", em_ms=200_000)),
     a("A3", R, "sala vazia enquanto ele está na cozinha", "60 s sem detecção", luz("sala", "APAGADA", em_ms=112_000)),
     a("A4", R, "volta para a sala escura", "cruza o vão de novo", luz("sala", "ACESA", desde_ms=120_000, ate_ms=124_000)),
     a("A5", R, "entrada em cômodo escuro", "a lâmpada acende", m("atraso_percebido_ms_max", max=1000)),
     a("A6", R, "cômodo esvaziado", "a luz apaga", m("desperdicio_por_saida_s_max", max=90)),
     a("A7", R, "morador sempre presente em algum cômodo", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M02", "NORMAL", "Entra pela rua e vai direto à cozinha", 180_000,
    "O morador entra pela porta da sala em t=5 s e segue direto para a cozinha.",
    "A cozinha acende quando ele chega; a sala, que ele só atravessou, apaga depois de 60 s.",
    "A sala acende na entrada (SA-01) e apaga 60 s depois da última detecção.",
    [ent(5_000), mud(6_000, "cozinha", vel_m_s=1.2), ale(15_000, 160_000)], [],
    ["RF-OPR-01"], ["RN-V1-01"],
    [a("A1", R, "cozinha escura", "o morador chega", luz("cozinha", "ACESA", desde_ms=6_000, ate_ms=15_000)),
     a("A2", R, "sala atravessada", "60 s sem detecção", luz("sala", "APAGADA", em_ms=100_000)),
     a("A3", C, "a sala acende na entrada", "o SA-01 detecta", luz("sala", "ACESA", desde_ms=5_000, ate_ms=6_000)),
     a("A4", R, "sala esvaziada", "a luz apaga", {**m("desperdicio_por_saida_s_max", max=90), "comodo": "sala"}),
     a("A5", R, "morador sempre presente", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M03", "FALSO_POSITIVO", "Espia a cozinha pelo vão sem entrar", 180_000,
    "O morador vai até o vão em t=10 s, espia a cozinha em t=20 s e volta para a sala.",
    "A cozinha não deveria acender: ninguém entrou.",
    "Limitação conhecida (DQ1-09): o SA do vão é detecção para os dois cômodos, e a cozinha acende por 60 s.",
    [ent(5_000), anda(10_000, (4.3, 3.0)), ac(20_000, "morador", "ESPIAR", comodo="cozinha"),
     ale(25_000, 150_000)], [],
    ["RN09", "RF-OPR-01"], ["RN-V1-01"],
    [a("A1", C, "o SA do vão dispara", "a referência decide",
       {"tipo": "intencao", "comodo": "cozinha", "acao": "ACENDER", "causa": "PASSAGEM_SA", "entre_ms": [20_000, 22_000]}),
     a("A2", C, "cozinha acesa e vazia", "o cenário termina", {**m("desperdicio_s", min=55), "comodo": "cozinha"}),
     a("A3", R, "morador sempre na sala", "o cenário segue", cte("sala", "ACESA", 6_000, 180_000)),
     a("A4", R, "ninguém na cozinha", "90 s depois", luz("cozinha", "APAGADA", em_ms=110_000)),
     a("A5", R, "morador sempre presente", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M04", "NORMAL", "Rex sozinho na cozinha, morador na sala", 300_000,
    "O morador e o Rex entram; o Rex vai para a cozinha em t=15 s e fica andando; o morador anda na sala.",
    "Os dois cômodos ficam acesos: o Rex é ocupante (RN34).",
    "Cada controlador mantém o seu cômodo aceso pelas detecções do seu SP.",
    [ent(5_000), ent(8_000, "rex"), ale(10_000, 285_000), mud(15_000, "cozinha", "rex"), ale(25_000, 270_000, "rex")], [],
    ["RN34", "RF-OPR-01"], ["RN-V1-02", "RN-I0-01"],
    [a("A1", R, "Rex na cozinha", "o cenário segue", cte("cozinha", "ACESA", 21_000, 300_000)),
     a("A2", R, "morador na sala", "o cenário segue", cte("sala", "ACESA", 6_000, 300_000)),
     a("A3", R, "Rex em movimento", "t = 200 s", {"tipo": "ocupacao", "comodo": "cozinha", "valor": "OCUPADA", "em_ms": 200_000}),
     a("A4", R, "ocupantes sempre presentes", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M05", "FALSO_NEGATIVO", "Morador parado na cozinha", 300_000,
    "O morador vai para a cozinha em t=8 s e fica parado lá até o fim.",
    "A cozinha continua acesa enquanto ele está lá.",
    "Limitação conhecida da v0, agora na cozinha: sem movimento, o PIR não detecta e a luz apaga 60 s depois.",
    [ent(5_000), mud(8_000, "cozinha")], [],
    ["RF-OPR-01"], ["RN-V1-02"],
    [a("A1", C, "morador parado", "60 s sem detecção",
       {"tipo": "intencao", "comodo": "cozinha", "acao": "APAGAR", "entre_ms": [60_000, 100_000]}),
     a("A2", C, "morador parado no escuro", "o cenário termina", {**m("escuro_com_ocupante_s", min=150), "comodo": "cozinha"}),
     a("A3", R, "sala vazia", "60 s depois", luz("sala", "APAGADA", em_ms=120_000))])

cen("M06", "NORMAL", "Morador e Rex cruzam o vão juntos", 240_000,
    "Os dois param perto do vão e o cruzam quase juntos em t=30 s; depois o morador volta para a sala e o Rex fica.",
    "A cozinha acende e continua acesa com o Rex; o SA conta uma passagem para dois ocupantes (CV15).",
    "O rearme de 2 s do SA-02 faz as duas travessias virarem uma só evidência; nada mais muda.",
    [ent(5_000), ent(7_000, "rex"), anda(15_000, (4.4, 3.0)), anda(15_000, (4.4, 3.2), "rex"),
     mud(30_000, "cozinha"), mud(30_300, "cozinha", "rex"), ale(35_000, 85_000), ale(35_000, 200_000, "rex"),
     mud(125_000, "sala"), ale(130_000, 105_000)], [],
    ["CV15", "RN09"], ["RN-V1-01"],
    [a("A1", R, "dois entram na cozinha", "o cenário segue", cte("cozinha", "ACESA", 32_000, 240_000)),
     a("A2", C, "duas travessias em menos de 2 s", "o SA-02 rearma",
       {"tipo": "evento", "comodo": "cozinha", "camada": "PERCEPCAO", "evento": "PASSAGEM", "campos": {"origem": "SA-02"},
        "entre_ms": [30_000, 34_000], "max": 1}),
     a("A3", R, "morador volta à sala", "cruza o vão", luz("sala", "ACESA", desde_ms=125_000, ate_ms=130_000)),
     a("A4", R, "ocupantes sempre presentes", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M07", "FALHA", "O SA do vão falha", 240_000,
    "O SA-02 perde a próxima passagem. O morador passa para a cozinha em t=40 s.",
    "A cozinha acende mesmo assim, um pouco depois, pelo PIR.",
    "Sem o SA, o SP-02 detecta o movimento e acende a cozinha.",
    [ent(5_000), ale(10_000, 25_000), mud(40_000, "cozinha"), ale(45_000, 190_000)],
    [{"t_ms": 0, "tipo": "SA_PERDE_PROXIMA", "dispositivo": "SA-02"}],
    ["RN01", "RF-OPR-01"], ["RN-V1-01"],
    [a("A1", R, "SA-02 mudo", "o morador entra na cozinha", luz("cozinha", "ACESA", desde_ms=40_000, ate_ms=47_000)),
     a("A2", C, "só o PIR detecta", "a cozinha acende", {**m("atraso_percebido_ms_max", max=3000), "comodo": "cozinha"}),
     a("A3", R, "morador sempre presente", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M08", "FALHA", "SP da cozinha sem resposta", 300_000,
    "O morador está na cozinha quando o SP-02 para de responder (t=60 s); ele volta para a sala em t=205 s.",
    "A cozinha passa a ocupação desconhecida, sinaliza a falha e nunca apaga por silêncio (RN01).",
    "Como na F01 da v0, agora só na cozinha: a sala segue normal.",
    [ent(5_000), mud(10_000, "cozinha"), ale(15_000, 185_000), mud(205_000, "sala"), ale(210_000, 85_000)],
    [{"t_ms": 60_000, "tipo": "SP_SEM_RESPOSTA", "dispositivo": "SP-02"}],
    ["RN01", "RF-OPR-09"], ["RN-I0-04", "RN-V1-02"],
    [a("A1", R, "SP-02 mudo", "30 s sem heartbeat", {"tipo": "alerta", "comodo": "cozinha", "alerta": "SP_SEM_RESPOSTA",
                                                      "entre_ms": [80_000, 110_000]}),
     a("A2", R, "SP-02 mudo", "t = 150 s", {"tipo": "ocupacao", "comodo": "cozinha", "valor": "DESCONHECIDA", "em_ms": 150_000}),
     a("A3", R, "ocupação desconhecida", "o cenário segue",
       {"tipo": "sem_intencao", "comodo": "cozinha", "acao": "APAGAR", "entre_ms": [60_000, 300_000]}),
     a("A4", R, "sala sem falha", "o morador volta", luz("sala", "ACESA", desde_ms=205_000, ate_ms=210_000))])

cen("M09", "NORMAL", "Interruptor da cozinha", 240_000,
    "Na cozinha, o morador apaga a luz no interruptor em t=60 s e acende de novo em t=150 s; depois volta para a sala.",
    "O interruptor da cozinha só mexe na cozinha, com precedência manual de 15 min.",
    "Como a N04 da v0, no cômodo certo (OR-14).",
    [ent(5_000), mud(10_000, "cozinha"), ale(15_000, 45_000), ac(60_000, "morador", "INTERRUPTOR"),
     ale(61_000, 89_000), ac(150_000, "morador", "INTERRUPTOR"), mud(160_000, "sala"), ale(165_000, 70_000)], [],
    ["RF-OPR-02"], ["RN-I0-05", "RN-V1-02"],
    [a("A1", R, "morador apaga a cozinha", "o interruptor é acionado",
       {"tipo": "intencao", "comodo": "cozinha", "acao": "APAGAR", "precedencia": "MANUAL", "entre_ms": [60_000, 61_500]}),
     a("A2", R, "precedência manual", "o morador continua se movendo", cte("cozinha", "APAGADA", 61_000, 150_000)),
     a("A3", R, "morador acende de novo", "t = 152 s", luz("cozinha", "ACESA", em_ms=152_000)),
     a("A4", R, "sala vazia desde t=10 s", "o interruptor da cozinha não afeta a sala", luz("sala", "APAGADA", em_ms=100_000))])

cen("M10", "NORMAL", "Sai pela rua com a cozinha acesa e vazia", 300_000,
    "O morador sai da cozinha em t=65 s, atravessa a sala e sai pela porta em t=76 s.",
    "Cada cômodo apaga sozinho, no máximo 90 s depois de ficar vazio.",
    "A cozinha apaga 60 s depois da última detecção, mesmo sem o morador passar de novo pelo vão.",
    [ent(5_000), mud(10_000, "cozinha"), ale(15_000, 45_000), mud(65_000, "sala"), anda(70_000, PORTA), sai(76_000)], [],
    ["RF-OPR-01", "PS05"], ["RN-V1-02"],
    [a("A1", R, "cozinha vazia", "75 s depois", luz("cozinha", "APAGADA", em_ms=140_000)),
     a("A2", R, "cozinha esvaziada", "a luz apaga", {**m("desperdicio_por_saida_s_max", max=90), "comodo": "cozinha"}),
     a("A3", R, "casa vazia", "t = 150 s", luz("sala", "APAGADA", em_ms=150_000)),
     a("A4", R, "morador sempre presente até sair", "o cenário termina", m("apagamentos_indevidos", igual=0))])

cen("M11", "GEMEO_DIGITAL", "Comando remoto acende a cozinha", 180_000,
    "Casa vazia. O titular toca em \"acender a cozinha\" no app em t=70 s e consulta o app em t=75 s.",
    "Só a cozinha acende; o app mostra o resultado em até 3 s e o estado atual da cozinha.",
    "O comando vai ao controlador da cozinha, com precedência REMOTA (RN-DT-09).",
    [ac(70_000, "app", "APP_COMANDO", comando="ACENDER", comodo="cozinha"), ac(75_000, "app", "APP_CONSULTA")], [],
    ["RF-OPR-03", "RNF-DES-02"], ["RN-V1-03", "RN-DT-09"],
    [a("A1", R, "sessão ativa", "o titular toca em acender a cozinha",
       {"tipo": "comando", "comodo": "cozinha", "indice": 1, "nivel": "EFEITO_OBSERVADO", "latencia_max_ms": 3000}),
     a("A2", R, "comando aceito", "o atuador da cozinha executa", luz("cozinha", "ACESA", desde_ms=70_000, ate_ms=73_000)),
     a("A3", R, "comando só da cozinha", "o cenário segue", cte("sala", "APAGADA", 0, 180_000)),
     a("A4", R, "comando executado", "o titular consulta o app",
       {"tipo": "app_consulta", "comodo": "cozinha", "indice": 1, "campos": {"atualidade": "ATUAL", "luz": "ACESA_MANUAL"}}),
     a("A5", C, "comando remoto", "o controlador da cozinha decide",
       {"tipo": "intencao", "comodo": "cozinha", "acao": "ACENDER", "causa": "COMANDO_REMOTO", "precedencia": "REMOTA",
        "entre_ms": [70_000, 72_000]})])

cen("M12", "GEMEO_DIGITAL", "Preferência só da cozinha", 420_000,
    "Em t=10 s o titular muda o tempo de apagamento da cozinha para 120 s. O morador passa pela cozinha e sai de casa.",
    "A cozinha apaga 120 s depois de ficar vazia; a sala continua com 60 s.",
    "O hub aplica a versão 2 só no controlador da cozinha (RN-V1-03).",
    [ac(10_000, "app", "APP_PREFERENCIA", t_apagamento_ms=120_000, comodo="cozinha"), ent(20_000), mud(25_000, "cozinha"),
     ale(30_000, 60_000), mud(95_000, "sala"), ale(100_000, 50_000), anda(150_000, PORTA), sai(160_000)], [],
    ["RF-OPR-07", "RF-SYN-06", "INV-14"], ["RN-V1-03", "RN-DT-07"],
    [a("A1", R, "preferência da cozinha", "o hub confirma", {"tipo": "config", "comodo": "cozinha", "versao": 2, "estado": "APLICADA"}),
     a("A2", R, "versão aplicada", "só na cozinha",
       {"tipo": "evento", "comodo": "cozinha", "camada": "SISTEMA", "evento": "CONFIG_APLICADA", "campos": {"versao": 2, "comodo": "cozinha"}}),
     a("A3", R, "T_apagamento da cozinha = 120 s", "85 s depois de ela ficar vazia", luz("cozinha", "ACESA", em_ms=180_000)),
     a("A4", R, "T_apagamento da cozinha = 120 s", "145 s depois", luz("cozinha", "APAGADA", em_ms=240_000)),
     a("A5", R, "T_apagamento da sala = 60 s", "70 s depois da saída", luz("sala", "APAGADA", em_ms=230_000))])

cen("M13", "GEMEO_DIGITAL", "Desconexão com circulação entre cômodos", 900_000,
    "O enlace cai de t=60 s a t=660 s. O morador vai para a cozinha, volta para a sala e sai de casa antes da volta.",
    "A casa funciona sem a plataforma; na volta, o gêmeo recebe o estado atual de cada cômodo e registra a divergência da sala.",
    "Como a DT05, cômodo a cômodo.",
    [ent(10_000), ale(15_000, 40_000), mud(60_000, "cozinha"), ale(65_000, 225_000), mud(300_000, "sala"),
     ale(305_000, 235_000), anda(545_000, PORTA), sai(555_000)],
    [{"t_ms": 60_000, "tipo": "CANAL_DESCONECTA", "duracao_ms": 600_000}],
    ["RF-SYN-04", "RF-SYN-05", "RNF-CON-01", "CF06"], ["RN-V1-04", "RN-DT-03"],
    [a("A1", R, "enlace cai", "logo depois", {"tipo": "gemeo", "comodo": "cozinha", "em_ms": 61_000, "atualidade": "DESATUALIZADO"}),
     a("A2", R, "enlace fora", "o morador está na cozinha", luz("cozinha", "ACESA", em_ms=200_000)),
     a("A3", R, "sessão restabelecida", "o R recebe o estado atual", m("reconciliacao_ms_max", max=5000)),
     a("A4", R, "sessão restabelecida", "t = 680 s", {"tipo": "gemeo", "comodo": "sala", "em_ms": 680_000,
                                                       "atualidade": "ATUAL", "ocupacao": "VAZIA"}),
     a("A5", R, "R mostrava a sala ocupada", "chega o estado do hub",
       {"tipo": "evento", "camada": "PLATAFORMA", "evento": "DIVERGENCIA", "campos": {"comodo": "sala", "atributo": "ocupacao"}}),
     a("A6", R, "fila do hub", "o cenário termina", m("eventos_nao_entregues", igual=0))],
    amostras_ms=[30_000, 400_000, 665_000])

cen("M14", "GEMEO_DIGITAL", "Espelho da residência", 300_000,
    "O morador anda na sala; o Rex vai para a cozinha, anda e deita em t=100 s.",
    "O espelho mostra os dois cômodos; a cozinha deixa de ser fiel quando o Rex fica parado.",
    "As amostras mostram a sala fiel e a cozinha com erro de percepção (o hub acha a cozinha vazia).",
    [ent(5_000), ent(7_000, "rex"), ale(10_000, 280_000), mud(12_000, "cozinha", "rex"), ale(20_000, 80_000, "rex")], [],
    ["RN-V1-04", "RN34"], ["RN-V1-04", "RN-I0-01"],
    [a("A1", R, "morador na sala", "o cenário segue", cte("sala", "ACESA", 6_000, 300_000)),
     a("E1", C, "Rex deitado", "t = 250 s", {"tipo": "espelho", "comodo": "cozinha", "em_ms": 250_000, "classe": "PERCEPCAO"}),
     a("E2", C, "morador andando", "t = 250 s", {"tipo": "espelho", "comodo": "sala", "em_ms": 250_000, "classe": "FIEL"}),
     a("E3", R, "Rex andando", "t = 60 s", {"tipo": "espelho", "comodo": "cozinha", "em_ms": 60_000, "classe": "FIEL"})],
    amostras_ms=[60_000, 150_000, 250_000])

if __name__ == "__main__":
    for r, e in CEN:
        (RAIZ / "cenarios/roteiros" / f"{r['id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (RAIZ / "cenarios/esperado" / f"{r['id']}.json").write_text(json.dumps(e, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(CEN)} cenários gravados em cenarios/roteiros e cenarios/esperado")
