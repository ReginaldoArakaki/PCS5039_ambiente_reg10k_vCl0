"""Protocolo de experimentos: gera o CSV e o manifesto de uma versão.

Exemplos (no núcleo):
    python -m experimentos --sementes 30
    python -m experimentos --familias F1 F3 --sementes 10 --modos IDEAL REALISTA
    python -m experimentos --controladores referencia alunos.grupo_exemplo --processos 4

Num repositório de versão:
    python nucleo/reg10k.py experimentos --sementes 30

Saída padrão: <raiz>/dados/experimentos-<versão>-<data>.csv e o .manifesto.json ao lado.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m experimentos", description=__doc__.split("\n")[0])
    ap.add_argument("--raiz", help="pasta de um repositório de versão (padrão: o núcleo ou REG10K_RAIZ)")
    ap.add_argument("--sementes", type=int, default=30)
    ap.add_argument("--modos", nargs="*", default=["CENARIO"], choices=["CENARIO", "IDEAL", "REALISTA"])
    ap.add_argument("--familias", nargs="*")
    ap.add_argument("--cenarios", nargs="*")
    ap.add_argument("--controladores", nargs="*", help="padrão: referencia")
    ap.add_argument("--processos", type=int, default=1)
    ap.add_argument("--saida", help="arquivo CSV (padrão: <raiz>/dados/experimentos-<versão>-<data>.csv)")
    ap.add_argument("--resumo", help="só imprime o resumo de um CSV já gerado")
    a = ap.parse_args(argv)

    if a.raiz:
        os.environ["REG10K_RAIZ"] = str(Path(a.raiz).resolve())  # também para os processos filhos
    from catalogo import executar as ex
    if a.raiz:
        ex.configurar_raiz(a.raiz)
    from experimentos.rodar import RESSALVA, resumo, rodar

    if a.resumo:
        with open(a.resumo, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    else:
        nome = ex.identidade()["nome"]
        saida = Path(a.saida) if a.saida else ex.RAIZ_VERSAO / "dados" / f"experimentos-{nome}-{dt.date.today():%Y%m%d}.csv"
        r = rodar(saida, a.sementes, a.modos, a.familias, a.controladores, a.cenarios, a.processos)
        linhas = r["linhas"]
        print(f"CSV: {r['csv']}\nManifesto: {r['arquivo_manifesto']}")
    print()
    for item in resumo(linhas):
        extras = "  ".join(f"{k}={v}" for k, v in item.items() if k not in ("familia", "controlador", "n", "requisitos_ok_pct"))
        print(f"{item['familia']}  {item['controlador']:16} n={item['n']:<5} requisitos {item['requisitos_ok_pct']:5}%  {extras}")
    print(f"\n{RESSALVA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
