"""Validação dos arquivos JSON contra os schemas (plano §8.1)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

RAIZ = Path(__file__).resolve().parent.parent
SCHEMAS = RAIZ / "schemas"


def _registro() -> Registry:
    recursos = []
    for p in SCHEMAS.glob("*.schema.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        r = Resource.from_contents(s)
        recursos += [(s["$id"], r), (p.name, r)]
    return Registry().with_resources(recursos)


_REG = None


def validador(nome: str) -> Draft202012Validator:
    global _REG
    _REG = _REG or _registro()
    schema = json.loads((SCHEMAS / f"{nome}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=_REG)


def erros(nome: str, doc) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}"
            for e in validador(nome).iter_errors(doc)]


def validar_tudo(com_saida: bool = True) -> list[str]:
    """Valida ambientes, roteiros, esperados e (se existirem) as saídas geradas da versão em uso."""
    from catalogo import executar
    problemas: list[str] = []
    ler = lambda p: json.loads(p.read_text(encoding="utf-8"))
    cen = executar.CENARIOS
    base = executar.RAIZ_VERSAO
    rel = lambda p: p.relative_to(base) if p.is_relative_to(base) else p
    # ambientes da versão (no núcleo: sala.json e residencia-*.json); um ambiente com "comodos" é uma residência
    dirs = [d for d in executar.AMBIENTES if base == RAIZ or d != executar.NUCLEO_CENARIOS]
    for d in dirs:
        for p in sorted(d.glob("*.json")):
            doc = ler(p)
            problemas += [f"{p.name}: {m}" for m in erros("residencia" if "comodos" in doc else "sala", doc)]
    for p in sorted((cen / "roteiros").glob("*.json")):
        problemas += [f"roteiros/{p.name}: {m}" for m in erros("roteiro", ler(p))]
    for p in sorted((cen / "esperado").glob("*.json")):
        problemas += [f"esperado/{p.name}: {m}" for m in erros("esperado", ler(p))]
    saida = executar.SAIDA
    if com_saida and saida.exists():
        v_ev = validador("evento")
        for p in sorted(saida.glob("*/*/*/eventos.jsonl")):
            for i, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                for e in v_ev.iter_errors(json.loads(linha)):
                    problemas.append(f"{rel(p)}:{i}: {e.message}")
                    break
        for p in sorted(saida.glob("*/*/*/metricas.json")):
            problemas += [f"{rel(p)}: {m}" for m in erros("metricas", ler(p))]
        if (saida / "catalogo.json").exists():
            problemas += [f"catalogo.json: {m}" for m in erros("catalogo", ler(saida / "catalogo.json"))]
    return problemas


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m catalogo.validar")
    ap.add_argument("--raiz", help="pasta de um repositório de versão (padrão: o núcleo)")
    a = ap.parse_args()
    if a.raiz:
        from catalogo.executar import configurar_raiz
        configurar_raiz(a.raiz)
    pr = validar_tudo()
    for m in pr[:50]:
        print(m)
    print(f"{len(pr)} problema(s)" if pr else "Todos os arquivos JSON são válidos.")
    sys.exit(1 if pr else 0)
