"""Detector de presença incompatível (nucleo-v1.3; OC-03 e RF-OPR-06 da V2/V3).

Fica no hub, fora do controlador: o controlador continua acendendo como
sempre (RN-I0-02). O detector só observa as evidências e decide se uma
presença é *incompatível com a evidência anterior*:

1. **Casa vazia por inferência.** Depois de um SA na porta externa, nenhuma
   evidência de presença (movimento de SP ou passagem interna) por
   `quieta_ms` (120 s). Como o SA não diz a direção (RN09), é a quietude que
   indica que foi uma saída.
2. **Suspeita.** Com a casa vazia, uma evidência de presença **sem** SA na porta
   externa nos `explica_ms` anteriores (10 s) abre uma suspeita. É suspeita,
   nunca invasão (RN03).
3. **Conciliação.** Um SA na porta externa até `concilia_ms` (30 s) depois
   explica a presença (passagem tardia): a suspeita é conciliada e não sai do hub.
4. **Verificação** a `verifica_ms` (5 min, RN17): se houve nova evidência de
   presença depois da suspeita, ou se algum SP continua em movimento (o PIR
   avisa o início e o fim do movimento, não cada passo), ela é confirmada e vai à plataforma como evento
   de fronteira "presença não explicada"; se não houve, é descartada.

Registra na camada SISTEMA: SUSPEITA_PRESENCA com estado ABERTA, CONCILIADA,
DESCARTADA ou CONFIRMADA. Só a CONFIRMADA é publicada para a plataforma.
"""
from __future__ import annotations

from typing import Optional

from sim.modelos import SISTEMA

PARAMETROS = {"quieta_ms": 120_000, "explica_ms": 10_000, "concilia_ms": 30_000, "verifica_ms": 300_000}


class DetectorPresenca:
    def __init__(self, reg, sa_externo: str, p: Optional[dict] = None):
        self.reg = reg
        self.sa_externo = sa_externo
        self.p = {**PARAMETROS, **(p or {})}
        self.ultimo_sa_externo: Optional[float] = None
        self.ultima_presenca: Optional[float] = None
        self.vazia = False
        self.suspeita: Optional[dict] = None
        self.n = 0
        self.sp_ativo: set[str] = set()   # SPs com movimento em curso (MOVIMENTO sem FIM_MOVIMENTO)

    def _registrar(self, t: float, estado: str, **dados) -> None:
        s = self.suspeita
        self.reg.add(SISTEMA, "SUSPEITA_PRESENCA", t, suspeita=s["id"], estado=estado,
                     desde_ms=int(s["t0"]), origem=s["origem"], comodos=s["comodos"],
                     descricao="presença não explicada", **dados)

    def observar(self, t: float, origem: str, tipo: str, comodos: list[str]) -> None:
        if tipo == "PASSAGEM" and origem == self.sa_externo:
            self.ultimo_sa_externo = t
            self.vazia = False
            if self.suspeita and self.suspeita["estado"] == "ABERTA" and t - self.suspeita["t0"] <= self.p["concilia_ms"]:
                self._registrar(t, "CONCILIADA", motivo="passagem tardia pela porta externa")
                self.suspeita = None
            return
        if tipo == "FIM_MOVIMENTO":
            self.sp_ativo.discard(origem)
            return
        if tipo not in ("MOVIMENTO", "PASSAGEM"):
            return
        if tipo == "MOVIMENTO":
            self.sp_ativo.add(origem)
        self.ultima_presenca = t
        if self.suspeita:
            self.suspeita["evidencias"] += 1
            return
        explicada = self.ultimo_sa_externo is not None and t - self.ultimo_sa_externo <= self.p["explica_ms"]
        if self.vazia and not explicada:
            self.n += 1
            self.suspeita = {"id": f"SUS-{self.n:03d}", "t0": t, "origem": origem, "comodos": list(comodos),
                             "estado": "ABERTA", "evidencias": 0}
            self._registrar(t, "ABERTA")
        self.vazia = False

    def tick(self, t: float) -> None:
        # casa vazia: depois de um SA externo, quietude por quieta_ms
        if not self.vazia and self.suspeita is None and self.ultimo_sa_externo is not None:
            ref = max(self.ultimo_sa_externo, self.ultima_presenca or 0)
            if ref == self.ultimo_sa_externo and t - ref >= self.p["quieta_ms"]:
                self.vazia = True
        s = self.suspeita
        if s and t - s["t0"] >= self.p["verifica_ms"]:
            if s["evidencias"] > 0 or self.sp_ativo:
                self._registrar(t, "CONFIRMADA", evidencias=s["evidencias"], movimento_em_curso=sorted(self.sp_ativo),
                                verificacao_ms=self.p["verifica_ms"])
            else:
                self._registrar(t, "DESCARTADA", motivo="sem nova evidência na verificação")
                self.vazia = True
            self.suspeita = None
