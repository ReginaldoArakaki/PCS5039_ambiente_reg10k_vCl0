"""nucleo-v1.0: repositórios de versão (N1, N2, N4).

Uma versão montada a partir do núcleo, rodada de fora pelo lançador, tem de
dar as mesmas decisões que o conjunto de regressão do núcleo (assinaturas).
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

from nova_versao import montar  # noqa: E402

BASE = json.loads((RAIZ / "tests" / "dados" / "assinaturas-v1dt.json").read_text(encoding="utf-8"))["assinaturas"]


def _reg10k(raiz: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RAIZ / "reg10k.py"), "--raiz", str(raiz), *args],
                          capture_output=True, text=True, timeout=600)


@pytest.fixture(scope="module")
def v1(tmp_path_factory):
    d = tmp_path_factory.mktemp("V1")
    montar(d, "V1", "sala e cozinha", ["residencia-v1"])
    return d


def test_montagem_da_versao(v1):
    ids = sorted(p.stem for p in (v1 / "cenarios" / "roteiros").glob("*.json"))
    assert ids == [f"M{i:02d}" for i in range(1, 15)]
    assert (v1 / "ambiente" / "residencia-v1.json").exists() and not (v1 / "ambiente" / "sala.json").exists()
    fam = json.loads((v1 / "experimentos" / "familias.json").read_text(encoding="utf-8"))["familias"]
    assert sorted(c for v in fam.values() for c in v) == ids  # todo cenário da V1 está numa família
    assert json.loads((v1 / "versao.json").read_text(encoding="utf-8"))["nome"] == "V1"


def test_versao_de_fora_tem_as_mesmas_decisoes(v1):
    r = _reg10k(v1, "assinaturas", "gravar", "V1")
    assert r.returncode == 0, r.stderr
    atual = json.loads((v1 / "dados" / "assinaturas-V1.json").read_text(encoding="utf-8"))["assinaturas"]
    assert len(atual) == 28  # 14 cenários × (referência + grupo_exemplo da versão)
    assert all(BASE[k] == v for k, v in atual.items())


def test_validacao_e_catalogo_da_versao(v1):
    assert _reg10k(v1, "validar").returncode == 0
    r = _reg10k(v1, "catalogo", "--sementes", "0", "--cenarios", "M01", "M03")
    assert r.returncode == 0, r.stdout + r.stderr
    cat = json.loads((v1 / "saida" / "catalogo.json").read_text(encoding="utf-8"))
    assert cat["identidade"]["nome"] == "V1" and cat["identidade"]["nucleo"] == cat["versao"]
    assert list(cat["ambientes"]) == ["residencia-v1"]
    assert (v1 / "site" / "index.html").exists()
    # nucleo-v1.2: o catálogo de uma versão sem a sala da v0 também passa na validação
    r = _reg10k(v1, "validar")
    assert r.returncode == 0, r.stdout


def test_experimentos_csv_e_manifesto(v1):
    saida = v1 / "dados" / "teste.csv"
    r = _reg10k(v1, "experimentos", "--familias", "F3", "F7", "--sementes", "2", "--saida", str(saida))
    assert r.returncode == 0, r.stderr
    linhas = list(csv.DictReader(saida.open(encoding="utf-8")))
    assert {(x["familia"], x["cenario"]) for x in linhas} == {("F3", "M03"), ("F7", "M14")}
    assert len(linhas) == 4 and all(x["versao"] == "V1" and x["n_comodos"] == "2" for x in linhas)
    man = json.loads(saida.with_suffix(".manifesto.json").read_text(encoding="utf-8"))
    assert man["n_execucoes"] == 4 and man["sementes"] == [1, 2]
    assert "ambiente/residencia-v1.json" in man["entradas_sha256"]
    assert man["ressalva"].startswith("Resultados de simulação")


def test_experimentos_deterministicos(tmp_path):
    from experimentos.rodar import rodar
    a = rodar(tmp_path / "a.csv", 2, familias=["F3"], cenarios=["FP01"], log=lambda *_: None)["linhas"]
    b = rodar(tmp_path / "b.csv", 2, familias=["F3"], cenarios=["FP01"], log=lambda *_: None)["linhas"]
    assert a == b and len(a) == 2


def test_ordem_das_versoes():
    from catalogo.executar import ordem_versao
    nomes = ["v2dt", "v1dt.1", "v0dta", "v1dt", "v0", "v0dt", "v3dt", "v1dtb"]
    assert sorted(nomes, key=ordem_versao) == ["v0", "v0dt", "v0dta", "v1dt", "v1dtb", "v1dt.1", "v2dt", "v3dt"]


def test_quatro_comodos_com_passagens_nas_duas_direcoes(tmp_path):
    """N3: motor, oráculo e página com 4 cômodos e passagem interna em parede horizontal."""
    import shutil
    dados = RAIZ / "tests" / "dados"
    (tmp_path / "ambiente").mkdir()
    (tmp_path / "cenarios" / "roteiros").mkdir(parents=True)
    shutil.copy2(dados / "residencia-teste-4.json", tmp_path / "ambiente" / "residencia-teste-4.json")
    shutil.copy2(dados / "roteiro-TQ01.json", tmp_path / "cenarios" / "roteiros" / "TQ01.json")
    (tmp_path / "versao.json").write_text('{"nome": "T4", "titulo": "teste de 4 cômodos"}', encoding="utf-8")
    assert _reg10k(tmp_path, "validar").returncode == 0
    r = _reg10k(tmp_path, "catalogo", "--sementes", "0")
    assert r.returncode == 0, r.stdout + r.stderr
    cat = json.loads((tmp_path / "saida" / "catalogo.json").read_text(encoding="utf-8"))
    e = cat["execucoes"][0]
    assert all(v["ok"] for v in e["invariantes"].values())
    ocupado = {c: m["metricas"]["tempo_ocupada_s"] for c, m in e["comodos"].items()}
    assert set(ocupado) == {"sala", "cozinha", "quarto", "banheiro"}
    assert ocupado["cozinha"] == 0 and min(ocupado["sala"], ocupado["quarto"], ocupado["banheiro"]) > 30


def test_comparar_versoes(tmp_path):
    """nucleo-v1.2: o comparador junta os CSV e resume só os cenários G* por família e versão."""
    from experimentos.comparar import comparar, ler
    linhas = []
    for nome, sementes in (("a", 2), ("b", 1)):
        p = tmp_path / f"{nome}.csv"
        p.write_text("versao,nucleo,n_comodos,familia,cenario,controlador,requisitos_ok,desperdicio_s,acionamentos\n"
                     + "".join(f"V{nome},n1,{1 if nome == 'a' else 2},F3,G03-X,referencia,True,{10 * (s + 1)},2\n" for s in range(sementes))
                     + f"V{nome},n1,1,F3,FP01,referencia,False,999,9\n", encoding="utf-8")
        linhas += ler([p])
    res = comparar(linhas)
    assert [(r["versao"], r["n"], r["n_comodos"], r["requisitos_ok_pct"], r["desperdicio_s_media"]) for r in res] == [
        ("Va", 2, 1, 100.0, 15.0), ("Vb", 1, 2, 100.0, 10.0)]
