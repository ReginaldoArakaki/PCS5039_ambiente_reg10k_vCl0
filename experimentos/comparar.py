"""Compara versões a partir dos CSV de experimentos (nucleo-v1.2).

Junta os CSV de várias versões e resume, por família, versão e controlador,
só os cenários equivalentes entre as casas: por padrão, os gerados por planta
(prefixo G), que repetem os mesmos episódios em qualquer planta.

Uso:
    python -m experimentos.comparar V0/dados/experimentos-V0-*.csv V1/dados/... V2/dados/... \\
        --saida comparacao.csv

Saída: tabela no terminal e, com --saida, um CSV com uma linha por
(família, versão, controlador): n, cômodos, % com requisitos atendidos, média,
mínimo e máximo de cada métrica da família, e os núcleos que geraram os dados.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

from experimentos.familias import FAMILIAS
from experimentos.rodar import RESSALVA


def ler(arquivos: list[Path], prefixo: str = "G") -> list[dict]:
    linhas = []
    for a in arquivos:
        with open(a, encoding="utf-8") as f:
            linhas += [ln for ln in csv.DictReader(f) if ln["cenario"].startswith(prefixo)]
    return linhas


def comparar(linhas: list[dict]) -> list[dict]:
    grupos: dict = {}
    for ln in linhas:
        grupos.setdefault((ln["familia"], ln["versao"], ln["controlador"]), []).append(ln)
    out = []
    for (fam, versao, ctrl), lns in sorted(grupos.items()):
        item = {"familia": fam, "versao": versao, "controlador": ctrl, "n": len(lns),
                "n_comodos": max(int(x["n_comodos"]) for x in lns),
                "n_cenarios": len({x["cenario"] for x in lns}),
                "nucleo": ",".join(sorted({x["nucleo"] for x in lns})),
                "requisitos_ok_pct": round(100 * sum(x["requisitos_ok"] == "True" for x in lns) / len(lns), 1)}
        for k in FAMILIAS[fam]["mede"]:
            vals = [float(x[k]) for x in lns if x.get(k) not in (None, "")]
            item[f"{k}_media"] = round(statistics.fmean(vals), 2) if vals else None
            item[f"{k}_min"] = min(vals) if vals else None
            item[f"{k}_max"] = max(vals) if vals else None
        out.append(item)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m experimentos.comparar", description=__doc__.split("\n")[0])
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--prefixo", default="G", help="cenários comparados (padrão: G, os gerados por planta)")
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args(argv)
    res = comparar(ler(a.csv, a.prefixo))
    if not res:
        print("Nenhum cenário com esse prefixo nos arquivos.")
        return 1
    for it in res:
        medias = "  ".join(f"{k[:-6]}={v}" for k, v in it.items() if k.endswith("_media"))
        print(f"{it['familia']}  {it['versao']:4} {it['n_comodos']} cômodo(s)  {it['controlador']:14} "
              f"n={it['n']:<4} requisitos {it['requisitos_ok_pct']:5}%  {medias}")
    if a.saida:
        campos = list(dict.fromkeys(k for it in res for k in it))
        with open(a.saida, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(res)
        print(f"\n{a.saida}")
    print(f"\n{RESSALVA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
