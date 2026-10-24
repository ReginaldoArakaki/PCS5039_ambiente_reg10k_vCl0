"""Canal simulado entre o hub e a plataforma (plano v0dt §6.1).

O canal tem dois sentidos: SOBE (hub → plataforma) e DESCE (plataforma → hub).
Cada mensagem sofre latência e pode ser perdida ou duplicada. A entrega é
"pelo menos uma vez": quem envia reenvia o que não foi confirmado, por isso
a duplicação é tratada por número de sequência (SOBE) e por chave de
idempotência (DESCE).

O enlace pode cair (falha CANAL_DESCONECTA). Mensagens em trânsito quando o
enlace cai são perdidas. Quem usa o canal é avisado da queda pelo motor.
"""
from __future__ import annotations

import random
from typing import Callable

from sim.modelos import REDE

SOBE = "SOBE"
DESCE = "DESCE"


class Canal:
    def __init__(self, p: dict, rng: random.Random, agendar: Callable, reg):
        self.p = p
        self.rng = rng
        self.agendar = agendar
        self.reg = reg
        self.enlace = True
        self.latencia_extra = {SOBE: 0, DESCE: 0}
        self.duplicar = {SOBE: set(), DESCE: set()}  # tipos de mensagem a duplicar uma vez
        self.perder = {SOBE: set(), DESCE: set()}
        self.contagem = {"enviadas": 0, "perdidas": 0, "duplicadas": 0, "entregues": 0}

    def _latencia(self, sentido: str) -> float:
        a, b = self.p["latencia_ms"]
        base = a if a == b else self.rng.uniform(a, b)
        return base + self.latencia_extra[sentido]

    def enviar(self, t: float, sentido: str, msg: dict, entregar: Callable[[float, dict], None]) -> None:
        self.contagem["enviadas"] += 1
        tipo = msg["tipo"]
        if not self.enlace:
            self._perdida(t, sentido, msg, "ENLACE_FORA")
            return
        if tipo in self.perder[sentido]:
            self.perder[sentido].discard(tipo)
            self._perdida(t, sentido, msg, "INJETADA")
            return
        if self.p.get("p_perda", 0) and self.rng.random() < self.p["p_perda"]:
            self._perdida(t, sentido, msg, "ALEATORIA")
            return
        copias = 1
        if tipo in self.duplicar[sentido]:
            self.duplicar[sentido].discard(tipo)
            copias = 2
        elif self.p.get("p_duplicacao", 0) and self.rng.random() < self.p["p_duplicacao"]:
            copias = 2
        if copias == 2:
            self.contagem["duplicadas"] += 1
            self.reg.add(REDE, "MSG_DUPLICADA", t, sentido=sentido, mensagem=tipo, **_ident(msg))
        for _ in range(copias):
            self.agendar(t + self._latencia(sentido), lambda tt, m=dict(msg): self._entregar(tt, sentido, m, entregar))

    def _entregar(self, t: float, sentido: str, msg: dict, entregar) -> None:
        if not self.enlace:
            self._perdida(t, sentido, msg, "ENLACE_FORA")
            return
        self.contagem["entregues"] += 1
        entregar(t, msg)

    def _perdida(self, t: float, sentido: str, msg: dict, motivo: str) -> None:
        self.contagem["perdidas"] += 1
        self.reg.add(REDE, "MSG_PERDIDA", t, sentido=sentido, mensagem=msg["tipo"], motivo=motivo, **_ident(msg))


def _ident(msg: dict) -> dict:
    """Campos que identificam a mensagem no registro."""
    return {k: msg[k] for k in ("n", "chave", "versao") if k in msg}
