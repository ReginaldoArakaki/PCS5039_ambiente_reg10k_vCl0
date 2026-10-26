"""Oráculo: métricas, invariantes e asserções (plano §10).

O oráculo é o único componente que lê a camada VERDADE junto com as demais.
Ele compara o que aconteceu (verdade) com o que o controlador decidiu e com o
que a lâmpada de fato fez.

v0dt: compara também três pontos de vista no mesmo instante — a verdade, o
DTReg10k-L (camada ESTADO) e o DTReg10k-R (camada PLATAFORMA) — e verifica as
invariantes OR-07 a OR-12 (plano v0dt §9).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from typing import Any, Optional

from sim.modelos import (
    ACENDER, APAGADA_MANUAL, APAGAR, ATUACAO, ATUAL, AUTOMATICA, DECISAO, DESCONHECIDA,
    EFEITO_OBSERVADO, ESTADO, EXECUCAO_RELATADA, DESCONHECIDO, LUZ_ACESA, OCUPADA, PERCEPCAO, PLATAFORMA,
    REDE, SISTEMA, SUBSTITUIDA, VAZIA, VERDADE,
)

NIVEIS_VALIDOS = {EFEITO_OBSERVADO, EXECUCAO_RELATADA, DESCONHECIDO, SUBSTITUIDA}
INVARIANTES = tuple(f"OR-{i:02d}" for i in range(1, 13))
PRAZO_ATUALIDADE_MS = 5_000   # PS11: divergência L × R tolerada até a sincronização
# v0dta: classes de fidelidade do espelho (plano v0dta §5)
FIEL = "FIEL"
PERCEPCAO_ERRO = "PERCEPCAO"
SINCRONIZACAO = "SINCRONIZACAO"
NAO_AFIRMA = "NAO_AFIRMA"
CLASSES_ESPELHO = (FIEL, PERCEPCAO_ERRO, SINCRONIZACAO, NAO_AFIRMA)
FALHAS_DE_REDE = {"CANAL_DESCONECTA", "PLATAFORMA_FORA", "CANAL_LATENCIA", "CANAL_DUPLICA", "CANAL_PERDE"}
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
    def __init__(self, eventos: list[dict], roteiro: dict, sala: dict, par: Optional[list[dict]] = None):
        self.ev = eventos
        self.roteiro = roteiro
        self.sala = sala
        self.par = par
        self.fim = roteiro["duracao_ms"]
        cfg = {**sala.get("controle", {}), **roteiro.get("controle", {})}
        self.t_apagamento = cfg.get("t_apagamento_ms", 60_000)
        self.t_apagamento_serie = Serie(self.t_apagamento)   # muda com CONFIG_APLICADA (v0dt)
        self.limite_atualidade = sala.get("plataforma", {}).get("limite_atualidade_ms", 60_000)
        # v0dt
        self.sessao = Serie(False)
        self.remoto_atual = Serie(False)
        self.remoto_valor = Serie((None, None))
        self.local_valor = Serie((DESCONHECIDA, "APAGADA"))
        self.estados_remotos: list[dict] = []
        self.mudancas_locais: list[dict] = []
        self.plataforma: list[dict] = []
        self.rede: list[dict] = []
        self.hub_ligado = Serie(True)

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
                self.local_valor.mudar(t, (e["ocupacao"], e["luz"]))
                if e.get("mudanca"):
                    self.mudancas_locais.append(e)
            elif c == PLATAFORMA:
                self.plataforma.append(e)
                if e["tipo"] == "ESTADO_REMOTO":
                    self.estados_remotos.append(e)
                    self.remoto_atual.mudar(t, e["atualidade"] == ATUAL)
                    self.remoto_valor.mudar(t, (e["ocupacao"], e["luz"]))
            elif c == REDE:
                self.rede.append(e)
                if e["tipo"] == "SESSAO_ESTABELECIDA":
                    self.sessao.mudar(t, True)
                elif e["tipo"] == "SESSAO_CAIU":
                    self.sessao.mudar(t, False)
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
                elif e["tipo"] == "HUB_DESLIGADO":
                    self.hub_ligado.mudar(t, False)
                elif e["tipo"] == "HUB_LIGADO":
                    self.hub_ligado.mudar(t, True)
                elif e["tipo"] == "CONFIG_APLICADA" and "t_apagamento_ms" in e:
                    self.t_apagamento_serie.mudar(t, e["t_apagamento_ms"])
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
            **self.metricas_gemeo(),
            **self.metricas_espelho(),
        }

    # ------------------------------------------------------ espelho (v0dta)
    def classe_espelho(self, t: int, visao: str = "R") -> str:
        """Compara o espelho com a verdade no instante t e classifica a causa da diferença."""
        real_ocup, real_luz = self.ocupada.em(t), self.luz.em(t)
        hub = self.hub_ligado.em(t)
        l_ocup, l_luz = self.local_valor.em(t)
        l_ok = hub and l_ocup != DESCONHECIDA and (l_ocup == OCUPADA) == real_ocup and (l_luz in LUZ_ACESA) == real_luz
        if visao == "L":
            if not hub or l_ocup == DESCONHECIDA:
                return NAO_AFIRMA  # hub desligado ou incerteza declarada (RN01)
            return FIEL if l_ok else PERCEPCAO_ERRO
        r_ocup, r_luz = self.remoto_valor.em(t)
        if not self.remoto_atual.em(t) or r_ocup in (None, DESCONHECIDA):
            return NAO_AFIRMA  # desatualizado, sem evidência ou ocupação desconhecida
        r_ok = r_ocup not in (None, DESCONHECIDA) and (r_ocup == OCUPADA) == real_ocup and (r_luz in LUZ_ACESA) == real_luz
        if r_ok:
            return FIEL
        return PERCEPCAO_ERRO if not l_ok else SINCRONIZACAO

    def segmentos_espelho(self, visao: str = "R") -> list[list]:
        series = (self.ocupada, self.luz, self.hub_ligado, self.local_valor, self.remoto_atual, self.remoto_valor)
        pontos = sorted({t for s in series for t in s.ts if t < self.fim} | {0, self.fim})
        segs: list[list] = []
        for a, b in zip(pontos, pontos[1:]):
            c = self.classe_espelho(a, visao)
            if segs and segs[-1][2] == c:
                segs[-1][1] = b
            else:
                segs.append([a, b, c])
        return segs

    def metricas_espelho(self) -> dict:
        tot = {c: 0 for c in CLASSES_ESPELHO}
        for a, b, c in self.segmentos_espelho("R"):
            tot[c] += b - a
        return {
            "espelho_fiel_s": round(tot[FIEL] / 1000, 1),
            "erro_de_percepcao_s": round(tot[PERCEPCAO_ERRO] / 1000, 1),
            "erro_de_sincronizacao_s": round(tot[SINCRONIZACAO] / 1000, 1),
            "espelho_nao_afirma_s": round(tot[NAO_AFIRMA] / 1000, 1),
            "espelho_fiel_pct": round(100 * tot[FIEL] / self.fim, 1) if self.fim else None,
        }

    # ------------------------------------------------------- métricas v0dt
    def _comandos(self) -> dict[str, dict]:
        cmds: dict[str, dict] = {}
        for e in self.plataforma:
            if e["tipo"] == "APP_COMANDO":
                cmds[e["chave"]] = {"t_app": e["t_ms"], "acao": e["acao"], "exibicoes": []}
            elif e["tipo"] == "APP_RESULTADO" and e["chave"] in cmds:
                cmds[e["chave"]]["exibicoes"].append(e)
        for e in self.sistema:
            if e["tipo"] == "COMANDO_REMOTO_RECEBIDO" and e["chave"] in cmds:
                cmds[e["chave"]].setdefault("recebidos", []).append(e)
        for i in self.intencoes:
            if i.get("chave_remota") in cmds:
                cmds[i["chave_remota"]].setdefault("intencoes", []).append(i)
        return cmds

    def metricas_gemeo(self) -> dict:
        fim = self.fim
        # Atualidade: mudança no L (com sessão ativa) até o R refleti-la
        atrasos = []
        for m in self.mudancas_locais:
            if not self.sessao.em(m["t_ms"]):
                continue
            seg = [r for r in self.estados_remotos if r.get("ref_seq", -1) >= m["seq"] and r["t_ms"] >= m["t_ms"]]
            if seg:
                atrasos.append(seg[0]["t_ms"] - m["t_ms"])
        cmds = self._comandos()
        lat_cmd = [c["exibicoes"][0]["latencia_ms"] for c in cmds.values() if c["exibicoes"]]
        vencidos = 0
        duplicados = 0
        for c in cmds.values():
            validade = {r["valida_ate_ms"] for r in c.get("recebidos", [])}
            its = c.get("intencoes", [])
            duplicados += max(0, len(its) - 1)
            vencidos += sum(1 for i in its if validade and i["t_ms"] > min(validade))
        # Reconciliação: sessão restabelecida → R volta a ATUAL
        reconc = []
        estab = [e["t_ms"] for e in self.rede if e["tipo"] == "SESSAO_ESTABELECIDA"]
        for t in estab[1:]:
            prox = [r["t_ms"] for r in self.estados_remotos if r["t_ms"] >= t and r["atualidade"] == ATUAL]
            reconc.append((prox[0] if prox else fim) - t)
        # Divergência L × R além do prazo de sincronização, com o R dizendo "atual"
        pontos = sorted({t for s in (self.remoto_atual, self.remoto_valor, self.local_valor) for t in s.ts if t < fim}
                        | {fim})
        divergencia, inicio = 0, None
        for a, b in zip(pontos, pontos[1:]):
            dif = self.remoto_atual.em(a) and self.remoto_valor.em(a) != self.local_valor.em(a)
            if dif:
                inicio = a if inicio is None else inicio
                divergencia += max(0, b - max(a, inicio + PRAZO_ATUALIDADE_MS))
            else:
                inicio = None
        sinc = next((e for e in self.sistema if e["tipo"] == "SINCRONIZACAO"), None)
        hub = (sinc or {}).get("hub", {})
        nao_atual = _cruzamento([self.remoto_atual], fim, lambda v: not v)
        return {
            "atualidade_gemeo_ms_p95": _p95(atrasos),
            "comando_remoto_ms_p95": _p95(lat_cmd),
            "comandos_remotos": len(cmds),
            "comandos_vencidos_executados": vencidos,
            "efeitos_duplicados_remotos": duplicados,
            "reconciliacao_ms_max": max(reconc) if reconc else None,
            "divergencia_alem_prazo_s": round(divergencia / 1000, 1),
            "gemeo_nao_atual_s": round(nao_atual / 1000, 1),
            "eventos_nao_entregues": hub.get("pendentes_na_fila"),
            "fila_max": hub.get("fila_max"),
        }

    # ----------------------------------------------------------- invariantes
    def invariantes(self) -> dict:
        r: dict[str, list[str]] = {k: [] for k in INVARIANTES}

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
                # o T_apagamento vigente pode mudar por configuração (v0dt); vale o menor do intervalo
                t_ap = min(self.t_apagamento_serie.em(ult[-1]), self.t_apagamento_serie.em(t)) if ult else 0
                if ult and t - ult[-1] < t_ap - 100:
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

        self._invariantes_gemeo(r)
        saida = {k: {"ok": not v, "violacoes": v[:5]} for k, v in r.items()}
        if self.par is None:
            saida["OR-12"]["aplica"] = False
        return saida

    def _invariantes_gemeo(self, r: dict) -> None:
        cmds = self._comandos()
        # OR-07: nenhuma intenção remota executada após validaAte
        for chave, c in cmds.items():
            for rec in c.get("recebidos", []):
                if rec["decisao"] == "ACEITO" and rec["t_ms"] > rec["valida_ate_ms"]:
                    r["OR-07"].append(f"{chave} aceito vencido em t={rec['t_ms']} ms")
            validade = [x["valida_ate_ms"] for x in c.get("recebidos", [])]
            for i in c.get("intencoes", []):
                if validade and i["t_ms"] > min(validade):
                    r["OR-07"].append(f"{chave} executado em t={i['t_ms']} ms após {min(validade)} ms")
        # OR-08: o R nunca diz "atual" com idade acima do limite ou sem sessão
        lim = self.limite_atualidade
        for i, e in enumerate(self.estados_remotos):
            if e["atualidade"] != ATUAL:
                continue
            if e["conexao"] != "CONECTADO":
                r["OR-08"].append(f"ATUAL sem sessão em t={e['t_ms']} ms")
            fim_int = self.estados_remotos[i + 1]["t_ms"] if i + 1 < len(self.estados_remotos) else self.fim
            rec = e.get("recepcao_ms")
            if rec is None or fim_int - rec > lim + 200:
                r["OR-08"].append(f"ATUAL até t={fim_int} ms com estado recebido em {rec} ms")
        for e in self.plataforma:
            if e["tipo"] == "APP_CONSULTA" and e.get("atualidade") == ATUAL:
                if e.get("conexao") != "CONECTADO" or (e.get("idade_ms") or 0) > lim:
                    r["OR-08"].append(f"app mostrou ATUAL em t={e['t_ms']} ms com idade {e.get('idade_ms')} ms")
        # OR-09: estado aplicado no R só avança (n e ref_seq crescentes)
        aplic = [e for e in self.estados_remotos if "n" in e]
        for a, b in zip(aplic, aplic[1:]):
            if b["n"] <= a["n"] or b["ref_seq"] < a["ref_seq"]:
                r["OR-09"].append(f"estado mais antigo aplicado em t={b['t_ms']} ms (n {a['n']} → {b['n']})")
        # OR-10: versão aplicada no hub ≤ vigente no R; pendente termina resolvida
        criadas = [(0, 1)] + [(e["t_ms"], e["versao"]) for e in self.plataforma
                              if e["tipo"] == "CONFIG_VERSAO" and e["estado"] == "PENDENTE"]
        for e in self.sistema:
            if e["tipo"] == "CONFIG_APLICADA":
                vigente = max(v for t, v in criadas if t <= e["t_ms"])
                if e["versao"] > vigente:
                    r["OR-10"].append(f"hub aplicou v{e['versao']} com vigente v{vigente} em t={e['t_ms']} ms")
        final: dict[int, tuple] = {}
        for e in self.plataforma:
            if e["tipo"] == "CONFIG_VERSAO":
                final[e["versao"]] = (e["estado"], e["t_ms"])
        for v, (estado, t) in final.items():
            if estado == "PENDENTE" and self.sessao.em(self.fim) and t < self.fim - 15_000:
                ultima_sessao = max([x["t_ms"] for x in self.rede if x["tipo"] == "SESSAO_ESTABELECIDA"] or [0])
                if self.fim - max(t, ultima_sessao) > 15_000:
                    r["OR-10"].append(f"v{v} continua pendente com sessão ativa")
        # OR-11: cada comando remoto produz no máximo um efeito
        for chave, c in cmds.items():
            if len(c.get("intencoes", [])) > 1:
                r["OR-11"].append(f"{chave} gerou {len(c['intencoes'])} intenções")
        # OR-12: com a rede ou a plataforma fora, as decisões locais são as mesmas
        if self.par is not None:
            a, b = _assinatura(self.ev), _assinatura(self.par)
            if a != b:
                dif = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                r["OR-12"].append(f"decisões locais diferem da execução sem falha de rede a partir do item {dif}: "
                                  f"{a[dif] if dif < len(a) else '—'} × {b[dif] if dif < len(b) else '—'}")

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
            a0, a1 = e.get("entre_ms", [0, self.fim])
            achados = [x for x in self.ev if x["camada"] == e["camada"] and x["tipo"] == e["evento"]
                       and a0 <= x["t_ms"] <= a1
                       and all(x.get(k) == v for k, v in e.get("campos", {}).items())]
            n_min = e.get("min", 1)
            n_max = e.get("max", 10**9)
            return n_min <= len(achados) <= n_max, f"{len(achados)} evento(s) {e['camada']}/{e['evento']}"
        if tipo == "espelho":
            c = self.classe_espelho(e["em_ms"], e.get("visao", "R"))
            return c == e["classe"], f"espelho {e.get('visao', 'R')} em {e['em_ms']} ms: {c}"
        if tipo == "gemeo":
            t = e["em_ms"]
            ultimos = [x for x in self.estados_remotos if x["t_ms"] <= t]
            if not ultimos:
                return False, f"DTReg10k-R sem estado em {t} ms"
            x = ultimos[-1]
            difs = [k for k in ("atualidade", "ocupacao", "luz", "conexao", "precedencia") if k in e and x.get(k) != e[k]]
            vals = ", ".join(f"{k}={x.get(k)}" for k in ("atualidade", "ocupacao", "luz", "conexao"))
            return not difs, f"DTReg10k-R em {t} ms: {vals}"
        if tipo == "comando":
            cmds = list(self._comandos().items())
            idx = e.get("indice", 1)
            if len(cmds) < idx:
                return False, f"comando {idx} não encontrado"
            chave, c = cmds[idx - 1]
            exib = [x for x in c["exibicoes"] if x["final"]] if e.get("final", True) else c["exibicoes"]
            if not exib:
                return False, f"{chave}: o app não mostrou resultado {'final ' if e.get('final', True) else ''}"
            x = exib[0]
            ok = x["nivel"] == e["nivel"]
            if "motivo" in e:
                ok = ok and x.get("motivo") == e["motivo"]
            if "latencia_max_ms" in e:
                ok = ok and x["latencia_ms"] <= e["latencia_max_ms"]
            return ok, f"{chave}: app mostra {x['nivel']} ({x.get('motivo') or '—'}) após {x['latencia_ms']} ms"
        if tipo == "config":
            ate = e.get("ate_ms", self.fim)
            ests = [x for x in self.plataforma if x["tipo"] == "CONFIG_VERSAO" and x["versao"] == e["versao"]
                    and x["t_ms"] <= ate]
            if not ests:
                return False, f"versão {e['versao']} não existe até {ate} ms"
            x = ests[-1]
            return x["estado"] == e["estado"], f"versão {e['versao']}: {x['estado']} em {x['t_ms']} ms"
        if tipo == "app_consulta":
            cons = [x for x in self.plataforma if x["tipo"] == "APP_CONSULTA"]
            idx = e.get("indice", 1)
            if len(cons) < idx:
                return False, f"consulta {idx} não encontrada"
            x = cons[idx - 1]
            difs = [k for k, v in e.get("campos", {}).items() if x.get(k) != v]
            vals = ", ".join(f"{k}={x.get(k)}" for k in e.get("campos", {}))
            return not difs, f"consulta {idx} em {x['t_ms']} ms: {vals}"
        if tipo == "relogio_nao_confiavel":
            depois = [x for x in self.ev if x["camada"] not in (VERDADE, REDE, PLATAFORMA) and x["t_ms"] >= e["apos_ms"]]
            ok = bool(depois) and all(x.get("relogio_confiavel") is False for x in depois)
            return ok, f"{len(depois)} evento(s) após {e['apos_ms']} ms, todos com relógio não confiável: {ok}"
        if tipo == "invariantes":
            inv = self.invariantes()
            falhas = [k for k, v in inv.items() if not v["ok"]]
            return not falhas, "todas respeitadas" if not falhas else f"violadas: {falhas}"
        return False, f"tipo de asserção desconhecido: {tipo}"


def _assinatura(eventos: list[dict]) -> list[tuple]:
    """Decisões e atuações locais, para a execução pareada da OR-12."""
    out = []
    for e in eventos:
        if e["camada"] in (DECISAO, ATUACAO):
            out.append((e["t_ms"], e["tipo"], e.get("acao"), e.get("causa"), e.get("chave"), e.get("nivel"),
                        e.get("ligado")))
    return out


def tem_falha_de_rede(roteiro: dict) -> bool:
    return any(f["tipo"] in FALHAS_DE_REDE for f in roteiro.get("falhas", [])) or \
        (roteiro.get("rede", {}).get("modo") or roteiro.get("modo", "IDEAL")).upper() == "REALISTA"


def tem_app(roteiro: dict) -> bool:
    """Comandos e preferências mudam decisões locais de propósito; consultas, não."""
    return any(a.get("acao") in ("APP_COMANDO", "APP_PREFERENCIA") for a in roteiro.get("acoes", []))


def roteiro_sem_rede(roteiro: dict) -> dict:
    """Mesmo roteiro, sem falhas de rede e com canal ideal (par da OR-12)."""
    r = dict(roteiro)
    r["falhas"] = [f for f in roteiro.get("falhas", []) if f["tipo"] not in FALHAS_DE_REDE]
    r["rede"] = {"modo": "IDEAL"}
    return r


def avaliar(eventos: list[dict], roteiro: dict, sala: dict, esperado: Optional[dict],
            par: Optional[list[dict]] = None) -> dict:
    an = Analise(eventos, roteiro, sala, par)
    m = an.metricas()
    from avaliacao.espelho import amostras  # v0dta
    espelho = {"segmentos": {"R": an.segmentos_espelho("R"), "L": an.segmentos_espelho("L")},
               "amostras": amostras(an)}
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
        "espelho": espelho,
    }
