"""nucleo-v1.4 (v3dt.1): relógio de parede, faixas de T_apagamento, aceite de sugestões, OR-17,
leitor que reage ao escuro, modelo agregado do gêmeo e rotina diária."""
import copy
import json
from pathlib import Path

import pytest

from avaliacao.oraculo import aprendizado_com_aceite
from avaliacao.residencia import avaliar_residencia
from experimentos.aprendizado import medir_dia
from experimentos.rotina import caminho, gerar_dia
from hub.controlador import ControladorReferencia
from plataforma.aprendizado import T_CURTO_MS, T_LONGO_MS, ModeloOcupacao
from sim.motor import simular
from sim.residencia import Residencia

DADOS = Path(__file__).parent / "dados"
AMB = json.loads((DADOS / "residencia-teste-4.json").read_text(encoding="utf-8"))
OCUP = [o["id"] for o in AMB["ocupantes"]]


def a(t, quem, acao, **k):
    return {"t_ms": t, "ocupante": quem, "acao": acao, **k}


def roteiro(acoes, **extra):
    return {"id": "TA", "versao": "nucleo-v1.4", "ambiente": AMB["id"], "modo": "IDEAL", "duracao_ms": 600_000,
            "estado_inicial": {"ocupantes_na_sala": [], "luz": "APAGADA"}, "falhas": [], "acoes": acoes, **extra}


def rodar(rot):
    reg = simular(AMB, rot, ControladorReferencia, 42)
    return reg, avaliar_residencia(reg.eventos, rot, Residencia(AMB), None, None)


SUG = {"id": "SUG-sala-20-22", "comodo": "sala", "de": "20:00", "ate": "22:00", "t_apagamento_ms": 300_000}
LEITURA = [a(5_000, OCUP[0], "ENTRAR"), a(9_000, OCUP[0], "LER")]


def eventos(reg, tipo, camada=None):
    return [e for e in reg.eventos if e["tipo"] == tipo and (camada is None or e["camada"] == camada)]


# ------------------------------------------------------------------ relógio
def test_sem_hora_inicio_nada_muda_no_registro():
    reg, _ = rodar(roteiro(LEITURA))
    assert reg.hora_inicio_ms is None
    assert not eventos(reg, "FAIXA_APLICADA") and not eventos(reg, "SUGESTAO")
    assert "hora_inicio" not in eventos(reg, "INICIO")[0]


def test_hora_do_dia_atravessa_a_meia_noite():
    reg, _ = rodar(roteiro(LEITURA, hora_inicio="23:59:30", duracao_ms=60_000))
    assert reg.hora_do_dia_ms(0) == (23 * 3600 + 59 * 60 + 30) * 1000
    assert reg.hora_do_dia_ms(40_000) == 10_000


# ------------------------------------------------------------------- leitor
def test_leitor_reage_ao_escuro_em_3_a_10_s():
    reg, _ = rodar(roteiro(LEITURA))
    reacoes = eventos(reg, "REAGIU_AO_ESCURO")
    apagou = [e["t_ms"] for e in reg.eventos if e["tipo"] == "LUZ_FISICA" and not e["acesa"] and e["comodo"] == "sala"]
    assert reacoes and apagou
    for r in reacoes:
        antes = max(t for t in apagou if t <= r["t_ms"])
        assert 3_000 <= r["t_ms"] - antes <= 10_100


# ------------------------------------------------------------------- faixas
def test_faixa_inicial_vale_dentro_do_horario_e_volta_ao_base():
    cfg = {"versao": 3, "faixas": {"sala": [{"de": "20:00", "ate": "20:05", "t_apagamento_ms": 300_000}]},
           "sugestoes_aceitas": ["SUG-x"]}
    reg, av = rodar(roteiro(LEITURA, hora_inicio="19:59", config_inicial=cfg))
    fx = eventos(reg, "FAIXA_APLICADA")
    assert [(f["faixa"], f["t_apagamento_ms"], f["hora"]) for f in fx] == [
        ("20:00-20:05", 300_000, "20:00:00"), (None, 60_000, "20:05:00")]
    assert av["invariantes"]["OR-03"]["ok"] and av["invariantes"]["OR-17"]["ok"]


def test_aceite_cria_versao_pendente_que_o_hub_aplica():
    rot = roteiro(LEITURA + [a(120_000, "app", "APP_ACEITAR", sugestoes=["SUG-sala-20-22"])],
                  hora_inicio="19:55", sugestoes=[SUG])
    reg, av = rodar(rot)
    estados = [(e["tipo"], e.get("estado")) for e in reg.eventos if e["tipo"] in ("SUGESTAO", "CONFIG_VERSAO")]
    assert estados == [("SUGESTAO", "PENDENTE"), ("SUGESTAO", "ACEITA"), ("CONFIG_VERSAO", "PENDENTE"),
                       ("CONFIG_VERSAO", "APLICADA")]
    assert eventos(reg, "CONFIG_APLICADA")[0]["faixas"] == {"sala": [{k: SUG[k] for k in ("de", "ate", "t_apagamento_ms")}]}
    assert eventos(reg, "FAIXA_APLICADA")[0]["hora"] == "20:00:00"
    assert av["invariantes"]["OR-17"] == {"ok": True, "violacoes": []}
    assert av["requisitos_ok"]


