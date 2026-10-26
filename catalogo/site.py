"""Gera site/index.html: página única, offline, com os dados embutidos (plano §11 e v0dt §10)."""
from __future__ import annotations

import base64
import datetime as dt
import json
from pathlib import Path

from avaliacao.espelho import NOMES_ROTULO, svg_amostra

RAIZ = Path(__file__).resolve().parent.parent
MODELO = Path(__file__).resolve().parent / "modelo.json"
TEMPLATE = Path(__file__).resolve().parent / "template.html"
UML = RAIZ / "docs" / "uml"
DESTINO = RAIZ / "site" / "index.html"

# Campos que não precisam ir para a página
_OMITIR = {"id", "relogio_hub_ms"}


def _compactar_eventos(eventos: list[dict]) -> tuple[list[dict], dict]:
    """Remove snapshots periódicos e separa as posições (iguais para todos os controladores)."""
    saida, pos = [], {"t": [], "o": {}}
    for e in eventos:
        if e["camada"] == "VERDADE" and e["tipo"] == "POSICOES":
            pos["t"].append(e["t_ms"])
            for oid, v in e["ocupantes"].items():
                pos["o"].setdefault(oid, []).append(v)
            continue
        if e["camada"] == "ESTADO" and not e.get("mudanca"):
            continue
        if e["camada"] == "PERCEPCAO" and e["tipo"] == "HEARTBEAT":
            # mantém, mas enxuto
            saida.append({"t_ms": e["t_ms"], "seq": e["seq"], "camada": "PERCEPCAO", "tipo": "HEARTBEAT",
                          "origem": e.get("origem"), "bateria": e.get("bateria"), "alto": e.get("alto")})
            continue
        c = {k: v for k, v in e.items() if k not in _OMITIR}
        if c.get("relogio_confiavel") is True:
            c.pop("relogio_confiavel")
        c.pop("mudanca", None)
        saida.append(c)
    return saida, pos


def _diagramas(modelo: dict) -> list[dict]:
    out = []
    for d in modelo["diagramas"]:
        svg = UML / f"{d['id']}.svg"
        src = ""
        if svg.exists():
            src = "data:image/svg+xml;base64," + base64.b64encode(svg.read_bytes()).decode("ascii")
        out.append({**d, "src": src, "fonte": f"docs/uml/{d['id']}.mmd"})
    return out


def _titulo(e: dict, a: dict) -> str:
    t = a["t_ms"] / 1000
    return f"{e['cenario']} — {NOMES_ROTULO[a['rotulo']]} (t = {int(t // 60)}:{t % 60:04.1f}) · {e['controlador']}"


def montar_dados(cat: dict) -> dict:
    modelo = json.loads(MODELO.read_text(encoding="utf-8"))
    roteiros = cat["_roteiros"]
    execucoes, posicoes = {}, {}
    for e in cat["execucoes"]:
        chave = f"{e['cenario']}|{e['controlador']}"
        evs, pos = _compactar_eventos(cat["_eventos"][(e["cenario"], e["controlador"])])
        posicoes.setdefault(e["cenario"], pos)
        execucoes[chave] = {
            **{k: e.get(k) for k in ("cenario", "controlador", "semente", "modo", "modo_rede", "execucao_pareada",
                                     "hash_eventos", "n_eventos",
                                 "metricas", "invariantes", "assercoes", "requisitos", "caracterizacao",
                                 "requisitos_ok", "aprovado")},
            "determinismo_ok": e.get("determinismo_ok"),
            # v0dta: segmentos de fidelidade, amostras e os mesmos SVG gravados em saida/.../espelho/
            "espelho": {**e["espelho"], "svg": {v: [svg_amostra(cat["sala"], a, _titulo(e, a), v)
                                                    for a in e["espelho"]["amostras"]] for v in ("R", "L")}},
            "distribuicao": e.get("distribuicao"),
            "eventos": evs,
        }
    cenarios = []
    for c in cat["cenarios"]:
        r = roteiros[c["id"]]
        cenarios.append({**c, "acoes": r.get("acoes", []), "falhas": r.get("falhas", []),
                         "estado_inicial": r.get("estado_inicial", {})})
    return {
        "meta": {
            "gerado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "versao": cat["versao"],
            "incremento": cat["incremento"],
            "controladores": cat["controladores"],
            "problemas": cat["problemas"],
        },
        "sala": cat["sala"],
        "modelo": {**modelo, "diagramas": _diagramas(modelo)},
        "cenarios": cenarios,
        "execucoes": execucoes,
        "posicoes": posicoes,
    }


def gerar_site(cat: dict, destino: Path = DESTINO) -> Path:
    dados = montar_dados(cat)
    js = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DADOS__*/null", js)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
