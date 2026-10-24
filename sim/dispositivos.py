"""Dispositivos simulados (plano §4.3): SA, SP (PIR), atuador, lâmpada e interruptor.

Cada dispositivo tem parâmetros para o modo IDEAL e o modo REALISTA, lidos de
cenarios/sala.json. A emissão de evidências é feita pela função `emitir`,
que agenda a entrega ao hub no instante em que o dispositivo a envia.
"""
from __future__ import annotations

import random
from typing import Callable

from sim.mundo import CACHORRO

Emitir = Callable[[float, str, str, dict], None]


def _lat(rng: random.Random, faixa) -> float:
    a, b = faixa
    return a if a == b else rng.uniform(a, b)


class SensorPassagem:
    """SA no batente: detecta cruzamento, sem direção (RN09)."""

    origem = "SA-01"

    def __init__(self, p: dict, rng: random.Random, emitir: Emitir):
        self.p, self.rng, self.emitir = p, rng, emitir
        self.rearme_ate = -1
        self.perder_proxima = False

    def estimulo(self, t: int, vel: float) -> None:
        if self.perder_proxima:
            self.perder_proxima = False
            return
        if t < self.rearme_ate:
            return
        prob = self.p["p_deteccao_rapida"] if vel > 2.0 else self.p["p_deteccao"]
        if self.rng.random() < prob:
            self.emitir(t + _lat(self.rng, self.p["latencia_ms"]), self.origem, "PASSAGEM", {})
            self.rearme_ate = t + self.p["rearme_ms"]

    def espurio(self, t: int) -> None:
        self.emitir(t + _lat(self.rng, self.p["latencia_ms"]), self.origem, "PASSAGEM", {})
        self.rearme_ate = t + self.p["rearme_ms"]

    def passo(self, t: int, dt_ms: int) -> None:
        taxa = self.p.get("espurio_por_hora", 0)
        if taxa and self.rng.random() < taxa * dt_ms / 3_600_000:
            self.espurio(t)


class SensorPresencaPIR:
    """SP: PIR com zona cega, retenção, latência, heartbeat e bateria."""

    origem = "SP-01"

    def __init__(self, p: dict, rng: random.Random, emitir: Emitir):
        self.p, self.rng, self.emitir = p, rng, emitir
        self.alto = False
        self.alto_ate = 0.0
        self.bateria = 100
        self.sem_resposta = False
        self.forcar_disparo = False

    def _disparar(self, t: int) -> None:
        t_emit = t + _lat(self.rng, self.p["latencia_ms"])
        if not self.alto:
            self.alto = True
            self.emitir(t_emit, self.origem, "MOVIMENTO", {})
        self.alto_ate = max(self.alto_ate, t_emit + self.p["retencao_ms"])

    def janela(self, t: int, leituras: list[dict]) -> None:
        """Avalia a janela de 1 s que termina em t.

        `leituras`: por ocupante, se esteve coberto movendo-se, com microgesto
        ou parado durante a janela.
        """
        if self.sem_resposta:
            return
        fator_bat = self.p["fator_bateria_baixa"] if self.bateria < 15 else 1.0
        det = self.forcar_disparo
        self.forcar_disparo = False
        for l in leituras:
            f = (self.p["fator_cachorro"] if l["tipo"] == CACHORRO else 1.0) * fator_bat
            if l["movendo"]:
                prob = self.p["p_movimento"] * f
            elif l["microgesto"]:
                prob = self.p["p_microgesto"] * f
            elif l["parado"]:
                prob = self.p["p_parado"] * f
            else:
                continue
            if self.rng.random() < prob:
                det = True
        taxa = self.p.get("falso_disparo_por_hora", 0)
        if not det and taxa and self.rng.random() < taxa / 3600:
            det = True
        if det:
            self._disparar(t)

    def passo(self, t: int) -> None:
        if self.sem_resposta:
            return
        if self.alto and t >= self.alto_ate:
            self.alto = False
            self.emitir(self.alto_ate, self.origem, "FIM_MOVIMENTO", {})
        if t > 0 and t % self.p["heartbeat_ms"] == 0:
            self.emitir(t, self.origem, "HEARTBEAT", {"bateria": self.bateria, "alto": self.alto})


class Lampada:
    origem = "LAMP-01"

    def __init__(self, p: dict, rng: random.Random, emitir: Emitir, agendar, registrar_verdade):
        self.p, self.rng, self.emitir, self.agendar = p, rng, emitir, agendar
        self.registrar_verdade = registrar_verdade
        self.fisica = False  # emite luz de fato?
        self.queimada = False

    def rele_mudou(self, t: float, ligado: bool) -> None:
        if self.queimada:
            return
        t_ef = t + _lat(self.rng, self.p["latencia_ms"])
        self.agendar(t_ef, lambda tt: self._aplicar(tt, ligado))

    def _aplicar(self, t: float, ligado: bool) -> None:
        if self.queimada or self.fisica == ligado:
            return
        self.fisica = ligado
        self.registrar_verdade(t, "LUZ_FISICA", acesa=ligado)
        self.emitir(t, self.origem, "EFEITO", {"acesa": ligado})

    def queimar(self, t: float) -> None:
        self.queimada = True
        if self.fisica:
            self.fisica = False
            self.registrar_verdade(t, "LUZ_FISICA", acesa=False)
            self.emitir(t, self.origem, "EFEITO", {"acesa": False})


class Atuador:
    origem = "ATU-01"

    def __init__(self, p: dict, rng: random.Random, emitir: Emitir, agendar, registrar_atuacao, lampada: Lampada):
        self.p, self.rng, self.emitir, self.agendar = p, rng, emitir, agendar
        self.registrar_atuacao = registrar_atuacao
        self.lampada = lampada
        self.ligado = False
        self.travado = False
        self.executadas: set[str] = set()

    def comando(self, chave: str, acao: str, t: int) -> None:
        if self.travado:
            return
        self.agendar(t + _lat(self.rng, self.p["latencia_ms"]), lambda tt: self._executar(tt, chave, acao))

    def _executar(self, t: float, chave: str, acao: str) -> None:
        if self.travado:
            return
        if chave not in self.executadas:  # efeito único por chave (RF-OPR-05)
            self.executadas.add(chave)
            desejado = acao == "ACENDER"
            if self.ligado != desejado:
                self.ligado = desejado
                self.registrar_atuacao(t, chave, desejado)
                self.lampada.rele_mudou(t, desejado)
        self.emitir(t, self.origem, "CONFIRMACAO", {"chave": chave})


class Interruptor:
    origem = "INT-01"

    def __init__(self, p: dict, rng: random.Random, emitir: Emitir):
        self.p, self.rng, self.emitir = p, rng, emitir

    def acionar(self, t: int) -> None:
        self.emitir(t + _lat(self.rng, self.p["latencia_ms"]), self.origem, "INTERRUPTOR", {})
