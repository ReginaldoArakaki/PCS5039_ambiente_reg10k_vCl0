"""Oráculo: métricas, invariantes e asserções (plano §10).

O oráculo é o único componente que lê a camada VERDADE junto com as demais.
Ele compara o que aconteceu (verdade) com o que o controlador decidiu e com o
que a lâmpada de fato fez.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from typing import Any, Optional

from sim.modelos import (
    ACENDER, APAGADA_MANUAL, APAGAR, ATUACAO, AUTOMATICA, DECISAO, DESCONHECIDA,
    EFEITO_OBSERVADO, ESTADO, EXECUCAO_RELATADA, DESCONHECIDO, PERCEPCAO, SISTEMA,
    SUBSTITUIDA, VAZIA, VERDADE,
)

NIVEIS_VALIDOS = {EFEITO_OBSERVADO, EXECUCAO_RELATADA, DESCONHECIDO, SUBSTITUIDA}
TIPOS_DETECCAO = {"PASSAGEM", "MOVIMENTO", "FIM_MOVIMENTO"}


# --------------------------------------------------------------------- séries
class Serie:
    """Série em degraus: valor vale a partir de t até a próxima mudança."""

    def __init__(self, inicial: Any):
        self.ts: list[int] = [0]
        self.vs: list[Any] = [inicial]

    def mudar(self, t: int, v: Any) -> None:
        if t == self.ts[-1]:
            self.vs[-1] = v
        elif v != self.vs[-1]:
            self.ts.append(t)
            self.vs.append(v)

    def em(self, t: int) -> Any:
        return self.vs[bisect_right(self.ts, t) - 1]

    def intervalos(self, fim: int):
        for i, (t, v) in enumerate(zip(self.ts, self.vs)):
            t1 = self.ts[i + 1] if i + 1 < len(self.ts) else fim
            if t1 > t:
                yield t, min(t1, fim), v


def _p95(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


def _cruzamento(series: list[Serie], fim: int, pred) -> float:
    """Soma o tempo em que pred(valores das séries) é verdadeiro."""
    pontos = sorted({t for s in series for t in s.ts if t < fim} | {fim})
    total = 0
    for a, b in zip(pontos, pontos[1:]):
        if pred(*[s.em(a) for s in series]):
            total += b - a
    return total


# -------------------------------------------------------------------- análise
class Analise:
    def __init__(self, eventos: list[dict], roteiro: dict, sala: dict):
        self.ev = eventos
        self.roteiro = roteiro
        self.sala = sala
        self.fim = roteiro["duracao_ms"]
        cfg = {**sala.get("controle", {}), **roteiro.get("controle", {})}
        self.t_apagamento = cfg.get("t_apagamento_ms", 60_000)

        self.ocupada = Serie(False)       # verdade: há ocupante na sala?
        self.luz = Serie(False)           # verdade: lâmpada emitindo luz?
        self.luz_estado = Serie("APAGADA")  # inferido: estado da luz no controlador
        self.ocupacao_inf = Serie(DESCONHECIDA)
        self.precedencia = Serie(AUTOMATICA)
        self.intencoes: list[dict] = []
        self.resultados: list[dict] = []
        self.comutacoes: list[dict] = []
        self.alertas: list[dict] = []
        self.sistema: list[dict] = []
        self.percepcao: list[dict] = []
        self.cruzamentos: list[dict] = []
        self.por_id = {e["id"]: e for e in eventos}

        for e in eventos:
            c, t = e["camada"], e["t_ms"]
            if c == VERDADE:
                if e["tipo"] == "OCUPANTES":
                    self.ocupada.mudar(t, bool(e["presentes"]))
                elif e["tipo"] == "LUZ_FISICA":
                    self.luz.mudar(t, bool(e["acesa"]))
                elif e["tipo"] == "CRUZOU_PORTA":
                    self.cruzamentos.append(e)
            elif c == ESTADO:
                self.luz_estado.mudar(t, e["luz"])
                self.ocupacao_inf.mudar(t, e["ocupacao"])
                self.precedencia.mudar(t, e["precedencia"])
            elif c == DECISAO and e["tipo"] == "INTENCAO":
                self.intencoes.append(e)
            elif c == ATUACAO and e["tipo"] == "RESULTADO":
                self.resultados.append(e)
            elif c == ATUACAO and e["tipo"] == "COMUTACAO":
                self.comutacoes.append(e)
            elif c == SISTEMA:
                self.sistema.append(e)
                if e["tipo"] == "ALERTA":
                    self.alertas.append(e)
            elif c == PERCEPCAO:
                self.percepcao.append(e)

    # ------------------------------------------------------------- métricas
    def metricas(self) -> dict:
        fim = self.fim
        desperdicio = _cruzamento([self.luz, self.ocupada], fim, lambda l, o: l and not o)
        # Escuro com ocupante, exceto quando o morador apagou de propósito
        escuro = _cruzamento([self.luz, self.ocupada, self.luz_estado], fim,
                             lambda l, o, s: (not l) and o and s != APAGADA_MANUAL)

        indevidos = [i for i in self.intencoes
                     if i["acao"] == APAGAR and i["precedencia"] == AUTOMATICA and self.ocupada.em(i["t_ms"])]

        latencias = []
        for i in self.intencoes:
            ev = self.por_id.get(i.get("evidencia_id") or "")
            if ev is not None:
                latencias.append(i["t_ms"] - ev["t_ms"])

        # Atraso percebido: entrada em sala vazia e escura → luz acesa de fato
        atrasos = []
        for c in self.cruzamentos:
            t = c["t_ms"]
            if c["sentido"] != "ENTRADA" or self.ocupada.em(t - 1) or self.luz.em(t):
                continue
            prox = [ts for ts, v in zip(self.luz.ts, self.luz.vs) if ts >= t and v]
            atrasos.append((prox[0] if prox else fim) - t)

        # Desperdício por saída: sala fica vazia com luz acesa → luz apagada
        por_saida = []
        for c in self.cruzamentos:
            t = c["t_ms"]
            if c["sentido"] != "SAIDA" or self.ocupada.em(t + 1) or not self.luz.em(t):
                continue
            prox = [ts for ts, v in zip(self.luz.ts, self.luz.vs) if ts > t and not v]
            por_saida.append((prox[0] if prox else fim) - t)

        desconhecida = _cruzamento([self.ocupacao_inf], fim, lambda o: o == DESCONHECIDA)
        # O controlador começa em Desconhecida até a primeira avaliação; desconta o 1º segundo
        return {
            "desperdicio_s": round(desperdicio / 1000, 1),
            "escuro_com_ocupante_s": round(escuro / 1000, 1),
            "apagamentos_indevidos": len(indevidos),
            "acionamentos": len(self.intencoes),
            "latencia_reacao_ms_p95": _p95(latencias),
            "latencia_reacao_ms_max": max(latencias) if latencias else None,
            "atraso_percebido_ms_max": max(atrasos) if atrasos else None,
            "desperdicio_por_saida_s_max": round(max(por_saida) / 1000, 1) if por_saida else None,
            "ocupacao_desconhecida_s": round(desconhecida / 1000, 1),
            "tempo_ocupada_s": round(_cruzamento([self.ocupada], fim, bool) / 1000, 1),
            "tempo_luz_acesa_s": round(_cruzamento([self.luz], fim, bool) / 1000, 1),
            "alertas": sorted({a["alerta"] for a in self.alertas if a["ativo"]}),
        }

    # ----------------------------------------------------------- invariantes
    def invariantes(self) -> dict:
        r: dict[str, list[str]] = {f"OR-0{i}": [] for i in range(1, 7)}

        # OR-01: seq estritamente crescente e ids únicos (registro só acréscimo)
        seqs = [e["seq"] for e in self.ev]
        if seqs != list(range(1, len(seqs) + 1)):
            r["OR-01"].append("seq não é 1..n contínuo")
        if len({e["id"] for e in self.ev}) != len(self.ev):
            r["OR-01"].append("ids repetidos")

        # OR-02: nível de resultado válido e nunca acima da capacidade da lâmpada
        cap = self.sala.get("dispositivos", {}).get("LAMP-01", {}).get("capacidade", EFEITO_OBSERVADO)
        for res in self.resultados:
            if res["nivel"] not in NIVEIS_VALIDOS:
                r["OR-02"].append(f"nível inválido {res['nivel']} em {res['id']}")
            if res["nivel"] == EFEITO_OBSERVADO and cap != EFEITO_OBSERVADO:
                r["OR-02"].append(f"efeito observado sem capacidade em {res['id']}")

        # OR-03: ocupação Vazia só após T_apagamento sem detecção
        deteccoes = sorted(
            e["t_ms"] for e in self.percepcao
            if e["tipo"] in TIPOS_DETECCAO or (e["tipo"] == "HEARTBEAT" and e.get("alto"))
        )
        anterior = None
        for e in self.ev:
            if e["camada"] != ESTADO:
                continue
            if e["ocupacao"] == VAZIA and anterior != VAZIA:
                t = e["t_ms"]
                ult = [d for d in deteccoes if d <= t]
                if ult and t - ult[-1] < self.t_apagamento - 100:
                    r["OR-03"].append(f"Vazia em t={t} ms, {t - ult[-1]} ms após a última detecção")
            anterior = e["ocupacao"]
        # reinícios zeram a referência do controlador; nada a fazer aqui

        # OR-04: nenhum apagamento automático com ocupação desconhecida
        for i in self.intencoes:
            if i["acao"] == APAGAR and i["precedencia"] == AUTOMATICA and i.get("ocupacao_no_momento") == DESCONHECIDA:
                r["OR-04"].append(f"APAGAR automático com ocupação desconhecida em t={i['t_ms']} ms")

        # OR-05: cada chave produz no máximo um efeito
        vistas: dict[str, int] = {}
        for c in self.comutacoes:
            vistas[c["chave"]] = vistas.get(c["chave"], 0) + 1
        for k, n in vistas.items():
            if n > 1:
                r["OR-05"].append(f"chave {k} produziu {n} efeitos")

        # OR-06: o controlador nunca recebe a verdade
        fim = [e for e in self.sistema if e["tipo"] == "FIM"]
        if fim and fim[-1].get("entregas_ao_controlador", {}).get("VERDADE", 0):
            r["OR-06"].append("eventos de verdade entregues ao controlador")

        return {k: {"ok": not v, "violacoes": v[:5]} for k, v in r.items()}

    # ------------------------------------------------------------- asserções
    def verificar(self, a: dict, metricas: dict) -> tuple[bool, str]:
        e = a["entao"]
        tipo = e["tipo"]
        if tipo == "metrica":
            v = metricas.get(e["nome"])
            if v is None:
                return False, f"{e['nome']} indisponível"
            ok = True
            if "max" in e and v > e["max"]:
                ok = False
            if "min" in e and v < e["min"]:
                ok = False
            if "igual" in e and v != e["igual"]:
                ok = False
            return ok, f"{e['nome']} = {v}"
        if tipo == "luz":
            alvo = e["valor"] == "ACESA"
            if "em_ms" in e:
                v = self.luz.em(e["em_ms"])
                return v == alvo, f"luz em {e['em_ms']} ms = {'ACESA' if v else 'APAGADA'}"
            desde = e.get("desde_ms", 0)
            ate = e["ate_ms"]
            pontos = [t for t in self.luz.ts if desde <= t <= ate] + [desde]
            ok = any(self.luz.em(t) == alvo for t in pontos)
            return ok, f"luz {'atinge' if ok else 'não atinge'} {e['valor']} entre {desde} e {ate} ms"
        if tipo == "luz_constante":
            a0, a1 = e["entre_ms"]
            alvo = e["valor"] == "ACESA"
            pontos = [a0] + [t for t in self.luz.ts if a0 < t <= a1]
            ok = all(self.luz.em(t) == alvo for t in pontos)
            return ok, f"luz {'constante' if ok else 'muda'} em [{a0}, {a1}] ms"
        if tipo in ("intencao", "sem_intencao"):
            a0, a1 = e.get("entre_ms", [0, self.fim])
            achadas = [i for i in self.intencoes
                       if a0 <= i["t_ms"] <= a1 and i["acao"] == e["acao"]
                       and ("causa" not in e or i["causa"] == e["causa"])
                       and ("precedencia" not in e or i["precedencia"] == e["precedencia"])]
            if tipo == "intencao":
                n_min = e.get("min", 1)
                n_max = e.get("max", 10**9)
                ok = n_min <= len(achadas) <= n_max
            else:
                ok = not achadas
            ts = [i["t_ms"] for i in achadas][:5]
            return ok, f"{len(achadas)} intenção(ões) {e['acao']} em [{a0}, {a1}] ms {ts}"
        if tipo == "ocupacao":
            v = self.ocupacao_inf.em(e["em_ms"])
            return v == e["valor"], f"ocupação inferida em {e['em_ms']} ms = {v}"
        if tipo == "alerta":
            ativos = [x for x in self.alertas if x["alerta"] == e["alerta"] and x["ativo"]]
            a0, a1 = e.get("entre_ms", [0, self.fim])
            ok = any(a0 <= x["t_ms"] <= a1 for x in ativos)
            return ok, f"alerta {e['alerta']} {'ativado' if ok else 'não ativado'} em [{a0}, {a1}] ms"
        if tipo == "resultado":
            achados = [x for x in self.resultados if x["nivel"] == e["nivel"]
                       and ("divergencia" not in e or x["divergencia"] == e["divergencia"])]
            return bool(achados), f"{len(achados)} resultado(s) {e['nivel']}"
        if tipo == "evento":
            achados = [x for x in self.ev if x["camada"] == e["camada"] and x["tipo"] == e["evento"]]
            n_min = e.get("min", 1)
            return len(achados) >= n_min, f"{len(achados)} evento(s) {e['camada']}/{e['evento']}"
        if tipo == "relogio_nao_confiavel":
            depois = [x for x in self.ev if x["camada"] != VERDADE and x["t_ms"] >= e["apos_ms"]]
            ok = bool(depois) and all(x.get("relogio_confiavel") is False for x in depois)
            return ok, f"{len(depois)} evento(s) após {e['apos_ms']} ms, todos com relógio não confiável: {ok}"
        if tipo == "invariantes":
            inv = self.invariantes()
            falhas = [k for k, v in inv.items() if not v["ok"]]
            return not falhas, "todas respeitadas" if not falhas else f"violadas: {falhas}"
        return False, f"tipo de asserção desconhecido: {tipo}"


def avaliar(eventos: list[dict], roteiro: dict, sala: dict, esperado: Optional[dict]) -> dict:
    an = Analise(eventos, roteiro, sala)
    m = an.metricas()
    inv = an.invariantes()
    resultados = {}
    if esperado:
        for a in esperado.get("assercoes", []):
            ok, detalhe = an.verificar(a, m)
            resultados[a["id"]] = {"ok": ok, "nivel": a.get("nivel", "REQUISITO"), "detalhe": detalhe}
    req = [r for r in resultados.values() if r["nivel"] == "REQUISITO"]
    car = [r for r in resultados.values() if r["nivel"] == "CARACTERIZACAO"]
    inv_ok = all(v["ok"] for v in inv.values())
    return {
        "metricas": m,
        "invariantes": inv,
        "assercoes": resultados,
        # Requisitos e invariantes valem para qualquer controlador.
        "requisitos_ok": all(r["ok"] for r in req) and inv_ok,
        "requisitos": {"total": len(req), "ok": sum(r["ok"] for r in req)},
        # Caracterização descreve a referência: em outro controlador, "difere" não é falha.
        "caracterizacao": {"total": len(car), "igual_referencia": sum(r["ok"] for r in car)},
        "aprovado": all(r["ok"] for r in resultados.values()) and inv_ok,
    }
