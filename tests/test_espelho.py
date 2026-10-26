"""v0dta: cômodo espelho, amostras e fidelidade."""
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from avaliacao.espelho import ROTULOS, amostras, svg_amostra
from avaliacao.oraculo import CLASSES_ESPELHO, Analise, _assinatura, avaliar
from catalogo.executar import carregar_esperado, carregar_roteiros, carregar_sala, descobrir_controladores
from hub.controlador import ControladorReferencia
from sim.motor import simular

SALA = carregar_sala()
ROTEIROS = carregar_roteiros()
R = {r["id"]: r for r in ROTEIROS}
CTRLS = descobrir_controladores()
ASSINATURAS = json.loads((Path(__file__).parent / "dados" / "assinaturas-v0dt.json").read_text())["assinaturas"]


@pytest.mark.parametrize("nome", list(CTRLS))
@pytest.mark.parametrize("roteiro", ROTEIROS, ids=[r["id"] for r in ROTEIROS])
def test_decisoes_e_atuacoes_identicas_as_da_v0dt(roteiro, nome):
    """CP-DTA-01: o espelho não muda nada na sala."""
    a = _assinatura(simular(SALA, roteiro, CTRLS[nome], 42).eventos)
    h = hashlib.sha256(json.dumps(a).encode()).hexdigest()
    assert h == ASSINATURAS[f"{roteiro['id']}|{nome}"]


def _analise(cid):
    r = R[cid]
    return Analise(simular(SALA, r, ControladorReferencia, 42).eventos, r, SALA)


@pytest.mark.parametrize("cid", ["N01", "FN01", "DT05", "DT08", "DT10"])
def test_classes_somam_a_duracao(cid):
    an = _analise(cid)
    for visao in ("R", "L"):
        segs = an.segmentos_espelho(visao)
        assert segs[0][0] == 0 and segs[-1][1] == R[cid]["duracao_ms"]
        assert all(a[1] == b[0] for a, b in zip(segs, segs[1:]))
        assert {c for _, _, c in segs} <= set(CLASSES_ESPELHO)


def test_causas_esperadas():
    assert _analise("FN01").classe_espelho(450_000) == "PERCEPCAO"   # morador parado, hub acha vazia
    assert _analise("DT05").classe_espelho(300_000) == "NAO_AFIRMA"  # enlace fora
    assert _analise("N01").classe_espelho(60_000) == "FIEL"


def test_espelho_nunca_usa_a_verdade():
    """DTA-03: o lado do espelho só tem dados que chegaram ao gêmeo."""
    for a in amostras(_analise("DT12")):
        for lado in ("R", "L"):
            texto = json.dumps(a[lado])
            assert "morador" not in texto and "rex" not in texto and "posic" not in texto


def test_tres_amostras_com_svg_valido():
    an = _analise("DT05")
    lista = amostras(an)
    assert [a["rotulo"] for a in lista] == list(ROTULOS)
    assert [a["t_ms"] for a in lista] == R["DT05"]["amostras_ms"]
    for a in lista:
        for visao in ("R", "L"):
            ElementTree.fromstring(svg_amostra(SALA, a, "teste", visao))


def test_assercao_espelho_e_metricas_no_resultado():
    r = R["DT10"]
    res = avaliar(simular(SALA, r, ControladorReferencia, 42).eventos, r, SALA, carregar_esperado("DT10"))
    assert res["assercoes"]["E1"]["ok"]
    m = res["metricas"]
    total = m["espelho_fiel_s"] + m["erro_de_percepcao_s"] + m["erro_de_sincronizacao_s"] + m["espelho_nao_afirma_s"]
    assert abs(total - r["duracao_ms"] / 1000) < 0.5
