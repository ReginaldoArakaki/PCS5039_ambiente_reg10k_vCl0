"""Rodada de experimentos: famílias × cenários × controladores × sementes × modos.

Cada execução vira uma linha de CSV com as métricas do oráculo. Junto do CSV
vai um manifesto com tudo o que é preciso para reproduzir o dado: núcleo e
versão (tag e commit), sementes, modos, controladores e o hash de cada arquivo
de entrada. Os números são de simulação, não de medição (ressalva P7).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

from avaliacao.oraculo import avaliar
from catalogo import executar as ex
from experimentos.familias import FAMILIAS, carregar
from sim.motor import simular

METRICAS = (
    "desperdicio_s", "escuro_com_ocupante_s", "apagamentos_indevidos", "acionamentos",
    "latencia_reacao_ms_p95", "latencia_reacao_ms_max", "atraso_percebido_ms_max", "desperdicio_por_saida_s_max",
    "ocupacao_desconhecida_s", "tempo_ocupada_s", "tempo_luz_acesa_s",
    "atualidade_gemeo_ms_p95", "gemeo_nao_atual_s", "comando_remoto_ms_p95", "comandos_remotos",
    "comandos_vencidos_executados", "efeitos_duplicados_remotos", "reconciliacao_ms_max", "divergencia_alem_prazo_s",
    "eventos_nao_entregues", "fila_max",
    "espelho_fiel_pct", "espelho_fiel_s", "erro_de_percepcao_s", "erro_de_sincronizacao_s", "espelho_nao_afirma_s",
)
COLUNAS = ("versao", "nucleo", "ambiente", "n_comodos", "n_moradores", "familia", "cenario", "tipo",
           "controlador", "semente", "modo", "modo_rede", "requisitos_ok", "invariantes_ok", "n_eventos") + METRICAS
RESSALVA = "Resultados de simulação, não de medição (P7): valem para o modelo e os parâmetros declarados."


def _git(pasta: Path, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _uma(tarefa: tuple) -> dict:
    """Executa uma combinação; roda também em outro processo (por isso recebe só dados simples)."""
    roteiro, ctrl_spec, semente, modo, familia = tarefa
    sala = ex.ambiente_de(roteiro)
    fab = ex.carregar_controlador(ctrl_spec)
    modo_efetivo = None if modo == "CENARIO" else modo
    reg = simular(sala, roteiro, fab, semente, modo_efetivo)
    av = avaliar(reg.eventos, roteiro, sala, ex.carregar_esperado(roteiro["id"]), None)
    m = av["metricas"]
    n_comodos = len(sala.get("comodos") or [None])
    return {
        "ambiente": roteiro.get("ambiente", "sala"), "n_comodos": n_comodos, "n_moradores": len(sala.get("ocupantes", [])),
        "familia": familia, "cenario": roteiro["id"], "tipo": roteiro["tipo"],
        "controlador": getattr(fab, "nome", ctrl_spec), "semente": semente,
        "modo": (modo_efetivo or roteiro.get("modo", "IDEAL")).upper(),
        "modo_rede": (roteiro.get("rede", {}).get("modo") or modo_efetivo or roteiro.get("modo", "IDEAL")).upper(),
        "requisitos_ok": av["requisitos_ok"],
        "invariantes_ok": all(v["ok"] for v in av["invariantes"].values()),
        "n_eventos": len(reg.eventos),
        **{k: m.get(k) for k in METRICAS},
    }


def rodar(saida: Path, sementes: int = 30, modos=("CENARIO",), familias: Optional[list[str]] = None,
          controladores: Optional[list[str]] = None, cenarios: Optional[list[str]] = None,
          processos: int = 1, log=print) -> dict:
    roteiros = {r["id"]: r for r in ex.carregar_roteiros()}
    mapa = carregar(ex.RAIZ_VERSAO, set(roteiros))
    if familias:
        mapa = {f: v for f, v in mapa.items() if f in familias}
    if cenarios:
        mapa = {f: [c for c in v if c in cenarios] for f, v in mapa.items()}
    specs = controladores or ["referencia"]
    tarefas = [(roteiros[c], spec, s, modo, f)
               for f, ids in mapa.items() for c in ids for spec in specs
               for modo in modos for s in range(1, sementes + 1)]
    ident = ex.identidade()
    log(f"{len(tarefas)} execuções: {sum(len(v) for v in mapa.values())} cenários em {len(mapa)} famílias, "
        f"{len(specs)} controlador(es), {len(modos)} modo(s), {sementes} sementes")
    if processos > 1:
        with ProcessPoolExecutor(processos) as pool:
            linhas = list(pool.map(_uma, tarefas, chunksize=8))
    else:
        linhas = []
        for i, t in enumerate(tarefas, 1):
            linhas.append(_uma(t))
            if i % 200 == 0:
                log(f"  {i}/{len(tarefas)}")
    for ln in linhas:
        ln.update(versao=ident["nome"], nucleo=ident["nucleo"])

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)

    usados = sorted({c for v in mapa.values() for c in v})
    entradas = {}
    for c in usados:
        for p in (ex.CENARIOS / "roteiros" / f"{c}.json", ex.CENARIOS / "esperado" / f"{c}.json"):
            if p.exists():
                entradas[str(p.relative_to(ex.RAIZ_VERSAO) if p.is_relative_to(ex.RAIZ_VERSAO) else p)] = _sha(p)
    for amb in sorted({roteiros[c].get("ambiente", "sala") for c in usados}):
        p = ex.caminho_ambiente(amb)
        entradas[str(p.relative_to(ex.RAIZ_VERSAO) if p.is_relative_to(ex.RAIZ_VERSAO) else p)] = _sha(p)
    manifesto = {
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "comando": " ".join(sys.argv),
        "versao": ident,
        "nucleo": {"nome": ex.VERSAO, "commit": _git(ex.RAIZ, "rev-parse", "HEAD"),
                   "descricao_git": _git(ex.RAIZ, "describe", "--tags", "--always", "--dirty")},
        "repositorio_versao": None if ex.RAIZ_VERSAO == ex.RAIZ else {
            "commit": _git(ex.RAIZ_VERSAO, "rev-parse", "HEAD"),
            "descricao_git": _git(ex.RAIZ_VERSAO, "describe", "--tags", "--always", "--dirty")},
        "python": platform.python_version(),
        "sementes": list(range(1, sementes + 1)),
        "modos": list(modos),
        "controladores": specs,
        "familias": {f: {"nome": FAMILIAS[f]["nome"], "cenarios": v} for f, v in mapa.items()},
        "n_execucoes": len(linhas),
        "observacoes": ["OR-12 (execução pareada sem falha de rede) não é calculada nos experimentos.",
                        "modo CENARIO = o modo declarado em cada roteiro."],
        "csv": {"arquivo": saida.name, "sha256": _sha(saida), "colunas": list(COLUNAS)},
        "entradas_sha256": entradas,
        "ressalva": RESSALVA,
    }
    man = saida.with_suffix(".manifesto.json")
    man.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"linhas": linhas, "manifesto": manifesto, "csv": saida, "arquivo_manifesto": man}


def resumo(linhas: list[dict]) -> list[dict]:
    """Por família e controlador: n, % com requisitos ok e a média das métricas que a família mede."""
    grupos: dict = {}
    for ln in linhas:
        grupos.setdefault((ln["familia"], ln["controlador"]), []).append(ln)
    out = []
    for (f, c), lns in sorted(grupos.items()):
        item = {"familia": f, "controlador": c, "n": len(lns),
                "requisitos_ok_pct": round(100 * sum(1 for x in lns if str(x["requisitos_ok"]) == "True") / len(lns), 1)}
        for k in FAMILIAS[f]["mede"]:
            vals = [float(x[k]) for x in lns if x.get(k) not in (None, "")]
            item[k] = round(sum(vals) / len(vals), 2) if vals else None
        out.append(item)
    return out
