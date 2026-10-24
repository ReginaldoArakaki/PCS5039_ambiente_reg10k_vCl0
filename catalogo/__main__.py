"""Gera o catálogo completo e a página de navegação.

Exemplos:
    python -m catalogo                       # todos os cenários, referência + alunos/
    python -m catalogo --sementes 0          # sem a distribuição do modo realista (mais rápido)
    python -m catalogo --controladores referencia alunos.grupo_exemplo
    python -m catalogo --cenarios N01 FP01 --sem-site

Saída: saida/catalogo.json, saida/<cenário>/<controlador>/<semente>/ e site/index.html.
Código de saída diferente de zero se a referência falhar em alguma asserção,
se algum controlador violar invariantes ou se alguma execução não for
determinística.
"""
from __future__ import annotations

import argparse
import sys
import time

from catalogo.executar import carregar_controlador, descobrir_controladores, gerar_catalogo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m catalogo", description=__doc__.split("\n")[0])
    ap.add_argument("--controladores", nargs="*", help="padrão: referência e todos os pacotes em alunos/")
    ap.add_argument("--cenarios", nargs="*")
    ap.add_argument("--sementes", type=int, default=30, help="sementes do modo realista (0 desliga)")
    ap.add_argument("--sem-site", action="store_true")
    a = ap.parse_args(argv)

    if a.controladores:
        ctrls = {}
        for spec in a.controladores:
            fab = carregar_controlador(spec)
            ctrls[getattr(fab, "nome", spec)] = fab
    else:
        ctrls = descobrir_controladores()

    t0 = time.time()
    print(f"Controladores: {', '.join(ctrls)}")
    cat = gerar_catalogo(ctrls, a.cenarios, a.sementes)
    print(f"Catálogo: saida/catalogo.json ({len(cat['execucoes'])} execuções, {time.time() - t0:.1f} s)")
    if not a.sem_site:
        from catalogo.site import gerar_site
        caminho = gerar_site(cat)
        print(f"Página: {caminho}")
    if cat["problemas"]:
        print("\nProblemas:")
        for p in cat["problemas"]:
            print(f"  - {p}")
        return 1
    print("Sem problemas: referência aprovada, invariantes respeitadas, execuções determinísticas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
