"""Consolida o código de um repositório git num único Markdown, para avaliação.

Uso (dentro da pasta do repositório; funciona no Windows, Linux e macOS):
    python consolidar.py                      # gera codigo_consolidado.md
    python consolidar.py --saida revisao.md --ref v0dta

- Só arquivos versionados (git ls-files): saida/, venv, caches e o próprio
  arquivo de saída ficam de fora automaticamente.
- Ordem estável (alfabética), índice no início, cerca adaptada ao conteúdo
  (um arquivo .md com ``` dentro não quebra o documento).
- Gerados ou volumosos (site/index.html, *.svg) são listados, mas não copiados.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXTENSOES = {".py": "python", ".html": "html", ".md": "markdown", ".json": "json", ".yml": "yaml",
             ".yaml": "yaml", ".mmd": "mermaid", ".txt": "text", ".toml": "toml", ".cfg": "ini"}
NOMES = {".gitignore": "gitignore"}
OMITIR = {"site/index.html"}            # página gerada (dados e diagramas embutidos)
OMITIR_EXT = {".svg", ".png", ".jpg", ".docx", ".pdf", ".jsonl"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, encoding="utf-8").stdout


def cerca(texto: str) -> str:
    n, maior, atual = 3, 0, 0
    for ch in texto:
        atual = atual + 1 if ch == "`" else 0
        maior = max(maior, atual)
    return "`" * max(n, maior + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="codigo_consolidado.md")
    ap.add_argument("--ref", default="HEAD", help="commit ou tag a consolidar (padrão: HEAD)")
    a = ap.parse_args()

    commit = git("rev-parse", "--short", a.ref).strip()
    descr = git("describe", "--tags", "--always", a.ref).strip()
    arquivos = sorted(git("ls-tree", "-r", "--name-only", a.ref).splitlines())
    incluir, omitidos = [], []
    for f in arquivos:
        p = Path(f)
        if f == a.saida:
            continue
        ling = NOMES.get(p.name) or EXTENSOES.get(p.suffix.lower())
        if f in OMITIR or p.suffix.lower() in OMITIR_EXT or ling is None:
            omitidos.append(f)
        else:
            incluir.append((f, ling))

    partes = [f"# Código consolidado — {Path.cwd().name}\n",
              f"Referência: `{descr}` (commit `{commit}`). {len(incluir)} arquivos incluídos, {len(omitidos)} listados sem conteúdo.\n",
              "## Índice\n"]
    partes += [f"{i}. `{f}`" for i, (f, _) in enumerate(incluir, 1)]
    partes.append("\n## Arquivos não copiados (gerados ou binários)\n")
    partes += [f"- `{f}`" for f in omitidos]
    total = 0
    for f, ling in incluir:
        texto = git("show", f"{a.ref}:{f}").rstrip("\n")
        total += len(texto.splitlines())
        c = cerca(texto)
        partes.append(f"\n---\n\n## Arquivo: `{f}`\n\n{c}{ling}\n{texto}\n{c}")
    Path(a.saida).write_text("\n".join(partes) + "\n", encoding="utf-8")
    print(f"{a.saida}: {len(incluir)} arquivos, {total} linhas (ref {descr})")


if __name__ == "__main__":
    main()
