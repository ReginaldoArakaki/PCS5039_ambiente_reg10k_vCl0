"""Mundo simulado: os ocupantes e seu movimento (camada de verdade, plano §4).

v1dt: o ocupante tem um cômodo e pode mudar de cômodo por uma passagem
interna (modo PASSANDO). A geometria dos cômodos está em sim/residencia.py;
a classe Sala abaixo fica só por compatibilidade com código de alunos.
"""
from __future__ import annotations

import math
import random
from typing import Optional

PESSOA = "PESSOA"
CACHORRO = "CACHORRO"

PONTO_ENTRADA = (0.95, 0.4)
# nucleo-v1.3: perfis de pessoa (só o movimento muda; os sensores não distinguem perfis, RN09).
# (velocidade de ANDAR, velocidade de ANDAR_ALEATORIO), em m/s
PERFIS = {"ADULTO": (1.0, 0.8), "CRIANCA": (1.2, 1.0), "IDOSO": (0.6, 0.5)}
# Dormindo: microgestos raros (a cada 10 a 25 min)
MICRO_DORMINDO = (600_000, 1_500_000)


class Ocupante:
    def __init__(self, id_: str, tipo: str, perfil: str = "ADULTO", visitante: bool = False):
        self.id = id_
        self.tipo = tipo
        self.perfil = perfil if perfil in PERFIS else "ADULTO"  # nucleo-v1.3
        self.visitante = visitante                               # nucleo-v1.3: ocupante sem papel no app
        self.dormindo = False                                    # nucleo-v1.3: PI-01
        self.lendo = False                                       # nucleo-v1.4: parado e acordado; reage ao escuro
        self.reacao_ms: Optional[int] = None                     # nucleo-v1.4: instante do gesto de reação
        self.pos: Optional[tuple[float, float]] = None  # None = exterior
        self.comodo: Optional[str] = None  # v1dt: cômodo atual (None = exterior)
        self.chegou_passagem = False       # v1dt: chegou ao vão e vai cruzar neste passo
        self.destino = None                # v1dt: (passagem, cômodo de destino, alvo)
        self.modo = "FORA"  # FORA, PARADO, ANDAR, ALEATORIO, MICRO
        self.alvo: Optional[tuple[float, float]] = None
        self.vel = 1.0
        self.area: Optional[tuple[float, float, float, float]] = None
        self.fim_ms: Optional[int] = None
        self.gesto_ate = 0
        self.micro_intervalo = (120_000, 240_000)
        self.micro_prox: Optional[int] = None
        # Situação no passo atual
        self.movendo = False
        self.microgesto = False

    @property
    def na_sala(self) -> bool:
        return self.pos is not None


class Sala:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.largura = cfg["largura_m"]
        self.profundidade = cfg["profundidade_m"]
        self.zonas_cegas = cfg.get("zonas_cegas", [])
        sp = cfg["dispositivos"]["SP-01"]
        self.sp_pos = (sp["x"], sp["y"])
        self.sp_alcance = sp["alcance_m"]

    def na_zona_cega(self, p: tuple[float, float]) -> bool:
        return any(z["x0"] <= p[0] <= z["x1"] and z["y0"] <= p[1] <= z["y1"] for z in self.zonas_cegas)

    def coberto_pelo_sp(self, p: Optional[tuple[float, float]]) -> bool:
        if p is None or self.na_zona_cega(p):
            return False
        return math.dist(p, self.sp_pos) <= self.sp_alcance

    def ponto_aleatorio(self, rng: random.Random, area=None) -> tuple[float, float]:
        m = 0.3
        x0, y0, x1, y1 = area if area else (m, m, self.largura - m, self.profundidade - m)
        return (round(rng.uniform(x0, x1), 3), round(rng.uniform(y0, y1), 3))


def mover(o: Ocupante, sala, t: int, dt_ms: int, rng: random.Random) -> None:
    """Avança o ocupante um passo de simulação.

    `sala` é o cômodo atual do ocupante (sim.residencia.Comodo), ou a Sala da v0.
    """
    o.movendo = False
    o.microgesto = False
    if o.pos is None:
        return
    if t < o.gesto_ate:
        o.movendo = True
    if o.modo == "ALEATORIO" and o.fim_ms is not None and t >= o.fim_ms:
        o.modo, o.alvo = "PARADO", None
    if o.modo in ("ANDAR", "ALEATORIO", "PASSANDO") and o.alvo is not None:
        dx, dy = o.alvo[0] - o.pos[0], o.alvo[1] - o.pos[1]
        dist = math.hypot(dx, dy)
        passo = o.vel * dt_ms / 1000
        o.movendo = True
        if dist <= passo:
            o.pos = o.alvo
            if o.modo == "PASSANDO":
                o.chegou_passagem = True
            elif o.modo == "ANDAR":
                o.modo, o.alvo = "PARADO", None
            else:
                o.alvo = sala.ponto_aleatorio(rng, o.area)
        else:
            o.pos = (o.pos[0] + dx / dist * passo, o.pos[1] + dy / dist * passo)
    if o.modo == "MICRO" and o.micro_prox is not None and t >= o.micro_prox:
        o.microgesto = True
        o.micro_prox = t + rng.randint(*o.micro_intervalo)
