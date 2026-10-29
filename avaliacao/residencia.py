"""Avaliação de uma residência com vários cômodos (plano v1dt §7 e §9).

O oráculo da v0 avalia um cômodo. Para a residência, cada cômodo recebe uma
**vista** do registro: a verdade daquele cômodo, as evidências entregues ao
seu controlador, as decisões, atuações e estados dele, e o que a plataforma
sabe dele. O mesmo oráculo avalia cada vista, e os resultados são somados.

A vista traduz o cruzamento do vão (CRUZOU_PASSAGEM) em entrada no cômodo de
destino e saída do cômodo de origem, para que as métricas da v0 (atraso
percebido, desperdício por saída) valham por cômodo.

OR-01, OR-12, OR-13 e OR-14 são verificadas no registro inteiro.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from avaliacao.oraculo import (
    CLASSES_ESPELHO, FIEL, INVARIANTES, aprendizado_com_aceite, NAO_AFIRMA, PERCEPCAO_ERRO, SINCRONIZACAO, Analise, _assinatura,
)
from sim.modelos import ATUACAO, DECISAO, ESTADO, PERCEPCAO, PLATAFORMA, REDE, SISTEMA, VERDADE

SOMA = ("desperdicio_s", "escuro_com_ocupante_s", "apagamentos_indevidos", "acionamentos", "ocupacao_desconhecida_s",
        "tempo_ocupada_s", "tempo_luz_acesa_s", "comandos_remotos", "comandos_vencidos_executados",
        "efeitos_duplicados_remotos", "divergencia_alem_prazo_s", "gemeo_nao_atual_s", "espelho_fiel_s",
        "erro_de_percepcao_s", "erro_de_sincronizacao_s", "espelho_nao_afirma_s", "luz_com_todos_dormindo_s")
MAXIMO = ("latencia_reacao_ms_p95", "latencia_reacao_ms_max", "atraso_percebido_ms_max", "desperdicio_por_saida_s_max",
          "atualidade_gemeo_ms_p95", "comando_remoto_ms_p95", "reconciliacao_ms_max")
GLOBAL = ("eventos_nao_entregues", "fila_max", "suspeitas_abertas", "suspeitas_confirmadas", "suspeitas_conciliadas")
# Ordem de gravidade para compor a classe da residência a partir dos cômodos
_GRAVIDADE = {PERCEPCAO_ERRO: 3, SINCRONIZACAO: 2, NAO_AFIRMA: 1, FIEL: 0}


# ----------------------------------------------------------------------- vistas
def vista(eventos: list[dict], cid: str) -> list[dict]:
    out = []
    for e in eventos:
        c, tipo = e["camada"], e["tipo"]
        if c == VERDADE:
            if tipo == "OCUPANTES":
                out.append({**e, "presentes": e.get("por_comodo", {}).get(cid, [])})
            elif tipo == "CRUZOU_PASSAGEM":
                if e["para"] == cid:
                    out.append({**e, "tipo": "CRUZOU_PORTA", "sentido": "ENTRADA"})
                elif e["de"] == cid:
                    out.append({**e, "tipo": "CRUZOU_PORTA", "sentido": "SAIDA"})
            elif tipo == "ESPIOU":
                if cid in (e.get("de"), e.get("comodo")):
                    out.append(e)
            elif "comodo" in e and tipo != "FALHA_INJETADA":
                if e["comodo"] == cid:
                    out.append(e)
            else:
                out.append(e)
        elif c == PERCEPCAO:
            if cid in e.get("comodos", [cid]):
                out.append(e)
        elif c in (DECISAO, ATUACAO, ESTADO):
            if e.get("comodo", cid) == cid:
                out.append(e)
        elif c == SISTEMA:
            if e.get("comodo") in (None, cid):
                out.append(e)
        elif c == REDE:
            out.append(e)
        elif c == PLATAFORMA:
            if tipo == "APP_CONSULTA":
                out.append({**e, **(e.get("comodos") or {}).get(cid, {})} if e.get("disponivel") else e)
            elif tipo in ("CONFIG_VERSAO", "APP_PREFERENCIA", "CONFIG_REJEITADA"):
                if (e.get("parametros") or {}).get("comodo") in (None, cid):
                    out.append(e)
            elif "comodos" in e:
                if cid in e["comodos"]:
                    out.append(e)
            elif "comodo" in e:
                if e["comodo"] == cid:
                    out.append(e)
            else:
                out.append(e)
        else:
            out.append(e)
    return out


def _roteiro_do_comodo(roteiro: dict, cid: str) -> dict:
    r = dict(roteiro)
    r["controle"] = {**roteiro.get("controle", {}), **roteiro.get("controle_comodos", {}).get(cid, {})}
    return r


# ------------------------------------------------------------------- agregação
def agregar(metricas: dict[str, dict], duracao_ms: int) -> dict:
    ms = list(metricas.values())
    out: dict = {}
    for k in SOMA:
        vals = [m.get(k) for m in ms if m.get(k) is not None]
        out[k] = round(sum(vals), 1) if vals else None
    for k in MAXIMO:
        vals = [m.get(k) for m in ms if m.get(k) is not None]
        out[k] = max(vals) if vals else None
    for k in GLOBAL:
        out[k] = ms[0].get(k)
    out["alertas"] = sorted({a for m in ms for a in m.get("alertas", [])})
    n = len(ms)
    out["espelho_fiel_pct"] = round(100 * out["espelho_fiel_s"] * 1000 / (duracao_ms * n), 1) if duracao_ms else None
    return out


def compor_segmentos(por_comodo: dict[str, list]) -> list[list]:
    """Classe da residência em cada instante: a mais grave entre os cômodos."""
    pontos = sorted({t for segs in por_comodo.values() for s in segs for t in s[:2]})
    out: list[list] = []
    for a, b in zip(pontos, pontos[1:]):
        classes = []
        for segs in por_comodo.values():
            classes += [c for t0, t1, c in segs if t0 <= a < t1]
        c = max(classes, key=lambda x: _GRAVIDADE[x]) if classes else NAO_AFIRMA
        if out and out[-1][2] == c:
            out[-1][1] = b
        else:
            out.append([a, b, c])
    return out


# ----------------------------------------------------------- invariantes globais
def _seq_continuo(eventos: list[dict]) -> list[str]:
    v = []
    if [e["seq"] for e in eventos] != list(range(1, len(eventos) + 1)):
        v.append("seq não é 1..n contínuo")
    if len({e["id"] for e in eventos}) != len(eventos):
        v.append("ids repetidos")
    return v


def isolamento_e_atuacao(eventos: list[dict], res) -> dict:
    """OR-13 (entrega por cômodo) e OR-14 (atuação no próprio cômodo)."""
    v13: list[str] = []
    fim = next((e for e in eventos if e["camada"] == SISTEMA and e["tipo"] == "FIM"), None)
    entregues = (fim or {}).get("entregas_por_comodo") or {}
    esperado: dict[str, Counter] = {cid: Counter() for cid in res.ids}
    for e in eventos:
        if e["camada"] != PERCEPCAO:
            continue
        cids = e.get("comodos") or []
        for cid in cids:
            if cid in esperado:
                esperado[cid][e["origem"]] += 1
        for ps in res.passagens.values():
            if e.get("origem") == ps.sa and e["tipo"] == "PASSAGEM" and sorted(cids) != sorted(ps.comodos):
                v13.append(f"SA {ps.sa} em t={e['t_ms']} ms entregue a {cids}, deveria ir a {ps.comodos}")
    for cid, rec in entregues.items():
        permitidos = res.permitidos(cid)
        for origem, n in rec.items():
            if origem not in permitidos:
                v13.append(f"{cid} recebeu {n} evidência(s) de {origem}, que não é do cômodo")
            elif origem != "HUB" and n != esperado[cid][origem]:
                v13.append(f"{cid}: {n} entregas de {origem}, {esperado[cid][origem]} registradas")
    v14: list[str] = []
    intencoes = {e["chave"]: e for e in eventos if e["camada"] == DECISAO and e["tipo"] == "INTENCAO"}
    for e in eventos:
        if e["camada"] == ATUACAO and e["tipo"] == "COMUTACAO":
            i = intencoes.get(e["chave"])
            if i is None:
                continue
            esperado_atu = res.comodos[i.get("comodo", res.ids[0])].atuador
            if e.get("origem") != esperado_atu:
                v14.append(f"intenção {e['chave']} de {i.get('comodo')} comutou {e.get('origem')} em t={e['t_ms']} ms")
    tem_interna = any(ps.tipo == "INTERNA" for ps in res.passagens.values())
    return {"OR-13": {"ok": not v13, "violacoes": v13[:5], **({} if tem_interna else {"aplica": False})},
            "OR-14": {"ok": not v14, "violacoes": v14[:5]}}


def presenca_incompativel(eventos: list[dict], verifica_ms: int = 300_000) -> dict:
    """OR-15 (nucleo-v1.3; RN03, RN17, RF-OPR-06).

    (a) nenhum evento rotula invasão; (b) todo evento de fronteira tem antes uma
    suspeita CONFIRMADA, verificada pelo menos `verifica_ms` depois de aberta;
    (c) suspeita conciliada nunca é confirmada nem enviada.
    """
    v: list[str] = []
    for e in eventos:
        textos = [e["tipo"]] + [x for x in e.values() if isinstance(x, str)]
        if any("INVAS" in x.upper() for x in textos):
            v.append(f"{e['camada']}/{e['tipo']} em t={e['t_ms']} ms rotula invasão")
    estados: dict[str, dict[str, dict]] = {}
    for e in eventos:
        if e["camada"] == SISTEMA and e["tipo"] == "SUSPEITA_PRESENCA":
            estados.setdefault(e["suspeita"], {})[e["estado"]] = e
    for sid, st in estados.items():
        if "CONCILIADA" in st and ("CONFIRMADA" in st):
            v.append(f"{sid} foi conciliada e também confirmada")
        c = st.get("CONFIRMADA")
        if c and c["t_ms"] - c["desde_ms"] < verifica_ms:
            v.append(f"{sid} confirmada {c['t_ms'] - c['desde_ms']} ms depois de aberta, antes da verificação ({verifica_ms} ms)")
    for e in eventos:
        if e["camada"] == PLATAFORMA and e["tipo"] == "EVENTO_FRONTEIRA":
            c = estados.get(e.get("suspeita"), {}).get("CONFIRMADA")
            if c is None or c["t_ms"] > e["t_ms"]:
                v.append(f"evento de fronteira em t={e['t_ms']} ms sem suspeita confirmada antes")
    return {"OR-15": {"ok": not v, "violacoes": v[:5], **({} if estados else {"aplica": False})}}


# --------------------------------------------------------------------- avaliação
def avaliar_residencia(eventos: list[dict], roteiro: dict, res, esperado: Optional[dict],
                       par: Optional[list[dict]]) -> dict:
    from avaliacao.espelho import amostras_residencia
    analises = {cid: Analise(vista(eventos, cid), _roteiro_do_comodo(roteiro, cid), res.sala_da_vista(cid),
                             None, parcial=True) for cid in res.ids}
    metricas_c = {cid: an.metricas() for cid, an in analises.items()}
    m = agregar(metricas_c, roteiro["duracao_ms"])

    inv_c = {cid: an.invariantes() for cid, an in analises.items()}
    inv: dict = {}
    for k in INVARIANTES:
        if k in ("OR-01", "OR-12", "OR-13", "OR-14", "OR-15", "OR-17"):
            continue
        viol = [f"[{cid}] {x}" for cid in res.ids for x in inv_c[cid][k]["violacoes"]]
        inv[k] = {"ok": all(inv_c[cid][k]["ok"] for cid in res.ids), "violacoes": viol[:5]}
    v01 = _seq_continuo(eventos)
    inv["OR-01"] = {"ok": not v01, "violacoes": v01}
    if par is None:
        inv["OR-12"] = {"ok": True, "violacoes": [], "aplica": False}
    else:
        a, b = _assinatura(eventos), _assinatura(par)
        inv["OR-12"] = {"ok": a == b, "violacoes": [] if a == b else ["decisões locais diferem da execução sem falha de rede"]}
    inv.update(isolamento_e_atuacao(eventos, res))
    inv.update(presenca_incompativel(eventos))
    inv.update(aprendizado_com_aceite(eventos, [o["id"] for o in res.ocupantes]))
    inv = {k: inv[k] for k in INVARIANTES}
    inv_ok = all(v["ok"] for v in inv.values())

    resultados = {}
    primeiro = res.ids[0]
    for a in (esperado or {}).get("assercoes", []):
        e = a["entao"]
        if e["tipo"] == "invariantes":
            falhas = [k for k, v in inv.items() if not v["ok"]]
            ok, detalhe = not falhas, "todas respeitadas" if not falhas else f"violadas: {falhas}"
        elif e["tipo"] == "metrica" and not e.get("comodo"):
            ok, detalhe = analises[primeiro].verificar(a, m)
            detalhe = f"residência: {detalhe}"
        else:
            cid = e.get("comodo", primeiro)
            ok, detalhe = analises[cid].verificar(a, metricas_c[cid])
            detalhe = f"{cid}: {detalhe}"
        resultados[a["id"]] = {"ok": ok, "nivel": a.get("nivel", "REQUISITO"), "detalhe": detalhe}
    req = [r for r in resultados.values() if r["nivel"] == "REQUISITO"]
    car = [r for r in resultados.values() if r["nivel"] == "CARACTERIZACAO"]

    seg_c = {cid: {"R": an.segmentos_espelho("R"), "L": an.segmentos_espelho("L")} for cid, an in analises.items()}
    espelho = {
        "segmentos": {"R": compor_segmentos({c: s["R"] for c, s in seg_c.items()}),
                      "L": compor_segmentos({c: s["L"] for c, s in seg_c.items()}),
                      "por_comodo": seg_c},
        "amostras": amostras_residencia(analises, res, eventos, roteiro),
    }
    return {
        "metricas": m,
        "invariantes": inv,
        "assercoes": resultados,
        "requisitos_ok": all(r["ok"] for r in req) and inv_ok,
        "requisitos": {"total": len(req), "ok": sum(r["ok"] for r in req)},
        "caracterizacao": {"total": len(car), "igual_referencia": sum(r["ok"] for r in car)},
        "aprovado": all(r["ok"] for r in resultados.values()) and inv_ok,
        "espelho": espelho,
        "comodos": {cid: {"metricas": metricas_c[cid]} for cid in res.ids},
    }
