"""nucleo-v1.1: gerador de cenários por planta (CP-V2-02).

As mesmas famílias, geradas para a sala (V0), a residência da V1 e uma casa de
4 cômodos, passam nas invariantes e nos requisitos com a referência.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from avaliacao.oraculo import avaliar
from catalogo.validar import erros
from experimentos.gerador import Planta, gerar
from hub.controlador import ControladorReferencia
from sim.motor import simular

RAIZ = Path(__file__).resolve().parent.parent
PLANTAS = {
    "sala": RAIZ / "cenarios" / "sala.json",
    "residencia-v1": RAIZ / "cenarios" / "residencia-v1.json",
    "residencia-teste-4": RAIZ / "tests" / "dados" / "residencia-teste-4.json",
}
QUANTOS = {"sala": 8, "residencia-v1": 16, "residencia-teste-4": 32}  # nucleo-v1.3: + F8 e F9 por cômodo


def _cfg(nome):
    return json.loads(PLANTAS[nome].read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome", list(PLANTAS))
def test_familias_geradas(nome):
    cs = gerar(_cfg(nome), nome, "v2dt")
    assert len(cs) == QUANTOS[nome]
    assert len({r["id"] for r, _ in cs}) == len(cs)
    assert {r["familia"] for r, _ in cs} == {"F1", "F2", "F4", "F5", "F6", "F7", "F8", "F9"} | ({"F3"} if nome != "sala" else set())
    for r, e in cs:
        assert not erros("roteiro", r), r["id"]
        assert not erros("esperado", e), r["id"]
    assert gerar(_cfg(nome), nome, "v2dt") == cs  # determinístico


@pytest.mark.parametrize("nome", list(PLANTAS))
def test_referencia_passa_nos_cenarios_gerados(nome):
    cfg = _cfg(nome)
    for r, e in gerar(cfg, nome, "v2dt"):
        av = avaliar(simular(cfg, r, ControladorReferencia, 42).eventos, r, cfg, e, None)
        falhas = {k: v["detalhe"] for k, v in av["assercoes"].items() if not v["ok"]}
        assert not falhas, (r["id"], falhas)


def test_caminho_mais_curto_na_casa_de_4_comodos():
    p = Planta(_cfg("residencia-teste-4"), "residencia-teste-4")
    assert p.caminho("sala", "banheiro") == ["sala", "quarto", "banheiro"]
    assert p.caminho("cozinha", "quarto") == ["cozinha", "sala", "quarto"]


def test_desperdicio_por_saida_termina_quando_alguem_volta():
    """nucleo-v1.1: sair do cômodo e voltar antes do apagamento não conta como uma saída longa."""
    cfg = _cfg("residencia-v1")
    r = next(r for r, _ in gerar(cfg, "residencia-v1", "v2dt") if r["id"] == "G01-cozinha")
    av = avaliar(simular(cfg, r, ControladorReferencia, 42).eventos, r, cfg, None, None)
    assert av["comodos"]["sala"]["metricas"]["desperdicio_por_saida_s_max"] < 70
