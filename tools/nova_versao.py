"""Monta a pasta de um repositório de versão (reg10k-V0 … reg10k-V4) a partir do núcleo.

Uso:
    python tools/nova_versao.py DESTINO --nome V0 --titulo "uma sala, com gêmeo digital e espelho" \\
        --ambientes sala [--submodulo URL_DO_NUCLEO --tag nucleo-v1.0]

Copia para DESTINO os ambientes pedidos, os roteiros e esperados que usam esses
ambientes, o grupo de exemplo dos alunos e o mapeamento de famílias desses
cenários, e escreve versao.json, README, .gitignore, licenças e a CI.
Com --submodulo, cria também o submódulo git `nucleo/` fixado na tag.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from experimentos.familias import FAMILIAS, PADRAO  # noqa: E402

CI = """name: versao

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  catalogo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Dependências do núcleo
        run: pip install -r nucleo/requirements.txt
      - name: Validação dos JSON da versão
        run: python nucleo/reg10k.py validar
      - name: Regressão por assinatura (se houver dados/assinaturas-{nome}.json)
        run: if [ -f dados/assinaturas-{nome}.json ]; then python nucleo/reg10k.py assinaturas comparar {nome}; fi
      - name: Catálogo e página
        run: python nucleo/reg10k.py catalogo --sementes 30
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pagina-e-catalogo-{nome}
          path: |
            site/index.html
            saida/catalogo.json
"""

README = """# Reg10k — versão {nome}: {titulo}

Repositório de versão do ambiente de simulação Reg10k (PCS5039, EPUSP).
Linha de pesquisa: Laboratório de Digital Twin de Arquitetura de Sistemas de Software (EPUSP) e GLIP USP.

O código (motor, hub, plataforma, oráculo, página) fica no **núcleo**, na subpasta `nucleo/`,
fixado numa tag. Esta pasta guarda só o que é da versão:

| Pasta | Conteúdo |
|---|---|
| `ambiente/` | Planta(s): {ambientes} |
| `cenarios/` | Roteiros e resultados esperados ({n} cenários) |
| `alunos/` | Controladores dos alunos (um pacote por grupo) |
| `experimentos/familias.json` | Famílias do protocolo de experimentos e os cenários de cada uma |
| `dados/` | CSV dos experimentos, manifestos e assinaturas de regressão |
| `site/` | Página gerada |

## Como usar

```
git clone --recurse-submodules <endereço deste repositório>
cd <pasta>
pip install -r nucleo/requirements.txt
python nucleo/reg10k.py catalogo            # catálogo e site/index.html
python nucleo/reg10k.py sim --cenario {exemplo}
python nucleo/reg10k.py experimentos --sementes 30
```

Para trocar a versão do núcleo: `cd nucleo && git fetch --tags && git checkout <tag>`, depois
`cd ..`, `git add nucleo` e um commit. Dados de artigo são gerados só com o núcleo numa tag
(o manifesto registra o commit).

Resultados de simulação, não de medição.

Licenças: código MIT (`LICENSE`); dados e documentos CC BY 4.0 (`LICENSE-dados.md`).
"""

GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\nsaida/\n.venv/\n.DS_Store\n"

LICENCA_DADOS = """# Licença dos dados e documentos

Os arquivos de `cenarios/`, `ambiente/`, `experimentos/`, `dados/` e `docs/` deste repositório
estão licenciados sob a Creative Commons Atribuição 4.0 Internacional (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/deed.pt-br

Atribuição: Reginaldo Arakaki — Laboratório de Digital Twin de Arquitetura de Sistemas de Software
(EPUSP) e GLIP USP. O código está sob a licença MIT (`LICENSE`).
"""


def montar(destino: Path, nome: str, titulo: str, ambientes: list[str], descricao: str = "",
           submodulo: str | None = None, tag: str | None = None) -> dict:
    destino = Path(destino)
    if destino.exists() and any(p.name not in (".git",) for p in destino.iterdir()):
        raise FileExistsError(f"{destino} não está vazio")
    cen = RAIZ / "cenarios"
    (destino / "ambiente").mkdir(parents=True, exist_ok=True)
    for a in ambientes:
        shutil.copy2(cen / f"{a}.json", destino / "ambiente" / f"{a}.json")
    ids = []
    for p in sorted((cen / "roteiros").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("ambiente", "sala") in ambientes:
            ids.append(r["id"])
            for sub in ("roteiros", "esperado"):
                q = cen / sub / p.name
                if q.exists():
                    (destino / "cenarios" / sub).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(q, destino / "cenarios" / sub / p.name)
    shutil.copytree(RAIZ / "alunos" / "grupo_exemplo", destino / "alunos" / "grupo_exemplo",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (destino / "alunos" / "__init__.py").write_text('"""Controladores dos alunos: um pacote por grupo."""\n', encoding="utf-8")
    fam = {f: [c for c in v if c in ids] for f, v in PADRAO.items()}
    (destino / "experimentos").mkdir(exist_ok=True)
    (destino / "experimentos" / "familias.json").write_text(json.dumps(
        {"descricao": {f: FAMILIAS[f]["nome"] for f in fam}, "familias": fam}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destino / "dados").mkdir(exist_ok=True)
    (destino / "dados" / "LEIA-ME.md").write_text(
        "CSV dos experimentos com o manifesto ao lado, e assinaturas de regressão (`assinaturas-<versão>.json`).\n", encoding="utf-8")
    ident = {"nome": nome, "titulo": titulo, "descricao": descricao or titulo, "ambientes": ambientes,
             "nucleo_tag": tag}
    (destino / "versao.json").write_text(json.dumps(ident, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destino / "README.md").write_text(README.format(nome=nome, titulo=titulo, ambientes=", ".join(ambientes),
                                                     n=len(ids), exemplo=ids[0] if ids else "ID"), encoding="utf-8")
    (destino / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    shutil.copy2(RAIZ / "LICENSE", destino / "LICENSE")
    (destino / "LICENSE-dados.md").write_text(LICENCA_DADOS, encoding="utf-8")
    (destino / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (destino / ".github" / "workflows" / "ci.yml").write_text(CI.replace("{nome}", nome), encoding="utf-8")
    if submodulo:
        subprocess.run(["git", "-C", str(destino), "submodule", "add", submodulo, "nucleo"], check=True)
        if tag:
            subprocess.run(["git", "-C", str(destino / "nucleo"), "checkout", "-q", tag], check=True)
    return {"cenarios": ids, "familias": fam}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("destino")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--descricao", default="")
    ap.add_argument("--ambientes", nargs="+", required=True)
    ap.add_argument("--submodulo")
    ap.add_argument("--tag")
    a = ap.parse_args(argv)
    r = montar(Path(a.destino), a.nome, a.titulo, a.ambientes, a.descricao, a.submodulo, a.tag)
    print(f"{a.destino}: {len(r['cenarios'])} cenários; famílias " + ", ".join(f"{f}={len(v)}" for f, v in r["familias"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
