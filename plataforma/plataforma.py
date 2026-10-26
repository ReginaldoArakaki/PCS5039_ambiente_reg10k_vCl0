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


class Plataforma:
    def __init__(self, reg, canal, p: dict, p_app: dict, rng: random.Random, agendar, config_inicial: ConfigSala):
        self.reg = reg
        self.canal = canal
        self.p = p
        self.p_app = p_app
        self.rng = rng
        self.agendar = agendar
        self.agente = None
        self.fora = False
        self.sessao = False
        # DTReg10k-R
        self.estado: Optional[dict] = None
        self.n_aplicado = 0
        self.recepcao_estado: Optional[float] = None
        self.ultima_evidencia: Optional[float] = None
        self.atualidade = SEM_EVIDENCIA
        self.aguarda_estado = True   # após queda da sessão, só um estado novo restabelece a atualidade
        self.recebidas: set[int] = set()
        self.duplicadas = 0
        self.historico_fora_de_ordem = 0
        self._ultimo_log = None
        # comandos
        self.n_cmd = 0
        self.comandos: dict[str, dict] = {}
        # configuração
        self.versao_vigente = 1
        self.versoes = {1: {"parametros": {"t_apagamento_ms": config_inicial.t_apagamento_ms},
                            "estado": "APLICADA", "criada_ms": 0}}
        self.versao_aplicada_hub = 1

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
        self.aguarda_estado = True
        self._atualizar(t)

    def cair(self, t: float) -> None:
        """Falha PLATAFORMA_FORA: a plataforma para; o estado persistido fica."""
        self.reg.add(REDE, "PLATAFORMA_FORA", t)
        self.sessao = False
        self.aguarda_estado = True
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
            if msg.get("estado") is not None:
                self._aplicar_estado(t, n, msg["estado"], msg["ref_seq"], "RESUMO", msg.get("reconexao", False))
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
            estado = {k: d.get(k) for k in ("ocupacao", "luz", "precedencia", "idade_evidencia_ms", "alertas")}
            self._aplicar_estado(t, n, estado, msg["ref_seq"], "EVENTO", False)
        elif msg["camada"] == "PERCEPCAO":
            if msg["evento"] in ("PASSAGEM", "MOVIMENTO", "INTERRUPTOR"):
                self.ultima_evidencia = max(self.ultima_evidencia or 0, t)
            if msg["evento"] in ("PASSAGEM", "MOVIMENTO", "FIM_MOVIMENTO", "INTERRUPTOR"):
                # v0dta: o espelho mostra o sinal quando ele CHEGA à plataforma
                self.reg.add(PLATAFORMA, "EVIDENCIA_RECEBIDA", t, origem=d.get("origem"), evidencia=msg["evento"],
                             t_origem_ms=msg["t_origem"], atraso_ms=int(t - msg["t_origem"]),
                             historico=n < self.n_aplicado)
        elif msg["camada"] == "ATUACAO" and msg["evento"] == "RESULTADO":
            self.reg.add(PLATAFORMA, "RESULTADO_RECEBIDO", t, chave=d.get("chave"), acao=d.get("acao"),
                         nivel=d.get("nivel"), t_origem_ms=msg["t_origem"], historico=n < self.n_aplicado)

    def _aplicar_estado(self, t: float, n: int, estado: dict, ref_seq: int, origem: str, reconexao: bool) -> None:
        if n <= self.n_aplicado:
            # OR-09: histórico ou mensagem atrasada não substitui estado mais recente
            self.historico_fora_de_ordem += 1
            return
        anterior = self.estado
        if reconexao and anterior is not None:
            for k in ("ocupacao", "luz"):
                if anterior.get(k) != estado.get(k):
                    # RF-SYN-05: divergência resolvida pela autoridade do hub (RN27)
                    self.reg.add(PLATAFORMA, "DIVERGENCIA", t, atributo=k, valor_remoto=anterior.get(k),
                                 valor_local=estado.get(k), autoridade="DTReg10k-L", resolucao="ADOTA_LOCAL")
        self.estado = dict(estado)
        self.n_aplicado = n
        self.recepcao_estado = t
        self.aguarda_estado = False
        self._atualizar(t, ref_seq=ref_seq, origem=origem, forcar=(origem == "RESUMO"))

    # =========================================================== atualidade
    def _idade(self, t: float) -> Optional[int]:
        return None if self.recepcao_estado is None else int(t - self.recepcao_estado)

    def _atualizar(self, t: float, ref_seq: Optional[int] = None, origem: Optional[str] = None,
                   forcar: bool = False) -> None:
        if self.fora:
            return
        idade = self._idade(t)
        if self.estado is None:
            atual = SEM_EVIDENCIA
        elif self.sessao and not self.aguarda_estado and idade is not None \
                and idade <= self.p["limite_atualidade_ms"]:
            atual = ATUAL
        else:
            atual = DESATUALIZADO
        self.atualidade = atual
        e = self.estado or {}
        chave = (e.get("ocupacao"), e.get("luz"), e.get("precedencia"), tuple(e.get("alertas") or ()),
                 atual, self.sessao)
        # Registra quando algo muda e a cada resumo recebido (para a idade exibida)
        if chave != self._ultimo_log or forcar:
            campos = {"ocupacao": e.get("ocupacao"), "luz": e.get("luz"), "precedencia": e.get("precedencia"),
                      "alertas": list(e.get("alertas") or []), "atualidade": atual,
                      "conexao": "CONECTADO" if self.sessao else "DESCONECTADO",
                      "recepcao_ms": None if self.recepcao_estado is None else int(self.recepcao_estado),
                      "mudanca": chave != self._ultimo_log}
            if ref_seq is not None:
                campos.update(ref_seq=ref_seq, origem=origem, n=self.n_aplicado)
            self.reg.add(PLATAFORMA, "ESTADO_REMOTO", t, **campos)
            self._ultimo_log = chave

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
    def app_comando(self, t: float, acao: str) -> None:
        self.n_cmd += 1
        chave = f"CMD-{self.n_cmd:03d}"
        self.reg.add(PLATAFORMA, "APP_COMANDO", t, chave=chave, acao=acao)
        if self.fora:
            self._mostrar(t + _lat(self.rng, self.p_app["latencia_ms"]), chave, REJEITADA,
                          "PLATAFORMA_INDISPONIVEL", True, t)
            return
        self.agendar(t + _lat(self.rng, self.p_app["latencia_ms"]), lambda tt: self._criar_comando(tt, chave, acao, t))

    def _criar_comando(self, t: float, chave: str, acao: str, t_app: float) -> None:
        if self.fora:
            self._mostrar(t, chave, REJEITADA, "PLATAFORMA_INDISPONIVEL", True, t_app)
            return
        if not self.sessao:
            # RN-DT-06: recusa imediata, com a última evidência e a idade; nada fica pendente
            idade = self._idade(t)
            self.reg.add(PLATAFORMA, "COMANDO_RECUSADO", t, chave=chave, acao=acao, motivo="HUB_DESCONECTADO",
                         ultima_evidencia_ms=None if self.ultima_evidencia is None else int(self.ultima_evidencia),
                         idade_estado_ms=idade)
            self.comandos[chave] = {"chave": chave, "acao": acao, "t_app": t_app, "criado_ms": t,
                                    "valida_ate_ms": t, "final": True, "provisorio": True, "ack": True,
                                    "enviado_ms": t}
            self._ao_app(t, chave, REJEITADA, "HUB_DESCONECTADO", final=True)
            return
        valida = int(t + self.p["validade_comando_ms"])
        c = {"chave": chave, "acao": acao, "t_app": t_app, "criado_ms": t, "valida_ate_ms": valida,
             "final": False, "provisorio": False, "ack": False, "enviado_ms": t}
        self.comandos[chave] = c
        self.reg.add(PLATAFORMA, "COMANDO_CRIADO", t, chave=chave, acao=acao, valida_ate_ms=valida,
                     solicitante="titular")
        self._enviar_comando(t, c)

    def _enviar_comando(self, t: float, c: dict) -> None:
        c["enviado_ms"] = t
        self.canal.enviar(t, DESCE, {"tipo": "COMANDO", "chave": c["chave"], "acao": c["acao"],
                                     "valida_ate_ms": c["valida_ate_ms"], "solicitante": "titular"},
                          self.agente.receber)

    def _resultado_comando(self, t: float, msg: dict) -> None:
        c = self.comandos.get(msg["chave"])
        if c is None:
            return
        c["ack"] = True
        self.reg.add(PLATAFORMA, "COMANDO_RESULTADO", t, chave=msg["chave"], nivel=msg["nivel"],
                     motivo=msg.get("motivo"))
        if not c["final"]:
            c["final"] = True
            self._ao_app(t, msg["chave"], msg["nivel"], msg.get("motivo"), final=True)

    def _ao_app(self, t: float, chave: str, nivel: str, motivo: Optional[str], final: bool) -> None:
        c = self.comandos[chave]
        self._mostrar(t + _lat(self.rng, self.p_app["latencia_ms"]), chave, nivel, motivo, final, c["t_app"])

    def _mostrar(self, t: float, chave: str, nivel: str, motivo, final: bool, t_app: float) -> None:
        def registrar(tt):
            self.reg.add(PLATAFORMA, "APP_RESULTADO", tt, chave=chave, nivel=nivel, motivo=motivo, final=final,
                         latencia_ms=int(tt - t_app))
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

    # ================================================================= app
    def app_consulta(self, t: float) -> None:
        if self.fora:
            self.reg.add(PLATAFORMA, "APP_CONSULTA", t, disponivel=False)
            return
        self._atualizar(t)
        e = self.estado or {}
        v = self.versoes[self.versao_vigente]
        self.reg.add(PLATAFORMA, "APP_CONSULTA", t, disponivel=True, ocupacao=e.get("ocupacao"), luz=e.get("luz"),
                     atualidade=self.atualidade, idade_ms=self._idade(t),
                     conexao="CONECTADO" if self.sessao else "DESCONECTADO",
                     config_versao=self.versao_vigente, config_estado=v["estado"])

    def balanco(self) -> dict:
        return {"recebidas_unicas": len(self.recebidas), "duplicadas_descartadas": self.duplicadas,
                "historico_sem_efeito_no_estado": self.historico_fora_de_ordem,
                "versao_vigente": self.versao_vigente, "versao_aplicada_hub": self.versao_aplicada_hub,
                "versoes": {str(k): v["estado"] for k, v in self.versoes.items()}}
