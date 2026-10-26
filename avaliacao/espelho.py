"""Cômodo espelho e amostras (plano v0dta §3 e §4).

O espelho é a sala desenhada só com o que o gêmeo sabe. Do lado real entram
a verdade (ocupantes com posição, lâmpada física); do lado do espelho, apenas
o que chegou ao DTReg10k-R (ou ao DTReg10k-L, na visão L). O espelho não tem
ocupantes: tem uma "mancha de presença", sem identidade, posição ou contagem
(RN09, RN34).

As amostras são retratos lado a lado em três instantes (início, meio, fim),
com os dados de cada lado. Saem em JSON e em SVG.
"""
from __future__ import annotations

from typing import Optional

from sim.modelos import ATUAL, LUZ_ACESA, PERCEPCAO, PLATAFORMA, VERDADE

ROTULOS = ("inicio", "meio", "fim")
NOMES_ROTULO = {"inicio": "Início", "meio": "Meio", "fim": "Fim"}
JANELA_SINAL_MS = 1500


def instantes(roteiro: dict) -> list[int]:
    if roteiro.get("amostras_ms"):
        return [int(t) for t in roteiro["amostras_ms"]][:3]
    dur = roteiro["duracao_ms"]
    acoes = sorted(a["t_ms"] for a in roteiro.get("acoes", []))
    ini = min((acoes[0] if acoes else 0) + 5000, dur // 4)
    return [ini, dur // 2, max(0, dur - 1000)]


def _ultimo(eventos: list[dict], t: int, filtro) -> Optional[dict]:
    achado = None
    for e in eventos:
        if e["t_ms"] > t:
            break
        if filtro(e):
            achado = e
    return achado


def _sinais(eventos: list[dict], t: int, camada: str, tipo_campo: str) -> dict:
    """SA recente e SP ativo segundo as evidências de uma camada."""
    sa = sp = False
    for e in eventos:
        if e["t_ms"] > t:
            break
        if e["camada"] != camada:
            continue
        tipo = e.get(tipo_campo)
        if tipo == "PASSAGEM" and t - e["t_ms"] <= JANELA_SINAL_MS:
            sa = True
        elif tipo == "MOVIMENTO":
            sp = True
        elif tipo == "FIM_MOVIMENTO":
            sp = False
    return {"sa_recente": sa, "sp_ativo": sp}


def amostras(an) -> list[dict]:
    ev = an.ev
    saida = []
    for rot, t in zip(ROTULOS, instantes(an.roteiro)):
        pos = _ultimo(ev, t, lambda e: e["camada"] == VERDADE and e["tipo"] == "POSICOES")
        presentes = _ultimo(ev, t, lambda e: e["camada"] == VERDADE and e["tipo"] == "OCUPANTES")
        est = _ultimo(ev, t, lambda e: e["camada"] == "ESTADO")
        res_l = _ultimo(ev, t, lambda e: e["camada"] == "ATUACAO" and e["tipo"] == "RESULTADO")
        rem = _ultimo(ev, t, lambda e: e["camada"] == PLATAFORMA and e["tipo"] == "ESTADO_REMOTO")
        res_r = _ultimo(ev, t, lambda e: e["camada"] == PLATAFORMA and e["tipo"] == "RESULTADO_RECEBIDO")
        cfg = _ultimo(ev, t, lambda e: e["camada"] == PLATAFORMA and e["tipo"] == "CONFIG_VERSAO")
        app = _ultimo(ev, t, lambda e: e["camada"] == PLATAFORMA and e["tipo"] == "APP_RESULTADO")
        hub = an.hub_ligado.em(t)
        saida.append({
            "rotulo": rot, "t_ms": t,
            "real": {
                "presentes": (presentes or {}).get("presentes", []),
                "luz_fisica": bool(an.luz.em(t)),
                "posicoes": (pos or {}).get("ocupantes", {}),
            },
            "L": {
                "hub_ligado": hub,
                "ocupacao": est["ocupacao"] if est and hub else None,
                "luz": est["luz"] if est and hub else None,
                "precedencia": est["precedencia"] if est and hub else None,
                "alertas": est["alertas"] if est and hub else [],
                "nivel_ultima_atuacao": (res_l or {}).get("nivel"),
                **_sinais(ev, t, PERCEPCAO, "tipo"),
                "classe": an.classe_espelho(t, "L"),
            },
            "R": {
                "ocupacao": (rem or {}).get("ocupacao"),
                "luz": (rem or {}).get("luz"),
                "atualidade": (rem or {}).get("atualidade", "SEM_EVIDENCIA"),
                "conexao": (rem or {}).get("conexao", "DESCONECTADO"),
                "idade_ms": None if not rem or rem.get("recepcao_ms") is None else t - rem["recepcao_ms"],
                "nivel_ultima_atuacao": (res_r or {}).get("nivel"),
                "config": None if not cfg else {"versao": cfg["versao"], "estado": cfg["estado"]},
                "ultimo_app": None if not app else {"chave": app["chave"], "nivel": app["nivel"], "final": app["final"]},
                **_sinais(ev, t, PLATAFORMA, "evidencia"),
                "classe": an.classe_espelho(t, "R"),
            },
        })
    return saida


# ---------------------------------------------------------------------- SVG
_COR_CLASSE = {"FIEL": "#1a7f4b", "PERCEPCAO": "#7c3aed", "SINCRONIZACAO": "#c2410c", "NAO_AFIRMA": "#64748b"}
_TXT_CLASSE = {"FIEL": "espelho fiel", "PERCEPCAO": "erro de percepção (sensores/controlador)",
               "SINCRONIZACAO": "erro de sincronização (canal/plataforma)", "NAO_AFIRMA": "espelho não afirma (desatualizado)"}


def _esc(s) -> str:
    return str(s if s is not None else "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _planta(sala: dict, x0: float, y0: float, px: float, acesa: bool, hachura: bool = False) -> list[str]:
    W, H = sala["largura_m"], sala["profundidade_m"]
    X = lambda x: x0 + x * px
    Y = lambda y: y0 + (H - y) * px
    porta, z, lamp = sala["porta"], sala["zonas_cegas"][0], sala["lampada"]
    out = [f'<rect x="{X(0)}" y="{Y(H)}" width="{W * px}" height="{H * px}" fill="{"#fdf6dc" if acesa else "#2c3240"}"/>']
    if acesa:
        out.append(f'<circle cx="{X(lamp["x"])}" cy="{Y(lamp["y"])}" r="{1.9 * px}" fill="#ffe680" opacity=".45"/>')
    out.append(f'<rect x="{X(z["x0"])}" y="{Y(z["y1"])}" width="{(z["x1"] - z["x0"]) * px}" height="{(z["y1"] - z["y0"]) * px}" '
               f'fill="url(#hz)" opacity=".5"/>')
    out.append(f'<path d="M{X(porta["x_inicio"])},{Y(0)} L{X(0)},{Y(0)} L{X(0)},{Y(H)} L{X(W)},{Y(H)} L{X(W)},{Y(0)} '
               f'L{X(porta["x_fim"])},{Y(0)}" stroke="#334155" stroke-width="5" fill="none"/>')
    out.append(f'<circle cx="{X(lamp["x"])}" cy="{Y(lamp["y"])}" r="9" fill="{"#facc15" if acesa else "#475569"}" stroke="#0f172a" stroke-width="1.5"/>')
    if hachura:
        out.append(f'<rect x="{X(0)}" y="{Y(H)}" width="{W * px}" height="{H * px}" fill="url(#hd)"/>')
    return out


def svg_amostra(sala: dict, a: dict, titulo: str, visao: str = "R") -> str:
    px, W, H = 56, sala["largura_m"], sala["profundidade_m"]
    larg = W * px
    xr, xe, y0 = 20, 20 + larg + 60, 52
    X = lambda x0, x: x0 + x * px
    Y = lambda y: y0 + (H - y) * px
    real, m = a["real"], a[visao]
    tipos = {x["id"]: x["tipo"] for x in sala["ocupantes"]}
    nomes = {x["id"]: x.get("nome", x["id"]) for x in sala["ocupantes"]}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * larg + 100}" height="{y0 + H * px + 150}" '
         f'font-family="Arial, Helvetica, sans-serif" font-size="12">',
         '<defs><pattern id="hz" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<line x1="0" y1="0" x2="0" y2="6" stroke="#94a3b8" stroke-width="2"/></pattern>'
         '<pattern id="hd" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<line x1="0" y1="0" x2="0" y2="8" stroke="#e2e8f0" stroke-width="2.5" opacity=".7"/></pattern></defs>',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         f'<text x="20" y="20" font-size="14" font-weight="700">{_esc(titulo)}</text>',
         f'<text x="{xr}" y="{y0 - 10}" font-weight="700">Sala real (verdade)</text>',
         f'<text x="{xe}" y="{y0 - 10}" font-weight="700">Cômodo espelho — {"plataforma (DTReg10k-R)" if visao == "R" else "hub (DTReg10k-L)"}</text>']
    # lado real
    o += _planta(sala, xr, y0, px, real["luz_fisica"])
    for oid, p in (real.get("posicoes") or {}).items():
        if not p:
            continue
        cao = tipos.get(oid) == "CACHORRO"
        o.append(f'<circle cx="{X(xr, p[0])}" cy="{Y(p[1])}" r="{9 if cao else 11}" fill="{"#9a5b13" if cao else "#2563eb"}" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{X(xr, p[0])}" y="{Y(p[1]) + 4}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">{"R" if cao else "M"}</text>')
    # lado espelho
    if visao == "R":
        afirma = m.get("atualidade") == ATUAL
    else:
        afirma = bool(m.get("hub_ligado"))
    acesa_e = (m.get("luz") in LUZ_ACESA)
    o += _planta(sala, xe, y0, px, acesa_e, hachura=not afirma)
    ocup = m.get("ocupacao")
    cx, cy = X(xe, W / 2), Y(H / 2 - 0.7)
    if ocup == "OCUPADA":
        o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{1.7 * px}" ry="{1.2 * px}" fill="#22a06b" opacity=".38"/>'
                 f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-weight="700" fill="#065f46">presença</text>')
    elif ocup == "DESCONHECIDA":
        o.append(f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" font-size="34" font-weight="700" fill="#f5a524">?</text>')
    porta = sala["porta"]
    if m.get("sa_recente"):
        o.append(f'<line x1="{X(xe, porta["x_inicio"])}" y1="{Y(0)}" x2="{X(xe, porta["x_fim"])}" y2="{Y(0)}" stroke="#ef4444" stroke-width="6"/>')
    sp = sala["dispositivos"]["SP-01"]
    o.append(f'<circle cx="{X(xe, sp["x"]) - 9}" cy="{Y(sp["y"]) + 9}" r="7" fill="{"#06b6d4" if m.get("sp_ativo") else "#0e7490"}" '
             f'stroke="{"#fff" if m.get("sp_ativo") else "none"}" stroke-width="2"/>')
    # dados
    yt = y0 + H * px + 22
    linhas_r = [f"Na sala: {', '.join(nomes.get(i, i) for i in real['presentes']) or 'ninguém'}", f"Lâmpada: {'acesa' if real['luz_fisica'] else 'apagada'}"]
    if visao == "R":
        idade = m.get("idade_ms")
        linhas_e = [f"Ocupação: {_esc(ocup)} · luz: {_esc(m.get('luz'))}",
                    f"{_esc(m.get('atualidade'))} · {_esc(m.get('conexao'))}" + (f" · idade {idade / 1000:.0f} s" if idade is not None else ""),
                    f"Última atuação recebida: {_esc(m.get('nivel_ultima_atuacao'))}"]
        if m.get("config"):
            linhas_e.append(f"Configuração v{m['config']['versao']}: {m['config']['estado']}")
        if m.get("ultimo_app"):
            linhas_e.append(f"App: {m['ultimo_app']['chave']} → {m['ultimo_app']['nivel']}")
    else:
        linhas_e = [f"Ocupação: {_esc(ocup)} · luz: {_esc(m.get('luz'))}",
                    "hub ligado" if m.get("hub_ligado") else "hub desligado",
                    f"Última atuação: {_esc(m.get('nivel_ultima_atuacao'))}"]
    for i, l in enumerate(linhas_r):
        o.append(f'<text x="{xr}" y="{yt + 16 * i}">{_esc(l)}</text>')
    for i, l in enumerate(linhas_e):
        o.append(f'<text x="{xe}" y="{yt + 16 * i}">{_esc(l)}</text>')
    c = m["classe"]
    yb = yt + 16 * max(len(linhas_r), len(linhas_e)) + 10
    o.append(f'<rect x="{xr}" y="{yb}" width="{2 * larg + 60}" height="24" rx="5" fill="{_COR_CLASSE[c]}"/>'
             f'<text x="{xr + 10}" y="{yb + 16}" fill="#fff" font-weight="700">{_esc(_TXT_CLASSE[c])}</text>')
    o.append("</svg>")
    return "\n".join(o)


def svg(sala: dict, a: dict, titulo: str, visao: str = "R") -> str:
    """SVG de uma amostra: sala (v0) ou residência (v1dt)."""
    return svg_amostra_residencia(sala, a, titulo, visao) if "comodos" in a else svg_amostra(sala, a, titulo, visao)


def salvar_amostras(pasta, sala: dict, roteiro: dict, controlador: str, lista: list[dict]) -> None:
    import json
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "amostras.json").write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    for a in lista:
        t = a["t_ms"] / 1000
        titulo = f"{roteiro['id']} — {NOMES_ROTULO[a['rotulo']]} (t = {int(t // 60)}:{t % 60:04.1f}) · {controlador}"
        (pasta / f"{a['rotulo']}.svg").write_text(svg(sala, a, titulo), encoding="utf-8")


# =============================================================== residência (v1dt)
_GRAV = {"PERCEPCAO": 3, "SINCRONIZACAO": 2, "NAO_AFIRMA": 1, "FIEL": 0}


def amostras_residencia(analises: dict, res, eventos: list[dict], roteiro: dict) -> list[dict]:
    """Amostras da residência: o lado real inteiro e, por cômodo, o que o hub e a plataforma sabem."""
    por = {cid: amostras(an) for cid, an in analises.items()}
    saida = []
    for i, (rot, t) in enumerate(zip(ROTULOS, instantes(roteiro))):
        ocup = _ultimo(eventos, t, lambda e: e["camada"] == VERDADE and e["tipo"] == "OCUPANTES")
        pos = _ultimo(eventos, t, lambda e: e["camada"] == VERDADE and e["tipo"] == "POSICOES")
        comodos = {cid: {"L": por[cid][i]["L"], "R": por[cid][i]["R"]} for cid in res.ids}
        saida.append({
            "rotulo": rot, "t_ms": t,
            "real": {"presentes": (ocup or {}).get("presentes", []),
                     "por_comodo": (ocup or {}).get("por_comodo", {}),
                     "luz_fisica": {cid: por[cid][i]["real"]["luz_fisica"] for cid in res.ids},
                     "posicoes": (pos or {}).get("ocupantes", {})},
            "comodos": comodos,
            "L": {"classe": max((c["L"]["classe"] for c in comodos.values()), key=_GRAV.get)},
            "R": {"classe": max((c["R"]["classe"] for c in comodos.values()), key=_GRAV.get)},
        })
    return saida


def svg_amostra_residencia(cfg: dict, a: dict, titulo: str, visao: str = "R") -> str:
    """Retrato lado a lado da residência inteira: real × espelho, cômodo a cômodo."""
    from sim.residencia import Residencia
    res = Residencia(cfg)
    xmax = max(c.x0 + c.largura for c in res.comodos.values())
    ymax = max(c.y0 + c.profundidade for c in res.comodos.values())
    px = 44
    larg, alt = xmax * px, ymax * px
    xr, xe, y0 = 20, 20 + larg + 50, 52
    X = lambda x0, x: x0 + x * px
    Y = lambda y: y0 + (ymax - y) * px
    tipos = {x["id"]: x["tipo"] for x in res.ocupantes}
    nomes = {x["id"]: x.get("nome", x["id"]) for x in res.ocupantes}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * larg + 90}" height="{y0 + alt + 60 + 16 * (len(res.ids) + 2)}" '
         f'font-family="Arial, Helvetica, sans-serif" font-size="12">',
         '<defs><pattern id="hz" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<line x1="0" y1="0" x2="0" y2="6" stroke="#94a3b8" stroke-width="2"/></pattern>'
         '<pattern id="hd" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<line x1="0" y1="0" x2="0" y2="8" stroke="#e2e8f0" stroke-width="2.5" opacity=".7"/></pattern></defs>',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         f'<text x="20" y="20" font-size="14" font-weight="700">{_esc(titulo)}</text>',
         f'<text x="{xr}" y="{y0 - 10}" font-weight="700">Casa real (verdade)</text>',
         f'<text x="{xe}" y="{y0 - 10}" font-weight="700">Espelho — {"plataforma (DTReg10k-R)" if visao == "R" else "hub (DTReg10k-L)"}</text>']

    def comodo(x0, c, acesa, hachura=False):
        out = [f'<rect x="{X(x0, c.x0)}" y="{Y(c.y0 + c.profundidade)}" width="{c.largura * px}" height="{c.profundidade * px}" '
               f'fill="{"#fdf6dc" if acesa else "#2c3240"}"/>']
        for z in c.zonas_cegas:
            out.append(f'<rect x="{X(x0, z["x0"])}" y="{Y(z["y1"])}" width="{(z["x1"] - z["x0"]) * px}" '
                       f'height="{(z["y1"] - z["y0"]) * px}" fill="url(#hz)" opacity=".5"/>')
        lx, ly = c.lampada_pos
        out.append(f'<circle cx="{X(x0, lx)}" cy="{Y(ly)}" r="8" fill="{"#facc15" if acesa else "#475569"}" stroke="#0f172a"/>')
        out.append(f'<rect x="{X(x0, c.x0)}" y="{Y(c.y0 + c.profundidade)}" width="{c.largura * px}" '
                   f'height="{c.profundidade * px}" fill="{"url(#hd)" if hachura else "none"}" stroke="#334155" stroke-width="4"/>')
        out.append(f'<text x="{X(x0, c.x0) + 6}" y="{Y(c.y0 + c.profundidade) + 15}" font-weight="700" '
                   f'fill="{"#334155" if acesa else "#cbd5e1"}">{_esc(c.nome)}</text>')
        return out

    def passagens(x0):
        out = []
        for ps in res.passagens.values():
            p = ps.cfg
            if "x_inicio" in p:
                out.append(f'<line x1="{X(x0, p["x_inicio"])}" y1="{Y(p["y"])}" x2="{X(x0, p["x_fim"])}" y2="{Y(p["y"])}" '
                           f'stroke="#ffffff" stroke-width="6"/>')
            elif "y_inicio" in p:
                out.append(f'<line x1="{X(x0, p["x"])}" y1="{Y(p["y_inicio"])}" x2="{X(x0, p["x"])}" y2="{Y(p["y_fim"])}" '
                           f'stroke="#ffffff" stroke-width="6"/>')
        return out

    real = a["real"]
    for c in res.comodos.values():
        o += comodo(xr, c, real["luz_fisica"].get(c.id, False))
    o += passagens(xr)
    for oid, p in (real.get("posicoes") or {}).items():
        if p:
            cao = tipos.get(oid) == "CACHORRO"
            o.append(f'<circle cx="{X(xr, p[0])}" cy="{Y(p[1])}" r="{8 if cao else 10}" fill="{"#9a5b13" if cao else "#2563eb"}" '
                     f'stroke="#fff" stroke-width="2"/><text x="{X(xr, p[0])}" y="{Y(p[1]) + 4}" text-anchor="middle" '
                     f'font-size="9" font-weight="700" fill="#fff">{"R" if cao else "M"}</text>')
    for c in res.comodos.values():
        m = a["comodos"][c.id][visao]
        afirma = m.get("atualidade") == ATUAL if visao == "R" else bool(m.get("hub_ligado"))
        o += comodo(xe, c, m.get("luz") in LUZ_ACESA, hachura=not afirma)
        cx, cy = X(xe, c.x0 + c.largura / 2), Y(c.y0 + c.profundidade / 2 - 0.6)
        if m.get("ocupacao") == "OCUPADA":
            o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{min(1.4, c.largura / 3) * px}" ry="{0.9 * px}" fill="#22a06b" opacity=".38"/>'
                     f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-weight="700" fill="#065f46">presença</text>')
        elif m.get("ocupacao") == "DESCONHECIDA":
            o.append(f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" font-size="28" font-weight="700" fill="#f5a524">?</text>')
    o += passagens(xe)
    yt = y0 + alt + 22
    linhas_r = [f"{c.nome}: {', '.join(nomes.get(i, i) for i in real['por_comodo'].get(c.id, [])) or 'vazio'} · "
                f"lâmpada {'acesa' if real['luz_fisica'].get(c.id) else 'apagada'}" for c in res.comodos.values()]
    linhas_e = []
    for c in res.comodos.values():
        m = a["comodos"][c.id][visao]
        extra = ""
        if visao == "R":
            idade = m.get("idade_ms")
            extra = f" · {m.get('atualidade')}" + (f" · {idade / 1000:.0f} s" if idade is not None else "")
        linhas_e.append(f"{c.nome}: {m.get('ocupacao') or '—'} · {m.get('luz') or '—'}{extra}")
    for i, l in enumerate(linhas_r):
        o.append(f'<text x="{xr}" y="{yt + 16 * i}">{_esc(l)}</text>')
    for i, l in enumerate(linhas_e):
        o.append(f'<text x="{xe}" y="{yt + 16 * i}">{_esc(l)}</text>')
    cl = a[visao]["classe"]
    yb = yt + 16 * len(res.ids) + 6
    o.append(f'<rect x="{xr}" y="{yb}" width="{2 * larg + 50}" height="24" rx="5" fill="{_COR_CLASSE[cl]}"/>'
             f'<text x="{xr + 10}" y="{yb + 16}" fill="#fff" font-weight="700">{_esc(_TXT_CLASSE[cl])} '
             f'(a mais grave entre os cômodos)</text>')
    o.append("</svg>")
    return "\n".join(o)
