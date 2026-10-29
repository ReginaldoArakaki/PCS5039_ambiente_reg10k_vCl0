"""Plataforma simulada: gateway, DTReg10k-R, comandos, configuração e app (plano v0dt §4).

DTReg10k-R é uma projeção do que chegou do hub. Ele não decide nada sobre a
sala: o hub é a autoridade sobre fatos locais (RN27). A plataforma é a
autoridade sobre a configuração (RN28).

Regras:
- RN-DT-04: cada atributo é ATUAL (sessão ativa e idade ≤ 60 s, PS06),
  DESATUALIZADO ou SEM_EVIDENCIA. A idade conta desde a recepção do último
  estado (evento de estado ou resumo), no relógio da plataforma.
- RN-DT-03: estado só é aplicado se vier com `n` maior que o último aplicado;
  o histórico recebido na reconexão vai para o registro consolidado, não para
  o estado atual.
- RN-DT-05 / RN-DT-06: comando remoto com validade de 30 s e chave; com o hub
  desconectado, recusa imediata com motivo, última evidência e idade.
- RN-DT-07: preferência cria nova versão "pendente" até o hub confirmar.
- nucleo-v1.4 (v3dt.1): sugestões do gêmeo (T_apagamento por cômodo e faixa
  horária) ficam PENDENTES até o titular aceitar ou recusar no app. Só o aceite
  cria versão de configuração, que leva as faixas de todos os cômodos e a lista
  das sugestões de origem (OR-17). Recusa é registrada e nunca aplicada.
"""
from __future__ import annotations

import random
from typing import Optional

from plataforma.canal import DESCE
from sim.modelos import (
    ATUAL, DESATUALIZADO, DESCONHECIDO, PLATAFORMA, REDE, REJEITADA, SEM_EVIDENCIA, ConfigSala,
)

FINAIS = {"EFEITO_OBSERVADO", "EXECUCAO_RELATADA", "DESCONHECIDO", "SUBSTITUIDA", REJEITADA, "EXPIRADA"}


def _lat(rng: random.Random, faixa) -> float:
    a, b = faixa
    return a if a == b else rng.uniform(a, b)


class RepresentacaoComodo:
    """Estado de um cômodo no DTReg10k-R (EstadoComodo da V2; RN-V1-04)."""

    def __init__(self, comodo: str):
        self.comodo = comodo
        self.estado: Optional[dict] = None
        self.n_aplicado = 0
        self.recepcao: Optional[float] = None
        self.aguarda = True   # após queda da sessão, só um estado novo restabelece a atualidade
        self.atualidade = SEM_EVIDENCIA
        self.ultimo_log = None