def test_recusa_nao_cria_versao_nem_faixa():
    rot = roteiro(LEITURA + [a(120_000, "app", "APP_RECUSAR", sugestoes=["SUG-sala-20-22"])],
                  hora_inicio="19:55", sugestoes=[SUG])
    reg, av = rodar(rot)
    assert [e["estado"] for e in eventos(reg, "SUGESTAO")] == ["PENDENTE", "RECUSADA"]
    assert not eventos(reg, "CONFIG_VERSAO") and not eventos(reg, "FAIXA_APLICADA")
    assert av["invariantes"]["OR-17"]["ok"]


def test_aceite_com_canal_fora_fica_pendente_e_aplica_na_volta():
    rot = roteiro(LEITURA + [a(120_000, "app", "APP_ACEITAR", sugestoes=["SUG-sala-20-22"])],
                  hora_inicio="19:55", sugestoes=[SUG],
                  falhas=[{"t_ms": 100_000, "tipo": "CANAL_DESCONECTA", "duracao_ms": 200_000}])
    reg, av = rodar(rot)
    aplicada = eventos(reg, "CONFIG_APLICADA")[0]["t_ms"]
    assert aplicada >= 300_000
    assert eventos(reg, "SUGESTAO")[-1]["estado"] == "ACEITA"
    assert av["invariantes"]["OR-17"]["ok"] and av["invariantes"]["OR-10"]["ok"]


def test_sugestao_fora_da_politica_e_rejeitada():
    sg = {**SUG, "t_apagamento_ms": 5_000}
    reg, av = rodar(roteiro(LEITURA + [a(120_000, "app", "APP_ACEITAR", sugestoes=[SUG["id"]])],
                            hora_inicio="19:55", sugestoes=[sg]))
    assert eventos(reg, "SUGESTAO")[-1]["estado"] == "REJEITADA"
    assert not eventos(reg, "CONFIG_APLICADA")


# -------------------------------------------------------- OR-17 tem de falhar
@pytest.fixture(scope="module")
def aceito():
    rot = roteiro(LEITURA + [a(120_000, "app", "APP_ACEITAR", sugestoes=["SUG-sala-20-22"])],
                  hora_inicio="19:55", sugestoes=[SUG])
    return simular(AMB, rot, ControladorReferencia, 42).eventos


def test_or17_falha_se_o_hub_aplica_sem_aceite(aceito):
    ev = [e for e in aceito if not (e["tipo"] == "SUGESTAO" and e["estado"] == "ACEITA")]
    assert not aprendizado_com_aceite(ev, OCUP)["OR-17"]["ok"]


def test_or17_falha_se_aplica_faixa_sem_versao(aceito):
    ev = [e for e in aceito if e["tipo"] != "CONFIG_VERSAO"]
    assert not aprendizado_com_aceite(ev, OCUP)["OR-17"]["ok"]


def test_or17_falha_se_recusada_entra_numa_versao(aceito):
    ev = copy.deepcopy(aceito)
    for e in ev:
        if e["tipo"] == "SUGESTAO" and e["estado"] == "ACEITA":
            e["estado"] = "RECUSADA"
    assert not aprendizado_com_aceite(ev, OCUP)["OR-17"]["ok"]


def test_or17_falha_com_dado_por_ocupante(aceito):
    ev = copy.deepcopy(aceito)
    for e in ev:
        if e["tipo"] == "SUGESTAO" and e["estado"] == "PENDENTE":
            e["evidencia"] = {"quem": OCUP[0]}
    assert not aprendizado_com_aceite(ev, OCUP)["OR-17"]["ok"]


def test_or17_nao_se_aplica_sem_aprendizado():
    reg, av = rodar(roteiro(LEITURA))
    assert av["invariantes"]["OR-17"].get("aplica") is False


# ------------------------------------------------------------------- modelo
def _dia_plat(apagamentos):
    """Eventos sintéticos da camada PLATAFORMA: (cômodo, t_apagamento, reage?)."""
    ev = []
    for c, t, reage in apagamentos:
        ev += [{"camada": "PLATAFORMA", "tipo": "EVIDENCIA_RECEBIDA", "t_ms": t - 80_000, "t_origem_ms": t - 80_000,
                "evidencia": "PASSAGEM", "comodos": [c]},
               {"camada": "PLATAFORMA", "tipo": "EVIDENCIA_RECEBIDA", "t_ms": t - 60_000, "t_origem_ms": t - 60_000,
                "evidencia": "MOVIMENTO", "comodos": [c]},
               {"camada": "PLATAFORMA", "tipo": "ESTADO_REMOTO", "t_ms": t - 59_000, "comodo": c, "luz": "ACESA_AUTO"},
               {"camada": "PLATAFORMA", "tipo": "ESTADO_REMOTO", "t_ms": t, "comodo": c, "luz": "APAGADA"}]
        if reage:
            ev.append({"camada": "PLATAFORMA", "tipo": "EVIDENCIA_RECEBIDA", "t_ms": t + 6_000, "t_origem_ms": t + 6_000,
                       "evidencia": "MOVIMENTO", "comodos": [c]})
    ev.append({"camada": "PLATAFORMA", "tipo": "ESTADO_REMOTO", "t_ms": 7_000_000, "comodo": "x", "luz": "APAGADA"})
    return sorted(ev, key=lambda e: e["t_ms"])


