"""nucleo-v1.3: perfis de pessoa, ocupante dormindo (PI-01) e presença incompatível (OR-15)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from avaliacao.oraculo import avaliar
from avaliacao.residencia import presenca_incompativel
from catalogo.validar import erros
from hub.controlador import ControladorReferencia
from sim.motor import simular

RAIZ = Path(__file__).resolve().parent.parent
FAMILIA = json.loads((RAIZ / "tests" / "dados" / "residencia-v1-familia.json").read_text(encoding="utf-8"))
SALA = json.loads((RAIZ / "cenarios" / "sala.json").read_text(encoding="utf-8"))


def rot(acoes, dur, falhas=(), amb="residencia-v1-familia", id_="TX01"):
    return {"id": id_, "versao": "v1dt.1", "ambiente": amb, "titulo": "teste", "tipo": "NORMAL", "modo": "IDEAL",
            "duracao_ms": dur, "estado_inicial": {"ocupantes_na_sala": [], "luz": "APAGADA"},
            "acoes": acoes, "falhas": list(falhas)}


def a(t, quem, acao, **kw):
    return {"t_ms": t, "ocupante": quem, "acao": acao, **kw}


def rodar(r, cfg=FAMILIA, semente=42):
    ev = simular(cfg, r, ControladorReferencia, semente).eventos
    return ev, avaliar(ev, r, cfg, None, None)


def test_fixture_familia_valida():
    assert not erros("residencia", FAMILIA)


def test_dormir_apagar_nao_e_indevido_e_parado_e():
    base = [a(5_000, "morador", "ENTRAR"), a(8_000, "morador", "ANDAR", ate=[2.5, 2.0])]
    _, dorme = rodar(rot(base + [a(15_000, "morador", "DORMIR")], 300_000, amb="sala"), SALA)
    _, parado = rodar(rot(base + [a(15_000, "morador", "PARADO")], 300_000, amb="sala"), SALA)
    md, mp = dorme["metricas"], parado["metricas"]
    assert md["apagamentos_indevidos"] == 0 and md["escuro_com_ocupante_s"] < 1
    assert 40 < md["luz_com_todos_dormindo_s"] < 80          # acesa até o T_apagamento, depois o escuro desejado
    assert mp["apagamentos_indevidos"] == 1 and mp["escuro_com_ocupante_s"] > 200
    assert mp["luz_com_todos_dormindo_s"] == 0
    assert all(v["ok"] for v in dorme["invariantes"].values())


def test_dormindo_acorda_com_qualquer_acao():
    ev, _ = rodar(rot([a(5_000, "idoso", "ENTRAR"), a(10_000, "idoso", "DORMIR"),
                       a(100_000, "idoso", "ANDAR_ALEATORIO", duracao_ms=30_000)], 160_000))
    tipos = [(e["tipo"], e["t_ms"]) for e in ev if e["tipo"] in ("ADORMECEU", "ACORDOU")]
    assert tipos == [("ADORMECEU", 10_000), ("ACORDOU", 100_000)]


def test_perfis_mudam_so_o_movimento():
    """A criança chega ao vão antes do idoso, no mesmo roteiro."""
    def cruzou(quem):
        ev, _ = rodar(rot([a(5_000, quem, "ENTRAR"), a(10_000, quem, "MUDAR_COMODO", para="cozinha")], 60_000))
        return next(e["t_ms"] for e in ev if e["tipo"] == "CRUZOU_PASSAGEM")
    assert cruzou("crianca") < cruzou("morador") < cruzou("idoso")


def _visitante_fica(acorda_ms=900_000):
    return rot([a(5_000, "morador", "ENTRAR"), a(6_000, "visitante", "ENTRAR"),
                a(10_000, "visitante", "ANDAR", ate=[2.0, 2.0]), a(20_000, "visitante", "DORMIR"),
                a(12_000, "morador", "ANDAR", ate=[0.95, 1.0]), a(25_000, "morador", "SAIR"),
                a(acorda_ms, "visitante", "ACORDAR"),
                a(acorda_ms + 5_000, "visitante", "ANDAR_ALEATORIO", duracao_ms=400_000)], acorda_ms + 420_000)


def test_presenca_incompativel_confirmada_vira_evento_de_fronteira():
    ev, av = rodar(_visitante_fica())
    sus = [(e["estado"], e["t_ms"]) for e in ev if e["tipo"] == "SUSPEITA_PRESENCA"]
    assert [s for s, _ in sus] == ["ABERTA", "CONFIRMADA"]
    assert sus[1][1] - sus[0][1] >= 300_000                     # verificação de 5 min (RN17)
    fr = [e for e in ev if e["tipo"] == "EVENTO_FRONTEIRA"]
    assert len(fr) == 1 and fr[0]["evento"] == "PRESENCA_NAO_EXPLICADA"
    assert av["invariantes"]["OR-15"]["ok"]
    assert not any("INVAS" in json.dumps(e, ensure_ascii=False).upper() for e in ev)


def test_passagem_tardia_concilia_a_suspeita():
    r = rot([a(5_000, "morador", "ENTRAR"), a(8_000, "morador", "ANDAR", ate=[0.95, 1.0]), a(15_000, "morador", "SAIR"),
             a(200_000, "visitante", "ENTRAR"), a(203_000, "visitante", "ANDAR_ALEATORIO", duracao_ms=120_000),
             a(215_000, "morador", "ENTRAR")], 700_000,
            falhas=[{"t_ms": 190_000, "tipo": "SA_PERDE_PROXIMA"}])
    ev, av = rodar(r)
    assert [e["estado"] for e in ev if e["tipo"] == "SUSPEITA_PRESENCA"] == ["ABERTA", "CONCILIADA"]
    assert not [e for e in ev if e["tipo"] == "EVENTO_FRONTEIRA"]
    assert av["invariantes"]["OR-15"]["ok"]


def test_or15_falha_quando_deve():
    ev, _ = rodar(_visitante_fica())
    fr = next(e for e in ev if e["tipo"] == "EVENTO_FRONTEIRA")
    sem_verificacao = [e for e in ev if not (e["tipo"] == "SUSPEITA_PRESENCA" and e["estado"] == "CONFIRMADA")]
    assert not presenca_incompativel(sem_verificacao)["OR-15"]["ok"]
    rotulo = copy.deepcopy(ev)
    next(e for e in rotulo if e is not None and e["tipo"] == "EVENTO_FRONTEIRA")["descricao"] = "invasão"
    assert not presenca_incompativel(rotulo)["OR-15"]["ok"]
    assert fr["descricao"] == "presença não explicada"