class Plataforma:
    def __init__(self, reg, canal, p: dict, p_app: dict, rng: random.Random, agendar, config_inicial: ConfigSala,
                 comodos: Optional[list[str]] = None):
        self.reg = reg
        self.canal = canal
        self.p = p
        self.p_app = p_app
        self.rng = rng
        self.agendar = agendar
        self.agente = None
        self.fora = False
        self.sessao = False
        # DTReg10k-R: uma representação por cômodo
        self.comodos = list(comodos or ["sala"])
        self.r = {cid: RepresentacaoComodo(cid) for cid in self.comodos}
        self.ultima_evidencia: Optional[float] = None
        self.recebidas: set[int] = set()
        self.duplicadas = 0
        self.historico_fora_de_ordem = 0
        # comandos
        self.n_cmd = 0
        self.comandos: dict[str, dict] = {}
        # configuração
        self.versao_vigente = 1
        self.versoes = {1: {"parametros": {"t_apagamento_ms": config_inicial.t_apagamento_ms},
                            "estado": "APLICADA", "criada_ms": 0}}
        self.versao_aplicada_hub = 1
        # nucleo-v1.4: sugestões do gêmeo e faixas aceitas (por cômodo)
        self.sugestoes: dict[str, dict] = {}
        self.faixas_aceitas: dict[str, list] = {}
        self._inicio_pendente: list = []

    # Compatibilidade com a v0dt (um cômodo)
    @property
    def estado(self) -> Optional[dict]:
        return self.r[self.comodos[0]].estado

    @property
    def atualidade(self) -> str:
        return self.r[self.comodos[0]].atualidade

    # ============================================================== sessão
    def sessao_estabelecida(self, t: float) -> None:
        self.sessao = True
        self._atualizar(t)
        # RF-SYN-06: distribui a configuração vigente se o hub ainda não a aplicou
        self._distribuir_config(t)

    def sessao_caiu(self, t: float, motivo: str) -> None:
        if self.fora:
            return
        self.sessao = False
        for rc in self.r.values():
            rc.aguarda = True
        self._atualizar(t)

    def cair(self, t: float) -> None:
        """Falha PLATAFORMA_FORA: a plataforma para; o estado persistido fica."""
        self.reg.add(REDE, "PLATAFORMA_FORA", t)
        self.sessao = False
        for rc in self.r.values():
            rc.aguarda = True
        self._atualizar(t)   # último registro antes de parar: nada mais é "atual"
        self.fora = True

    def voltar(self, t: float) -> None:
        self.fora = False
        self.reg.add(REDE, "PLATAFORMA_VOLTOU", t)
        self._atualizar(t)

    # ===================================================== hub → plataforma
    def receber(self, t: float, msg: dict) -> None:
        if self.fora or not self.sessao:
            return  # a mensagem se perde; o hub a reenviará (fila)
        tipo = msg["tipo"]
        if tipo == "ACK_COMANDO":
            c = self.comandos.get(msg["chave"])
            if c:
                c["ack"] = True
            return
        n = msg["n"]
        self.canal.enviar(t, DESCE, {"tipo": "ACK", "n": n}, self.agente.receber)
        if n in self.recebidas:
            self.duplicadas += 1
            return
        self.recebidas.add(n)
        if tipo == "RESUMO":
            for cid, estado in (msg.get("comodos") or {}).items():
                if estado is not None and cid in self.r:
                    self._aplicar_estado(t, n, estado, msg["ref_seq"], "RESUMO", msg.get("reconexao", False), cid)
            self._conferir_config(t, msg["versao_config"])
        elif tipo == "EVENTO":
            self._evento(t, n, msg)
        elif tipo == "RESULTADO_COMANDO":
            self._resultado_comando(t, msg)
        elif tipo == "RESULTADO_CONFIG":
            self._resultado_config(t, msg)

    def _evento(self, t: float, n: int, msg: dict) -> None:
        d = msg["dados"]
        if msg["camada"] == "ESTADO":
            cid = d.get("comodo", self.comodos[0])
            estado = {k: d.get(k) for k in ("ocupacao", "luz", "precedencia", "idade_evidencia_ms", "alertas")}
            self._aplicar_estado(t, n, estado, msg["ref_seq"], "EVENTO", False, cid)
        elif msg["camada"] == "PERCEPCAO":
            cids = d.get("comodos") or [self.comodos[0]]
            if msg["evento"] in ("PASSAGEM", "MOVIMENTO", "INTERRUPTOR"):
                self.ultima_evidencia = max(self.ultima_evidencia or 0, t)
            if msg["evento"] in ("PASSAGEM", "MOVIMENTO", "FIM_MOVIMENTO", "INTERRUPTOR"):
                # v0dta: o espelho mostra o sinal quando ele CHEGA à plataforma
                self.reg.add(PLATAFORMA, "EVIDENCIA_RECEBIDA", t, origem=d.get("origem"), evidencia=msg["evento"],
                             t_origem_ms=msg["t_origem"], atraso_ms=int(t - msg["t_origem"]),
                             historico=any(n < self.r[c].n_aplicado for c in cids if c in self.r), comodos=cids)
        elif msg["camada"] == "SISTEMA" and msg["evento"] == "SUSPEITA_PRESENCA":
            # nucleo-v1.3 (RF-OPR-06): evento de fronteira para ocorrências, sem rotular invasão (RN03)
            self.reg.add(PLATAFORMA, "EVENTO_FRONTEIRA", t, evento="PRESENCA_NAO_EXPLICADA", destino="OCORRENCIAS",
                         suspeita=d.get("suspeita"), desde_ms=d.get("desde_ms"), t_origem_ms=msg["t_origem"],
                         comodos=d.get("comodos"), descricao="presença não explicada")
        elif msg["camada"] == "ATUACAO" and msg["evento"] == "RESULTADO":
            cid = d.get("comodo", self.comodos[0])
            self.reg.add(PLATAFORMA, "RESULTADO_RECEBIDO", t, chave=d.get("chave"), acao=d.get("acao"),
                         nivel=d.get("nivel"), t_origem_ms=msg["t_origem"],
                         historico=n < self.r[cid].n_aplicado if cid in self.r else False, comodo=cid)

    def _aplicar_estado(self, t: float, n: int, estado: dict, ref_seq: int, origem: str, reconexao: bool,
                        cid: str) -> None:
        rc = self.r[cid]
        if n <= rc.n_aplicado:
            # OR-09: histórico ou mensagem atrasada não substitui estado mais recente
            self.historico_fora_de_ordem += 1
            return
        anterior = rc.estado
        if reconexao and anterior is not None:
            for k in ("ocupacao", "luz"):
                if anterior.get(k) != estado.get(k):
                    # RF-SYN-05: divergência resolvida pela autoridade do hub (RN27)
                    self.reg.add(PLATAFORMA, "DIVERGENCIA", t, atributo=k, valor_remoto=anterior.get(k),
                                 valor_local=estado.get(k), autoridade="DTReg10k-L", resolucao="ADOTA_LOCAL",
                                 comodo=cid)
        rc.estado = dict(estado)
        rc.n_aplicado = n
        rc.recepcao = t
        rc.aguarda = False
        self._atualizar_comodo(t, rc, ref_seq=ref_seq, origem=origem, forcar=(origem == "RESUMO"))

    # =========================================================== atualidade
    def _idade(self, t: float, cid: Optional[str] = None) -> Optional[int]:
        rc = self.r[cid or self.comodos[0]]
        return None if rc.recepcao is None else int(t - rc.recepcao)

    def _atualizar(self, t: float) -> None:
        for rc in self.r.values():
            self._atualizar_comodo(t, rc)

    def _atualizar_comodo(self, t: float, rc: RepresentacaoComodo, ref_seq: Optional[int] = None,
                          origem: Optional[str] = None, forcar: bool = False) -> None:
        if self.fora:
            return
        idade = None if rc.recepcao is None else int(t - rc.recepcao)
        if rc.estado is None:
            atual = SEM_EVIDENCIA
        elif self.sessao and not rc.aguarda and idade is not None and idade <= self.p["limite_atualidade_ms"]:
            atual = ATUAL
        else:
            atual = DESATUALIZADO
        rc.atualidade = atual
        e = rc.estado or {}
        chave = (e.get("ocupacao"), e.get("luz"), e.get("precedencia"), tuple(e.get("alertas") or ()),
                 atual, self.sessao)
        # Registra quando algo muda e a cada resumo recebido (para a idade exibida)
        if chave != rc.ultimo_log or forcar:
            campos = {"ocupacao": e.get("ocupacao"), "luz": e.get("luz"), "precedencia": e.get("precedencia"),
                      "alertas": list(e.get("alertas") or []), "atualidade": atual,
                      "conexao": "CONECTADO" if self.sessao else "DESCONECTADO",
                      "recepcao_ms": None if rc.recepcao is None else int(rc.recepcao),
                      "mudanca": chave != rc.ultimo_log, "comodo": rc.comodo}
            if ref_seq is not None:
                campos.update(ref_seq=ref_seq, origem=origem, n=rc.n_aplicado)
            self.reg.add(PLATAFORMA, "ESTADO_REMOTO", t, **campos)
            rc.ultimo_log = chave

    def tick(self, t: float) -> None:
        if self.fora:
            return
        self._atualizar(t)
        prazo = self.p["prazo_resultado_ms"]
        for chave, c in self.comandos.items():
            if c["final"]:
                continue
            if not c["provisorio"] and t - c["criado_ms"] >= prazo:
                # PS02: sem resultado em 10 s, o app mostra "desconhecido"
                c["provisorio"] = True
                self._ao_app(t, chave, DESCONHECIDO, "SEM_RESULTADO_NO_PRAZO", final=False)
            if self.sessao and not c["ack"] and t < c["valida_ate_ms"] and t - c["enviado_ms"] >= self.p["reenvio_ms"]:
                self._enviar_comando(t, c)
        if self.sessao:
            for v, cfg in self.versoes.items():
                if cfg["estado"] == "PENDENTE" and t - cfg.get("enviada_ms", -10**9) >= self.p["reenvio_ms"]:
                    self._enviar_config(t, v)

    # ============================================================== comandos
    def app_comando(self, t: float, acao: str, comodo: Optional[str] = None) -> None:
        """RN-V1-03: o comando indica o cômodo (padrão: o primeiro)."""
        cid = comodo or self.comodos[0]
        self.n_cmd += 1
        chave = f"CMD-{self.n_cmd:03d}"
        self.reg.add(PLATAFORMA, "APP_COMANDO", t, chave=chave, acao=acao, comodo=cid)
        if self.fora:
            self._mostrar(t + _lat(self.rng, self.p_app["latencia_ms"]), chave, REJEITADA,
                          "PLATAFORMA_INDISPONIVEL", True, t, cid)
            return
        self.agendar(t + _lat(self.rng, self.p_app["latencia_ms"]),
                     lambda tt: self._criar_comando(tt, chave, acao, t, cid))

    def _criar_comando(self, t: float, chave: str, acao: str, t_app: float, cid: str) -> None:
        if self.fora:
            self._mostrar(t, chave, REJEITADA, "PLATAFORMA_INDISPONIVEL", True, t_app, cid)
            return
        if not self.sessao:
            # RN-DT-06: recusa imediata, com a última evidência e a idade; nada fica pendente
            idade = self._idade(t, cid)
            self.reg.add(PLATAFORMA, "COMANDO_RECUSADO", t, chave=chave, acao=acao, motivo="HUB_DESCONECTADO",
                         ultima_evidencia_ms=None if self.ultima_evidencia is None else int(self.ultima_evidencia),
                         idade_estado_ms=idade, comodo=cid)
            self.comandos[chave] = {"chave": chave, "acao": acao, "t_app": t_app, "criado_ms": t,
                                    "valida_ate_ms": t, "final": True, "provisorio": True, "ack": True,
                                    "enviado_ms": t, "comodo": cid}
            self._ao_app(t, chave, REJEITADA, "HUB_DESCONECTADO", final=True)
            return
        valida = int(t + self.p["validade_comando_ms"])
        c = {"chave": chave, "acao": acao, "t_app": t_app, "criado_ms": t, "valida_ate_ms": valida,
             "final": False, "provisorio": False, "ack": False, "enviado_ms": t, "comodo": cid}
        self.comandos[chave] = c
        self.reg.add(PLATAFORMA, "COMANDO_CRIADO", t, chave=chave, acao=acao, valida_ate_ms=valida,
                     solicitante="titular", comodo=cid)
        self._enviar_comando(t, c)

    def _enviar_comando(self, t: float, c: dict) -> None:
        c["enviado_ms"] = t
        self.canal.enviar(t, DESCE, {"tipo": "COMANDO", "chave": c["chave"], "acao": c["acao"],
                                     "valida_ate_ms": c["valida_ate_ms"], "solicitante": "titular",
                                     "comodo": c["comodo"]},
                          self.agente.receber)

    def _resultado_comando(self, t: float, msg: dict) -> None:
        c = self.comandos.get(msg["chave"])
        if c is None:
            return
        c["ack"] = True
        self.reg.add(PLATAFORMA, "COMANDO_RESULTADO", t, chave=msg["chave"], nivel=msg["nivel"],
                     motivo=msg.get("motivo"), comodo=c["comodo"])
        if not c["final"]:
            c["final"] = True
            self._ao_app(t, msg["chave"], msg["nivel"], msg.get("motivo"), final=True)

    def _ao_app(self, t: float, chave: str, nivel: str, motivo: Optional[str], final: bool) -> None:
        c = self.comandos[chave]
        self._mostrar(t + _lat(self.rng, self.p_app["latencia_ms"]), chave, nivel, motivo, final, c["t_app"], c["comodo"])

    def _mostrar(self, t: float, chave: str, nivel: str, motivo, final: bool, t_app: float, cid: str) -> None:
        def registrar(tt):
            self.reg.add(PLATAFORMA, "APP_RESULTADO", tt, chave=chave, nivel=nivel, motivo=motivo, final=final,
                         latencia_ms=int(tt - t_app), comodo=cid)
        self.agendar(t, registrar)

    # ========================================================== configuração
    def app_preferencia(self, t: float, parametros: dict) -> None:
        self.reg.add(PLATAFORMA, "APP_PREFERENCIA", t, parametros=parametros)
        if self.fora:
            self._mostrar_cfg(t, None, "REJEITADA", "PLATAFORMA_INDISPONIVEL")
            return
        self.agendar(t + _lat(self.rng, self.p_app["latencia_ms"]), lambda tt: self._nova_versao(tt, parametros))

    def _nova_versao(self, t: float, parametros: dict) -> None:
        lo, hi = self.p["t_apagamento_limites_ms"]
        v = parametros.get("t_apagamento_ms")
        if v is None or not lo <= v <= hi:
            self.reg.add(PLATAFORMA, "CONFIG_REJEITADA", t, parametros=parametros, motivo="FORA_DA_POLITICA",
                         limites_ms=[lo, hi])
            self._mostrar_cfg(t, None, "REJEITADA", "FORA_DA_POLITICA")
            return
        self.versao_vigente += 1
        nv = self.versao_vigente
        for antiga, cfg in self.versoes.items():
            if cfg["estado"] == "PENDENTE":
                cfg["estado"] = "SUBSTITUIDA"
                self.reg.add(PLATAFORMA, "CONFIG_VERSAO", t, versao=antiga, estado="SUBSTITUIDA")
        self.versoes[nv] = {"parametros": dict(parametros), "estado": "PENDENTE", "criada_ms": t}
        self.reg.add(PLATAFORMA, "CONFIG_VERSAO", t, versao=nv, estado="PENDENTE", parametros=parametros,
                     aplicada_hub=self.versao_aplicada_hub)
        self._mostrar_cfg(t, nv, "PENDENTE", None)
        if self.sessao:
            self._enviar_config(t, nv)

    def _enviar_config(self, t: float, v: int) -> None:
        self.versoes[v]["enviada_ms"] = t
        self.canal.enviar(t, DESCE, {"tipo": "CONFIG", "versao": v, "parametros": self.versoes[v]["parametros"]},
                          self.agente.receber)

    def _distribuir_config(self, t: float) -> None:
        v = self.versao_vigente
        if self.versoes[v]["estado"] == "PENDENTE":
            self._enviar_config(t, v)

    def _resultado_config(self, t: float, msg: dict) -> None:
        v = msg["versao"]
        self.versao_aplicada_hub = max(self.versao_aplicada_hub, msg.get("aplicada", 0))
        cfg = self.versoes.get(v)
        if cfg is None or cfg["estado"] != "PENDENTE":
            return
        cfg["estado"] = msg["estado"]
        self.reg.add(PLATAFORMA, "CONFIG_VERSAO", t, versao=v, estado=msg["estado"],
                     aplicada_hub=self.versao_aplicada_hub)
        self._mostrar_cfg(t, v, msg["estado"], None)

    def _conferir_config(self, t: float, aplicada: int) -> None:
        self.versao_aplicada_hub = max(self.versao_aplicada_hub, aplicada)
        if aplicada < self.versao_vigente and self.versoes[self.versao_vigente]["estado"] == "PENDENTE":
            return  # já em distribuição
        if aplicada > self.versao_vigente:
            self.reg.add(PLATAFORMA, "DIVERGENCIA", t, atributo="versao_config", valor_remoto=self.versao_vigente,
                         valor_local=aplicada, autoridade="DTReg10k-R", resolucao="REGISTRADA")

    def _mostrar_cfg(self, t: float, versao, estado: str, motivo) -> None:
        def registrar(tt):
            self.reg.add(PLATAFORMA, "APP_CONFIG", tt, versao=versao, estado=estado, motivo=motivo)
        self.agendar(t + _lat(self.rng, self.p_app["latencia_ms"]), registrar)

    # ============================================== sugestões (nucleo-v1.4)
    def configuracao_inicial(self, cfg: dict) -> None:
        """Versão já aplicada em dias anteriores, com as faixas e as sugestões aceitas que a originaram."""
        v = int(cfg.get("versao", 1))
        self.faixas_aceitas = {cid: [dict(f) for f in fs] for cid, fs in (cfg.get("faixas") or {}).items()}
        par = {"t_apagamento_ms": self.versoes[1]["parametros"]["t_apagamento_ms"]}
        if self.faixas_aceitas:
            par["faixas"] = self.faixas_aceitas
        self.versoes = {v: {"parametros": par, "estado": "APLICADA", "criada_ms": 0,
                            "sugestoes": list(cfg.get("sugestoes_aceitas") or [])}}
        self.versao_vigente = self.versao_aplicada_hub = v
        self._inicio_pendente.append(("CONFIG_VERSAO", {"versao": v, "estado": "APLICADA", "origem": "DIAS_ANTERIORES",
                                                        "parametros": par,
                                                        "sugestoes": list(cfg.get("sugestoes_aceitas") or [])}))

    def sugestoes_iniciais(self, sugestoes: list) -> None:
        for sg in sugestoes:
            self.sugestoes[sg["id"]] = {**sg, "estado": "PENDENTE"}
            self._inicio_pendente.append(("SUGESTAO", {**{k: v for k, v in sg.items() if k != "id"},
                                                       "sugestao": sg["id"], "estado": "PENDENTE"}))

    def registrar_inicio(self, t: float) -> None:
        for tipo, campos in self._inicio_pendente:
            self.reg.add(PLATAFORMA, tipo, t, **campos)
        self._inicio_pendente = []

    def app_sugestoes(self, t: float, ids: list, aceitar: bool) -> None:
        """APP_ACEITAR / APP_RECUSAR: decisão do titular sobre sugestões pendentes."""
        self.reg.add(PLATAFORMA, "APP_SUGESTOES", t, sugestoes=ids, decisao="ACEITAR" if aceitar else "RECUSAR")
        if self.fora:
            self._mostrar_cfg(t, None, "REJEITADA", "PLATAFORMA_INDISPONIVEL")
            return
        self.agendar(t + _lat(self.rng, self.p_app["latencia_ms"]), lambda tt: self._decidir(tt, ids, aceitar))

    def _decidir(self, t: float, ids: list, aceitar: bool) -> None:
        lo, hi = self.p["t_apagamento_limites_ms"]
        aceitas = []
        for sid in ids:
            sg = self.sugestoes.get(sid)
            if sg is None or sg["estado"] != "PENDENTE":
                self.reg.add(PLATAFORMA, "SUGESTAO", t, sugestao=sid, estado="SEM_EFEITO",
                             motivo="DESCONHECIDA" if sg is None else sg["estado"])
                continue
            if aceitar and not lo <= sg["t_apagamento_ms"] <= hi:
                sg["estado"] = "REJEITADA"
                self.reg.add(PLATAFORMA, "SUGESTAO", t, sugestao=sid, estado="REJEITADA", motivo="FORA_DA_POLITICA",
                             limites_ms=[lo, hi])
                continue
            sg["estado"] = "ACEITA" if aceitar else "RECUSADA"
            self.reg.add(PLATAFORMA, "SUGESTAO", t, sugestao=sid, estado=sg["estado"], comodo=sg["comodo"])
            if aceitar:
                aceitas.append(sg)
        if not aceitas:
            return
        for sg in aceitas:
            lista = [f for f in self.faixas_aceitas.get(sg["comodo"], []) if (f["de"], f["ate"]) != (sg["de"], sg["ate"])]
            lista.append({"de": sg["de"], "ate": sg["ate"], "t_apagamento_ms": sg["t_apagamento_ms"]})
            self.faixas_aceitas[sg["comodo"]] = sorted(lista, key=lambda f: f["de"])
        self._nova_versao_faixas(t, [sg["id"] for sg in aceitas])

    def _nova_versao_faixas(self, t: float, ids: list) -> None:
        self.versao_vigente += 1
        nv = self.versao_vigente
        for antiga, cfg in self.versoes.items():
            if cfg["estado"] == "PENDENTE":
                cfg["estado"] = "SUBSTITUIDA"
                self.reg.add(PLATAFORMA, "CONFIG_VERSAO", t, versao=antiga, estado="SUBSTITUIDA")
        par = {"faixas": {cid: [dict(f) for f in fs] for cid, fs in self.faixas_aceitas.items()}, "sugestoes": ids}
        self.versoes[nv] = {"parametros": par, "estado": "PENDENTE", "criada_ms": t, "sugestoes": ids}
        self.reg.add(PLATAFORMA, "CONFIG_VERSAO", t, versao=nv, estado="PENDENTE", parametros=par, origem="ACEITE",
                     sugestoes=ids, aplicada_hub=self.versao_aplicada_hub)
        self._mostrar_cfg(t, nv, "PENDENTE", None)
        if self.sessao:
            self._enviar_config(t, nv)

    # ================================================================= app
    def app_consulta(self, t: float) -> None:
        if self.fora:
            self.reg.add(PLATAFORMA, "APP_CONSULTA", t, disponivel=False)
            return
        self._atualizar(t)
        v = self.versoes[self.versao_vigente]
        por_comodo = {cid: {"ocupacao": (rc.estado or {}).get("ocupacao"), "luz": (rc.estado or {}).get("luz"),
                            "atualidade": rc.atualidade, "idade_ms": self._idade(t, cid)}
                      for cid, rc in self.r.items()}
        # Os campos do topo são os do primeiro cômodo (compatibilidade com a v0dt)
        self.reg.add(PLATAFORMA, "APP_CONSULTA", t, disponivel=True, **por_comodo[self.comodos[0]],
                     conexao="CONECTADO" if self.sessao else "DESCONECTADO",
                     config_versao=self.versao_vigente, config_estado=v["estado"], comodos=por_comodo)

    def balanco(self) -> dict:
        return {"recebidas_unicas": len(self.recebidas), "duplicadas_descartadas": self.duplicadas,
                "historico_sem_efeito_no_estado": self.historico_fora_de_ordem,
                "versao_vigente": self.versao_vigente, "versao_aplicada_hub": self.versao_aplicada_hub,
                "versoes": {str(k): v["estado"] for k, v in self.versoes.items()}}
