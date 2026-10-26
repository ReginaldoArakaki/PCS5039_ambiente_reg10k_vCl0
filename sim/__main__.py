"""Executa um cenário.

Exemplos:
    python -m sim --cenario N01
    python -m sim --cenario FN02 --semente 7
    python -m sim --cenario FP01 --controlador alunos.grupo_exemplo
    python -m sim --cenario FP01 --controlador meu_pacote.modulo:MinhaClasse
"""
from __future__ import annotations

import argparse
import json
import sys

from catalogo import executar as executar_mod
from catalogo.executar import carregar_controlador, carregar_roteiros, configurar_raiz, executar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sim", description="Executa um cenário do incremento 0.")
    ap.add_argument("--cenario", required=True, help="ID do cenário (ex.: N01) ou caminho de um roteiro JSON")
    ap.add_argument("--controlador", default="referencia")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--json", action="store_true", help="imprime o resumo em JSON")
    ap.add_argument("--raiz", help="pasta de um repositório de versão (padrão: o núcleo ou REG10K_RAIZ)")
    a = ap.parse_args(argv)
    if a.raiz:
        configurar_raiz(a.raiz)

    if a.cenario.endswith(".json"):
        with open(a.cenario, encoding="utf-8") as f:
            roteiro = json.load(f)
    else:
        achados = carregar_roteiros([a.cenario])
        if not achados:
            print(f"Cenário {a.cenario} não encontrado em cenarios/roteiros/", file=sys.stderr)
            return 2
        roteiro = achados[0]

    fab = carregar_controlador(a.controlador)
    res = executar(roteiro, fab, a.semente)
    res.pop("_eventos", None)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        nome = getattr(fab, "nome", a.controlador)
        print(f"{roteiro['id']} — {roteiro.get('titulo', '')}  [{nome}, semente {a.semente}, {res['modo']}]")
        for k, v in res["metricas"].items():
            print(f"  {k:30} {v}")
        print("  asserções:")
        for k, v in res["assercoes"].items():
            if v["nivel"] == "REQUISITO":
                marca = "ok    " if v["ok"] else "FALHA "
            else:
                marca = "=ref  " if v["ok"] else "difere"
            print(f"    {k:4} {v['nivel'][:4].lower()}  {marca} {v['detalhe']}")
        falhas = [k for k, v in res["invariantes"].items() if not v["ok"]]
        print(f"  invariantes: {'todas respeitadas' if not falhas else falhas}")
        print(f"  eventos: {executar_mod.SAIDA / roteiro['id'] / nome / str(a.semente) / 'eventos.jsonl'}")
    return 0 if res["requisitos_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
