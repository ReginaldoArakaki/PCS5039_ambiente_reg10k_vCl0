"""O catálogo como teste: referência, controladores dos alunos e determinação."""
import pytest

from avaliacao.oraculo import avaliar
from catalogo.executar import (carregar_esperado, carregar_roteiros, ambiente_de, carregar_sala,
                               descobrir_controladores)
from hub.controlador import Controlador, ControladorReferencia
from sim.motor import simular

SALA = carregar_sala()
ROTEIROS = carregar_roteiros()
IDS = [r["id"] for r in ROTEIROS]
CTRLS = descobrir_controladores()


def test_catalogo_tem_32_cenarios_de_regressao_e_14_da_v1dt():
    antigos = [r for r in ROTEIROS if not r["id"].startswith("M")]
    tipos = [r["tipo"] for r in antigos]
    assert len(antigos) == 32
    assert tipos.count("NORMAL") == 6 and tipos.count("FALSO_POSITIVO") == 3
    assert tipos.count("FALSO_NEGATIVO") == 5 and tipos.count("FALHA") == 6
    assert tipos.count("GEMEO_DIGITAL") == 12
    novos = [r for r in ROTEIROS if r["id"].startswith("M")]
    assert len(novos) == 14 and all(r["versao"] == "v1dt" and r["ambiente"] == "residencia-v1" for r in novos)
    assert all("ambiente" not in r for r in antigos)
    assert all(r.get("versao", "v0") == "v0" for r in ROTEIROS if r["id"][0] not in "DM")
    assert all(r["versao"] == "v0dt" for r in ROTEIROS if r["id"].startswith("DT"))


@pytest.mark.parametrize("roteiro", ROTEIROS, ids=IDS)
def test_referencia_passa_em_todas_as_assercoes(roteiro):
    amb = ambiente_de(roteiro)
    res = avaliar(simular(amb, roteiro, ControladorReferencia, 42).eventos, roteiro, amb,
                  carregar_esperado(roteiro["id"]))
    falhas = {k: v["detalhe"] for k, v in res["assercoes"].items() if not v["ok"]}
    assert not falhas, falhas
    assert res["aprovado"]


@pytest.mark.parametrize("nome", [n for n in CTRLS if n != "referencia"])
@pytest.mark.parametrize("roteiro", ROTEIROS, ids=IDS)
def test_controladores_dos_alunos_respeitam_invariantes(roteiro, nome):
    amb = ambiente_de(roteiro)
    res = avaliar(simular(amb, roteiro, CTRLS[nome], 42).eventos, roteiro, amb, None)
    violadas = {k: v["violacoes"] for k, v in res["invariantes"].items() if not v["ok"]}
    assert not violadas, violadas


@pytest.mark.parametrize("nome", list(CTRLS))
def test_controladores_implementam_a_interface(nome):
    assert isinstance(CTRLS[nome](), Controlador)


@pytest.mark.parametrize("cid", ["N04", "FN02", "F05"])
def test_mesma_semente_mesmo_registro(cid):
    r = next(x for x in ROTEIROS if x["id"] == cid)
    h1 = simular(SALA, r, ControladorReferencia, 7).hash()
    h2 = simular(SALA, r, ControladorReferencia, 7).hash()
    assert h1 == h2


def test_sementes_diferentes_mudam_o_modo_realista():
    r = next(x for x in ROTEIROS if x["id"] == "FN02")
    assert simular(SALA, r, ControladorReferencia, 1).hash() != simular(SALA, r, ControladorReferencia, 2).hash()
