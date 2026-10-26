"""v1dt: residência com dois cômodos, vistas por cômodo e OR-13/OR-14."""
import copy

import pytest

from avaliacao.oraculo import avaliar
from avaliacao.residencia import vista
from catalogo.executar import ambiente_de, carregar_esperado, carregar_roteiros, carregar_sala
from hub.controlador import ControladorReferencia
from sim.motor import simular
from sim.residencia import Residencia

R = {r["id"]: r for r in carregar_roteiros()}


def _rodar(cid, semente=42):
    r = R[cid]
    return simular(ambiente_de(r), r, ControladorReferencia, semente).eventos


def _avaliar(cid, eventos):
    r = R[cid]
    return avaliar(eventos, r, ambiente_de(r), carregar_esperado(cid))


def test_sala_da_v0_vira_residencia_de_um_comodo_com_os_mesmos_nomes():
    res = Residencia(carregar_sala())
    assert res.legado and res.ids == ["sala"] and not res.multi
    assert res.externa.sa == "SA-01" and res.rng_nome("SP-01") == "SP"


def test_sa_do_vao_vai_aos_dois_comodos_e_sp_so_ao_seu():
    res = Residencia(ambiente_de(R["M01"]))
    assert sorted(res.comodos_do_dispositivo("SA-02")) == ["cozinha", "sala"]
    assert res.comodos_do_dispositivo("SP-02") == ["cozinha"]
    assert "SP-02" not in res.permitidos("sala")


def test_cada_controlador_so_recebe_o_que_e_do_seu_comodo():
    fim = [e for e in _rodar("M01") if e["tipo"] == "FIM"][0]
    ent = fim["entregas_por_comodo"]
    assert "SP-02" not in ent["sala"] and "SP-01" not in ent["cozinha"]
    assert ent["sala"]["SA-02"] == ent["cozinha"]["SA-02"] > 0


def test_or13_detecta_evidencia_de_outro_comodo():
    ev = copy.deepcopy(_rodar("M01"))
    fim = [e for e in ev if e["tipo"] == "FIM"][0]
    fim["entregas_por_comodo"]["sala"]["SP-02"] = 3
    assert not _avaliar("M01", ev)["invariantes"]["OR-13"]["ok"]


def test_or14_detecta_atuacao_no_comodo_errado():
    ev = copy.deepcopy(_rodar("M01"))
    c = next(e for e in ev if e["tipo"] == "COMUTACAO" and e["comodo"] == "cozinha")
    c["origem"] = "ATU-01"
    assert not _avaliar("M01", ev)["invariantes"]["OR-14"]["ok"]


def test_vista_traduz_o_vao_em_entrada_e_saida():
    ev = _rodar("M01")
    coz = [e for e in vista(ev, "cozinha") if e["tipo"] == "CRUZOU_PORTA"]
    sala = [e for e in vista(ev, "sala") if e["tipo"] == "CRUZOU_PORTA"]
    assert [e["sentido"] for e in coz] == ["ENTRADA", "SAIDA"]
    assert [e["sentido"] for e in sala] == ["ENTRADA", "SAIDA", "ENTRADA"]


def test_metricas_da_residencia_somam_os_comodos():
    res = _avaliar("M03", _rodar("M03"))
    m, c = res["metricas"], res["comodos"]
    assert m["desperdicio_s"] == round(c["sala"]["metricas"]["desperdicio_s"] + c["cozinha"]["metricas"]["desperdicio_s"], 1)
    total = sum(m[k] for k in ("espelho_fiel_s", "erro_de_percepcao_s", "erro_de_sincronizacao_s", "espelho_nao_afirma_s"))
    assert abs(total - 2 * R["M03"]["duracao_ms"] / 1000) < 1


def test_mudar_de_comodo_sem_passagem_e_erro():
    r = copy.deepcopy(R["M01"])
    r["acoes"] = [{"t_ms": 1000, "ocupante": "morador", "acao": "ENTRAR"},
                  {"t_ms": 2000, "ocupante": "morador", "acao": "MUDAR_COMODO", "para": "quarto"}]
    with pytest.raises(ValueError):
        simular(ambiente_de(r), r, ControladorReferencia, 42)


def test_residencia_e_deterministica():
    assert simular(ambiente_de(R["M13"]), R["M13"], ControladorReferencia, 3).hash() == \
        simular(ambiente_de(R["M13"]), R["M13"], ControladorReferencia, 3).hash()
