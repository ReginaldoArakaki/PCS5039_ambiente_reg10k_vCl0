"""Agente de sincronização do hub e DTReg10k-L (plano v0dt §4 e §5).

O DTReg10k-L é o que o hub sabe da sala: o registro local (autoridade sobre
evidências, decisões e resultados, RN27), o estado inferido pelo controlador
e a versão de configuração aplicada. O agente o publica na plataforma:

- RN-DT-02: publica cada evento relevante com número de sequência `n` e um
  resumo de estado a cada 30 s; sem sessão, tudo fica na fila persistente.
- RN-DT-03: na reconexão envia primeiro o estado atual (resumo) e depois o
  histórico em ordem de `n`. O histórico nunca restabelece a atualidade.
- RN-DT-05: comando remoto vencido ou repetido é recusado; o válido vira
  evidência COMANDO_REMOTO para o controlador.
- RN-DT-07: nunca aplica versão de configuração menor ou igual à aplicada.

A fila, os comandos já vistos e a versão aplicada sobrevivem ao reinício do
hub (persistência local).
"""
from __future__ import annotations

import random
from collections import OrderedDict
from typing import Optional

from plataforma.canal import SOBE
from sim.modelos import (
    ATUACAO, DECISAO, ESTADO, EXPIRADA, PERCEPCAO, REDE, REJEITADA, SISTEMA,
)

PUBLICAR = {
    PERCEPCAO: {"PASSAGEM", "MOVIMENTO", "FIM_MOVIMENTO", "INTERRUPTOR", "LEITURA_LAMPADA",
                "COMANDO_REMOTO", "CONFIGURACAO"},
    DECISAO: {"INTENCAO"},
    ATUACAO: {"RESULTADO"},
    ESTADO: {"ESTADO_SALA"},
    SISTEMA: {"ALERTA", "LACUNA", "HUB_LIGADO", "HUB_DESLIGADO", "CONFIG_APLICADA", "RELOGIO_SALTO"},
}
_OMITIR = {"id", "camada", "tipo", "mudanca", "relogio_hub_ms", "relogio_confiavel", "seq", "t_ms"}


