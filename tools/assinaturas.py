"""Regressão por assinatura das decisões locais (guia de convenções §8).

Antes de mexer no motor de um incremento, grave a assinatura da versão atual;
depois, compare. A assinatura é o SHA-256 das camadas DECISAO e ATUACAO de cada
cenário e controlador, com a semente 42.

Uso, dentro da pasta do projeto:
    python tools/assinaturas.py gravar v0dta     # cria tests/dados/assinaturas-v0dta.json
    python tools/assinaturas.py comparar v0dta   # lista o que mudou; sai com código 1 se algo mudou
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from avaliacao.oraculo import _assinatura  # noqa: E402
from catalogo.executar import carregar_roteiros, carregar_sala, descobrir_controladores  # noqa: E402
from sim.motor import simular  # noqa: E402


def calcular() -> dict[str, str]:
    sala, out = carregar_sala(), {}
    for r in carregar_roteiros():
        for nome, fab in descobrir_controladores().items():
            a = _assinatura(simular(sala, r, fab, 42).eventos)
            out[f"{r['id']}|{nome}"] = hashlib.sha256(json.dumps(a).encode()).hexdigest()
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("gravar", "comparar"):
        print(__doc__)
        return 2
    acao, versao = argv
    arq = RAIZ / "tests" / "dados" / f"assinaturas-{versao}.json"
    atual = calcular()
    if acao == "gravar":
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps({"versao": versao, "descricao": f"SHA-256 das camadas DECISAO e ATUACAO (semente 42) na versão {versao}",
                                   "assinaturas": atual}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{arq.relative_to(RAIZ)}: {len(atual)} assinaturas")
        return 0
    base = json.loads(arq.read_text(encoding="utf-8"))["assinaturas"]
    mudou = sorted(k for k in base if k in atual and base[k] != atual[k])
    sumiu = sorted(set(base) - set(atual))
    novo = sorted(set(atual) - set(base))
    for k in mudou:
        print(f"MUDOU   {k}")
    for k in sumiu:
        print(f"SUMIU   {k}")
    print(f"{len(base) - len(mudou) - len(sumiu)} iguais, {len(mudou)} mudaram, {len(sumiu)} sumiram, {len(novo)} novos (cenários ou controladores)")
    return 1 if mudou or sumiu else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
