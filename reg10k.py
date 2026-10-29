"""Executa o núcleo Reg10k a partir de um repositório de versão (nucleo-v1.0).

Num repositório de versão (reg10k-V0 … reg10k-V4), o núcleo fica na subpasta
`nucleo/` (submódulo git fixado numa tag). Na raiz do repositório de versão:

    python nucleo/reg10k.py catalogo                 # catálogo e página da versão (site/index.html)
    python nucleo/reg10k.py catalogo --sementes 0    # sem a distribuição do modo realista
    python nucleo/reg10k.py sim --cenario N01        # um cenário
    python nucleo/reg10k.py validar                  # JSON da versão contra os schemas do núcleo
    python nucleo/reg10k.py experimentos --sementes 30
    python nucleo/reg10k.py gerador --ambiente casa-a --versao v2dt   # cenários G* das famílias F1–F7
    python nucleo/reg10k.py comparar ../V0/dados/x.csv ../V1/dados/y.csv     # compara versões (cenários G*)
    python nucleo/reg10k.py assinaturas gravar V0    # dados/assinaturas-V0.json
    python nucleo/reg10k.py assinaturas comparar V0

A raiz da versão é a pasta atual. Para outra pasta: `python nucleo/reg10k.py --raiz PASTA catalogo`.
Dentro do próprio núcleo, os comandos de sempre continuam valendo (`python -m catalogo` etc.).
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

NUCLEO = Path(__file__).resolve().parent
COMANDOS = {
    "catalogo": ("modulo", "catalogo"),
    "sim": ("modulo", "sim"),
    "validar": ("modulo", "catalogo.validar"),
    "experimentos": ("modulo", "experimentos"),
    "gerador": ("modulo", "experimentos.gerador"),
    "comparar": ("modulo", "experimentos.comparar"),
    "assinaturas": ("arquivo", str(NUCLEO / "tools" / "assinaturas.py")),
}


def main(argv: list[str]) -> int:
    raiz = Path.cwd()
    if argv[:1] == ["--raiz"] and len(argv) >= 2:
        raiz, argv = Path(argv[1]), argv[2:]
    if not argv or argv[0] not in COMANDOS:
        print(__doc__)
        return 2
    cmd, resto = argv[0], argv[1:]
    raiz = raiz.resolve()
    if raiz != NUCLEO:
        os.environ["REG10K_RAIZ"] = str(raiz)  # lido por catalogo.executar ao ser importado
    sys.path.insert(0, str(NUCLEO))
    tipo, alvo = COMANDOS[cmd]
    sys.argv = [f"reg10k {cmd}", *resto]
    try:
        if tipo == "modulo":
            runpy.run_module(alvo, run_name="__main__", alter_sys=True)
        else:
            runpy.run_path(alvo, run_name="__main__")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