class AgenteSincronizacao:
    def __init__(self, hub, reg, canal, p: dict, rng: random.Random, plataforma):
        self.hub = hub
        self.reg = reg
        self.canal = canal
        self.p = p
        self.rng = rng
        self.plataforma = plataforma
        self.ligado = True
        self.sessao = False
        # persistente
        self.n = 0
        self.fila: "OrderedDict[int, dict]" = OrderedDict()  # publicadas e ainda não confirmadas
        self.enviada_em: dict[int, float] = {}
        self.comandos_vistos: dict[str, Optional[str]] = {}
        self.versao_aplicada = 0
        self.publicadas = 0
        self.fila_max = 0
        # reconexão
        self.espera_ms = p["reconexao_min_ms"]
        self.proxima_tentativa: Optional[float] = 0
        self.proximo_resumo = 0
        reg.ouvintes.append(self._ouvir)

    # ------------------------------------------------------------ publicação
    def _ouvir(self, ev: dict) -> None:
        tipos = PUBLICAR.get(ev["camada"])
        if not tipos or ev["tipo"] not in tipos:
            return
        if ev["camada"] == ESTADO and not ev.get("mudanca"):
            return
        corpo = {k: v for k, v in ev.items() if k not in _OMITIR}
        self._publicar(ev["t_ms"], {"tipo": "EVENTO", "camada": ev["camada"], "evento": ev["tipo"],
                                    "ref_seq": ev["seq"], "t_origem": ev["t_ms"],
                                    "relogio_hub_ms": ev.get("relogio_hub_ms"),
                                    "relogio_confiavel": ev.get("relogio_confiavel", True), "dados": corpo})

    def _publicar(self, t: float, msg: dict, enfileirar: bool = True) -> None:
        self.n += 1
        msg = {**msg, "n": self.n}
        self.publicadas += 1
        if enfileirar:
            self.fila[self.n] = msg
            self.fila_max = max(self.fila_max, len(self.fila))
        if self.sessao and self.ligado:
            self._enviar(t, msg)

    def _enviar(self, t: float, msg: dict) -> None:
        self.enviada_em[msg["n"]] = t
        self.canal.enviar(t, SOBE, msg, self.plataforma.receber)

    def _resumo(self, t: float, reconexao: bool = False) -> None:
        e = self.hub.ctrl.estado() if self.hub.ctrl else None
        estado = None if e is None else {
            "ocupacao": e.ocupacao, "luz": e.luz, "precedencia": e.precedencia,
            "idade_evidencia_ms": e.idade_evidencia_ms, "alertas": list(e.alertas)}
        # O resumo não entra na fila: perdido, o próximo o substitui
        self._publicar(t, {"tipo": "RESUMO", "ref_seq": self.reg._seq, "t_origem": int(t), "estado": estado,
                           "versao_config": self.versao_aplicada, "reconexao": reconexao,
                           "fila": len(self.fila)}, enfileirar=False)
        self.proximo_resumo = t + self.p["resumo_ms"]

    # --------------------------------------------------------------- sessão
    def sessao_caiu(self, t: float, motivo: str) -> None:
        if not self.sessao:
            return
        self.sessao = False
        self.reg.add(REDE, "SESSAO_CAIU", t, motivo=motivo, fila=len(self.fila))
        self.espera_ms = self.p["reconexao_min_ms"]
        self.proxima_tentativa = t + self._espera()

    def _espera(self) -> float:
        j = self.p.get("reconexao_jitter", 0)
        e = self.espera_ms * (1 + (self.rng.uniform(-j, j) if j else 0))
        self.espera_ms = min(self.espera_ms * 2, self.p["reconexao_max_ms"])
        return e

    def _tentar(self, t: float) -> None:
        if self.canal.enlace and not self.plataforma.fora:
            self.sessao = True
            self.proxima_tentativa = None
            self.reg.add(REDE, "SESSAO_ESTABELECIDA", t, fila=len(self.fila))
            self.plataforma.sessao_estabelecida(t)
            # RN-DT-03: estado atual primeiro, depois o histórico em ordem
            self._resumo(t, reconexao=True)
            for n, msg in list(self.fila.items()):
                self._enviar(t, msg)
        else:
            self.proxima_tentativa = t + self._espera()

    def confirmar(self, t: float, n: int) -> None:
        self.fila.pop(n, None)
        self.enviada_em.pop(n, None)

    # ------------------------------------------------------------ ciclo de vida
    def desligar(self, t: float) -> None:
        if self.sessao:
            self.sessao = False
            self.reg.add(REDE, "SESSAO_CAIU", t, motivo="HUB_DESLIGADO", fila=len(self.fila))
            self.plataforma.sessao_caiu(t, "HUB_DESLIGADO")
        self.ligado = False
        self.proxima_tentativa = None

    def ligar(self, t: float) -> None:
        self.ligado = True
        self.espera_ms = self.p["reconexao_min_ms"]
        self.proxima_tentativa = t + self._espera()

    def tick(self, t: float) -> None:
        if not self.ligado:
            return
        if not self.sessao:
            if self.proxima_tentativa is not None and t >= self.proxima_tentativa:
                self._tentar(t)
            return
        if t >= self.proximo_resumo:
            self._resumo(t)
        reenvio = self.p["reenvio_ms"]
        for n, msg in list(self.fila.items()):
            if t - self.enviada_em.get(n, t) >= reenvio:
                self._enviar(t, msg)

    # --------------------------------------------------------- plataforma → hub
    def receber(self, t: float, msg: dict) -> None:
        if not self.ligado or not self.sessao:
            return
        tipo = msg["tipo"]
        if tipo == "ACK":
            self.confirmar(t, msg["n"])
        elif tipo == "COMANDO":
            self._comando(t, msg)
        elif tipo == "CONFIG":
            self._config(t, msg)

    def _responder(self, t: float, msg: dict) -> None:
        if self.sessao:
            self.canal.enviar(t, SOBE, msg, self.plataforma.receber)

    def _comando(self, t: float, msg: dict) -> None:
        chave = msg["chave"]
        self._responder(t, {"tipo": "ACK_COMANDO", "chave": chave})
        if chave in self.comandos_vistos:
            self.reg.add(SISTEMA, "COMANDO_REMOTO_RECEBIDO", t, chave=chave, acao=msg["acao"],
                         valida_ate_ms=msg["valida_ate_ms"], decisao="REPETIDO")
            return
        if t > msg["valida_ate_ms"]:
            self.comandos_vistos[chave] = EXPIRADA
            self.reg.add(SISTEMA, "COMANDO_REMOTO_RECEBIDO", t, chave=chave, acao=msg["acao"],
                         valida_ate_ms=msg["valida_ate_ms"], decisao="EXPIRADO")
            self.resultado_comando(t, chave, EXPIRADA, motivo="VALIDADE_VENCIDA")
            return
        self.comandos_vistos[chave] = None
        self.reg.add(SISTEMA, "COMANDO_REMOTO_RECEBIDO", t, chave=chave, acao=msg["acao"],
                     valida_ate_ms=msg["valida_ate_ms"], decisao="ACEITO")
        motivo = self.hub.comando_remoto(int(t), chave, msg["acao"], msg.get("solicitante", "titular"))
        if motivo:
            self.resultado_comando(t, chave, REJEITADA, motivo=motivo)

    def resultado_comando(self, t: float, chave: str, nivel: str, motivo: Optional[str] = None) -> None:
        self.comandos_vistos[chave] = nivel
        corpo = {"tipo": "RESULTADO_COMANDO", "chave": chave, "nivel": nivel, "t_origem": int(t)}
        if motivo:
            corpo["motivo"] = motivo
        self._publicar(t, corpo)

    def _config(self, t: float, msg: dict) -> None:
        v = msg["versao"]
        if v <= self.versao_aplicada:
            self.reg.add(SISTEMA, "CONFIG_RECUSADA", t, versao=v, aplicada=self.versao_aplicada)
            self._publicar(t, {"tipo": "RESULTADO_CONFIG", "versao": v, "estado": "RECUSADA",
                               "aplicada": self.versao_aplicada})
            return
        self.versao_aplicada = v
        self.hub.aplicar_config(int(t), v, msg["parametros"])
        self._publicar(t, {"tipo": "RESULTADO_CONFIG", "versao": v, "estado": "APLICADA", "aplicada": v})

    # ------------------------------------------------------------------ resumo
    def balanco(self) -> dict:
        return {"publicadas": self.publicadas, "pendentes_na_fila": len(self.fila), "fila_max": self.fila_max,
                "versao_config_aplicada": self.versao_aplicada}
