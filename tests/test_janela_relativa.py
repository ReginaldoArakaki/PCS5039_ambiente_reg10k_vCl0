"""nucleo-v1.1: asserções com janela relativa a um evento da verdade (CP-V2-03).

As janelas absolutas dos esperados foram calibradas para a semente 42; com
outras sementes, o morador chega ao vão em outro instante (M01, semente 25:
cruzou aos 44,1 s e a janela acabava em 44 s). Com a janela relativa ao
cruzamento, o mesmo M01 passa em todas as sementes.
"""
from __future__ import annotations

import pytest

from avaliacao.oraculo import avaliar
from catalogo.executar import ambiente_de, carregar_esperado, carregar_roteiros
from hub.controlador import ControladorReferencia
from sim.motor import simular

ENTRA = {"evento": "CRUZOU_PORTA", "sentido": "ENTRADA"}
SAI = {"evento": "CRUZOU_PORTA", "sentido": "SAIDA"}
M01_RELATIVO = {"cenario": "M01", "assercoes": [
    {"id": "R1", "nivel": "REQUISITO", "entao": {"tipo": "luz", "comodo": "cozinha", "valor": "ACESA", "apos": ENTRA, "ate_ms": 1000}},
    {"id": "R2", "nivel": "REQUISITO", "entao": {"tipo": "luz", "comodo": "cozinha", "valor": "APAGADA", "apos": SAI, "em_ms": 75000}},
    {"id": "R3", "nivel": "REQUISITO", "entao": {"tipo": "luz", "comodo": "sala", "valor": "APAGADA", "apos": SAI, "em_ms": 75000}},
    {"id": "R4", "nivel": "REQUISITO", "entao": {"tipo": "luz", "comodo": "sala", "valor": "ACESA", "apos": {**ENTRA, "ocorrencia": 2}, "ate_ms": 1000}},
    {"id": "R5", "nivel": "REQUISITO", "entao": {"tipo": "luz_constante", "comodo": "sala", "valor": "ACESA", "apos": ENTRA, "entre_ms": [1000, 30000]}},
]}


@pytest.fixture(scope="module")
def m01():
    r = carregar_roteiros(["M01"])[0]
    return r, ambiente_de(r)


def test_janela_absoluta_falha_na_semente_25(m01):
    r, sala = m01
    av = avaliar(simular(sala, r, ControladorReferencia, 25).eventos, r, sala, carregar_esperado("M01"), None)
    assert not av["assercoes"]["A1"]["ok"]


@pytest.mark.parametrize("semente", range(1, 31))
def test_janela_relativa_passa_em_todas_as_sementes(m01, semente):
    r, sala = m01
    av = avaliar(simular(sala, r, ControladorReferencia, semente).eventos, r, sala, M01_RELATIVO, None)
    falhas = {k: v["detalhe"] for k, v in av["assercoes"].items() if not v["ok"]}
    assert not falhas


def test_ancora_ausente_falha_com_explicacao(m01):
    r, sala = m01
    esp = {"cenario": "M01", "assercoes": [{"id": "X", "nivel": "REQUISITO", "entao": {
        "tipo": "luz", "comodo": "cozinha", "valor": "ACESA", "apos": {**ENTRA, "ocorrencia": 9}, "ate_ms": 1000}}]}
    av = avaliar(simular(sala, r, ControladorReferencia, 42).eventos, r, sala, esp, None)
    assert not av["assercoes"]["X"]["ok"] and "não ocorreu" in av["assercoes"]["X"]["detalhe"]


def test_sala_da_v0_tambem_aceita_janela_relativa():
    r = carregar_roteiros(["N01"])[0]
    sala = ambiente_de(r)
    esp = {"cenario": "N01", "assercoes": [{"id": "R1", "nivel": "REQUISITO", "entao": {
        "tipo": "luz", "valor": "ACESA", "apos": ENTRA, "ate_ms": 1000}}]}
    for s in (1, 7, 42):
        av = avaliar(simular(sala, r, ControladorReferencia, s).eventos, r, sala, esp, None)
        assert av["assercoes"]["R1"]["ok"], av["assercoes"]["R1"]["detalhe"]