def test_modelo_sugere_longo_onde_ha_reacao_e_curto_onde_ha_imobilidade():
    m = ModeloOcupacao()
    for dia in range(1, 8):
        m.observar_dia(dia, _dia_plat([("sala", 200_000, True), ("sala", 400_000, True), ("quarto", 4_000_000, False)]),
                       20 * 3_600_000)
    sug = {s["comodo"]: s for s in m.sugestoes({"sala": 60_000, "quarto": 60_000})}
    assert sug["sala"]["t_apagamento_ms"] == T_LONGO_MS and (sug["sala"]["de"], sug["sala"]["ate"]) == ("20:00", "21:00")
    assert sug["quarto"]["t_apagamento_ms"] == T_CURTO_MS and sug["quarto"]["de"] == "21:00"
    assert sug["sala"]["evidencia"]["reacoes"] == 14


def test_modelo_nao_sugere_com_poucos_dias_e_ignora_quem_passou():
    m = ModeloOcupacao()
    for dia in range(1, 4):
        m.observar_dia(dia, _dia_plat([("sala", 200_000, True)] * 3), 20 * 3_600_000)
    assert m.sugestoes({"sala": 60_000}) == []
    so_passou = [e for e in _dia_plat([("sala", 200_000, True)]) if e.get("evidencia") != "MOVIMENTO" or e["t_ms"] > 200_000]
    assert ModeloOcupacao().observar_dia(1, so_passou, 0) == {}


def test_modelo_guarda_30_dias_e_nada_por_ocupante():
    m = ModeloOcupacao()
    for dia in range(1, 41):
        m.observar_dia(dia, _dia_plat([("sala", 200_000, True)]), 0)
    assert sorted(m.dias) == list(range(11, 41))
    texto = json.dumps(m.exportar())
    assert "ocupante" not in texto and not any(o in texto for o in ("morador", "rex", "crianca"))


def test_modelo_so_le_a_camada_plataforma():
    ev = _dia_plat([("sala", 200_000, True)])
    verdade = [{**e, "camada": "VERDADE"} for e in ev]
    assert ModeloOcupacao().observar_dia(1, verdade, 0) == {}


# ------------------------------------------------------------------- rotina
ROTINA = {"ambiente": AMB["id"], "hora_inicio": "20:00", "duracao_h": 0.5, "ocupantes": {
    OCUP[0]: {"comeca_em": AMB["comodos"][0]["id"], "passos": [
        {"as": "20:00", "comodo": AMB["comodos"][0]["id"], "fazer": "LER"},
        {"as": "20:10", "var": 2, "comodo": AMB["comodos"][-1]["id"], "fazer": "ANDAR"},
        {"as": "20:20", "var": 2, "comodo": AMB["comodos"][-1]["id"], "fazer": "DORMIR"}]}}}


def test_rotina_e_deterministica_e_roda():
    r1, r2 = gerar_dia(AMB, ROTINA, 3, 7), gerar_dia(AMB, ROTINA, 3, 7)
    assert r1 == r2 and r1 != gerar_dia(AMB, ROTINA, 4, 7)
    assert r1["hora_inicio"] == "20:00" and r1["duracao_ms"] == 1_800_000
    reg = simular(AMB, r1, ControladorReferencia, 1)
    assert eventos(reg, "ADORMECEU")
    med = medir_dia(reg.eventos, AMB, reg.hora_inicio_ms, r1["duracao_ms"])
    assert all(h == 20 for _, h in med)


def test_caminho_pelas_passagens():
    ids = [c["id"] for c in AMB["comodos"]]
    rota = caminho(AMB, ids[0], ids[-1])
    assert rota[-1] == ids[-1] and ids[0] not in rota


def test_politica_de_aceite():
    from experimentos.aprendizado import escolher
    sg = [{"id": "L", "comodo": "sala", "t_apagamento_ms": 300_000}, {"id": "C", "comodo": "quarto", "t_apagamento_ms": 30_000}]
    base = {"sala": 60_000, "quarto": 60_000}
    assert [s["id"] for s in escolher(sg, "todas", base)] == ["L", "C"]
    assert [s["id"] for s in escolher(sg, "longas", base)] == ["L"]
    assert [s["id"] for s in escolher(sg, "curtas", base)] == ["C"]
    assert [s["id"] for s in escolher(sg, "comodos:quarto", base)] == ["C"]
    with pytest.raises(ValueError):
        escolher(sg, "nenhuma", base)
