"""v0dt: o gêmeo digital, o canal e as invariantes OR-07 a OR-12."""
import copy

import pytest

from avaliacao.oraculo import avaliar, roteiro_sem_rede
from catalogo.executar import carregar_esperado, carregar_roteiros, carregar_sala
from hub.controlador import ControladorReferencia
from sim.motor import simular

SALA = carregar_sala()
R = {r["id"]: r for r in carregar_roteiros()}


class IgnoraComandoRemoto(ControladorReferencia):
    """Controlador da v0 que não trata COMANDO_REMOTO (DQ-04)."""
    nome = "ignora_remoto"

    def ao_evento(self, ev, agora_ms):
        if ev.tipo == "COMANDO_REMOTO":
            return []
        return super().ao_evento(ev, agora_ms)


def _executar(cid, fab=ControladorReferencia, semente=42):
    r = R[cid]
    return simular(SALA, r, fab, semente).eventos


def _avaliar(cid, eventos, par=None):
    r = R[cid]
    return avaliar(eventos, r, SALA, carregar_esperado(cid), par)


def test_controlador_que_ignora_o_app_reprova_nos_requisitos_mas_nao_nas_invariantes():
    res = _avaliar("DT01", _executar("DT01", IgnoraComandoRemoto))
    assert all(v["ok"] for v in res["invariantes"].values())
    assert not res["requisitos_ok"]
    assert not res["assercoes"]["A1"]["ok"]


def test_rede_nao_altera_as_decisoes_locais():
    """OR-12 na prática: DT05 com e sem a queda do enlace."""
    com = _executar("DT05")
    sem = simular(SALA, roteiro_sem_rede(R["DT05"]), ControladorReferencia, 42).eventos
    res = _avaliar("DT05", com, sem)
    assert res["invariantes"]["OR-12"]["ok"]
    assert res["invariantes"]["OR-12"].get("aplica", True)


def test_or12_detecta_decisao_diferente():
    com = _executar("DT07")
    par = copy.deepcopy(com)
    i = next(i for i, e in enumerate(par) if e["camada"] == "DECISAO")
    par[i]["t_ms"] += 1000
    assert not _avaliar("DT07", com, par)["invariantes"]["OR-12"]["ok"]


def test_or07_detecta_comando_executado_vencido():
    ev = copy.deepcopy(_executar("DT01"))
    rec = next(e for e in ev if e["tipo"] == "COMANDO_REMOTO_RECEBIDO")
    rec["valida_ate_ms"] = rec["t_ms"] - 1
    res = _avaliar("DT01", ev)
    assert not res["invariantes"]["OR-07"]["ok"]
    assert res["metricas"]["comandos_vencidos_executados"] == 1


def test_or08_detecta_atual_sem_sessao():
    ev = copy.deepcopy(_executar("DT05"))
    e = next(e for e in ev if e["tipo"] == "ESTADO_REMOTO" and e["conexao"] == "DESCONECTADO")
    e["atualidade"] = "ATUAL"
    assert not _avaliar("DT05", ev)["invariantes"]["OR-08"]["ok"]


def test_or09_detecta_historico_aplicado_sobre_estado_novo():
    ev = copy.deepcopy(_executar("DT05"))
    aplic = [e for e in ev if e["tipo"] == "ESTADO_REMOTO" and "n" in e]
    aplic[-1]["n"] = 1
    assert not _avaliar("DT05", ev)["invariantes"]["OR-09"]["ok"]


def test_or10_detecta_versao_aplicada_maior_que_a_vigente():
    ev = copy.deepcopy(_executar("DT06"))
    e = next(e for e in ev if e["tipo"] == "CONFIG_APLICADA")
    e["versao"] = 9
    assert not _avaliar("DT06", ev)["invariantes"]["OR-10"]["ok"]


def test_or11_detecta_dois_efeitos_para_o_mesmo_comando():
    ev = copy.deepcopy(_executar("DT04"))
    i = next(i for i, e in enumerate(ev) if e["tipo"] == "INTENCAO" and e.get("chave_remota"))
    ev.insert(i + 1, {**ev[i], "chave": "I-1-9999"})
    res = _avaliar("DT04", ev)
    assert not res["invariantes"]["OR-11"]["ok"]
    assert res["metricas"]["efeitos_duplicados_remotos"] == 1


def test_canal_realista_e_deterministico_por_semente():
    h = lambda s: simular(SALA, R["DT08"], ControladorReferencia, s).hash()
    assert h(5) == h(5)
    assert h(5) != h(6)


@pytest.mark.parametrize("cid", ["DT02", "DT05", "DT10"])
def test_gemeo_nunca_diz_atual_sem_sessao(cid):
    for e in _executar(cid):
        if e["tipo"] == "ESTADO_REMOTO" and e["atualidade"] == "ATUAL":
            assert e["conexao"] == "CONECTADO"


def test_preferencia_muda_o_tempo_de_apagamento_do_hub():
    ev = _executar("DT06")
    aplic = [e for e in ev if e["tipo"] == "CONFIG_APLICADA"]
    assert aplic and aplic[0]["t_apagamento_ms"] == 120_000 and aplic[0]["versao"] == 2
