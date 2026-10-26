"""Residência simulada: cômodos, passagens e dispositivos (plano v1dt §4 e §6).

Um arquivo de ambiente pode ter dois formatos:

- **sala** (v0, `cenarios/sala.json`): um cômodo só, com `porta`, `zonas_cegas`,
  `lampada` e `interruptor` no topo. É lido como uma residência de um cômodo
  chamado `sala`, com os mesmos identificadores (SA-01, SP-01, LAMP-01, ATU-01,
  INT-01) e os mesmos nomes de gerador aleatório de antes, para que os
  cenários antigos produzam exatamente as mesmas decisões.
- **residência** (v1dt, `cenarios/residencia-v1.json`): listas `comodos` e
  `passagens`. Uma passagem EXTERNA liga um cômodo ao exterior; uma INTERNA
  liga dois cômodos. Cada passagem tem o seu SA (A14).

As coordenadas são sempre globais, em metros.
"""
from __future__ import annotations

import math
import random
from typing import Optional

EXTERNA = "EXTERNA"
INTERNA = "INTERNA"
# Nomes de gerador aleatório da v0 (regressão por assinatura)
_RNG_LEGADO = {"SA-01": "SA", "SP-01": "SP", "LAMP-01": "LAMP", "ATU-01": "ATU", "INT-01": "INT"}


class Comodo:
    def __init__(self, c: dict, dispositivos: dict):
        self.id = c["id"]
        self.nome = c.get("nome", self.id)
        self.x0, self.y0 = c.get("x0", 0.0), c.get("y0", 0.0)
        self.largura, self.profundidade = c["largura_m"], c["profundidade_m"]
        self.zonas_cegas = c.get("zonas_cegas", [])
        self.sp, self.lampada, self.atuador, self.interruptor = c["sp"], c["lampada"]["id"], c["atuador"], c["interruptor"]["id"]
        self.lampada_pos = (c["lampada"]["x"], c["lampada"]["y"])
        self.interruptor_pos = (c["interruptor"]["x"], c["interruptor"]["y"])
        sp = dispositivos[self.sp]
        self.sp_pos, self.sp_alcance = (sp["x"], sp["y"]), sp["alcance_m"]
        self.controle = c.get("controle", {})
        self.cfg = c

    @property
    def dispositivos(self) -> tuple:
        return (self.sp, self.lampada, self.atuador, self.interruptor)

    def contem(self, p) -> bool:
        return p is not None and self.x0 <= p[0] <= self.x0 + self.largura and self.y0 <= p[1] <= self.y0 + self.profundidade

    def na_zona_cega(self, p) -> bool:
        return any(z["x0"] <= p[0] <= z["x1"] and z["y0"] <= p[1] <= z["y1"] for z in self.zonas_cegas)

    def coberto_pelo_sp(self, p) -> bool:
        """DQ1-07: cada SP cobre só o seu cômodo."""
        if p is None or self.na_zona_cega(p):
            return False
        return math.dist(p, self.sp_pos) <= self.sp_alcance

    def centro(self) -> tuple:
        return (self.x0 + self.largura / 2, self.y0 + self.profundidade / 2)

    def ponto_aleatorio(self, rng: random.Random, area=None) -> tuple:
        m = 0.3
        x0, y0, x1, y1 = area if area else (self.x0 + m, self.y0 + m, self.x0 + self.largura - m, self.y0 + self.profundidade - m)
        return (round(rng.uniform(x0, x1), 3), round(rng.uniform(y0, y1), 3))


class Passagem:
    def __init__(self, p: dict):
        self.id = p["id"]
        self.tipo = p["tipo"]
        self.comodos = list(p["comodos"])
        self.sa = p["sa"]
        self.pontos = {k: tuple(v) for k, v in p["pontos"].items()}  # ponto de cada lado, dentro do cômodo
        self.alvo = {k: tuple(v) for k, v in p.get("alvo", {}).items()}  # para onde se anda depois de entrar
        self.cfg = p

    def outro(self, comodo: str) -> Optional[str]:
        resto = [c for c in self.comodos if c != comodo]
        return resto[0] if resto else None


class Residencia:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.legado = "comodos" not in cfg
        if self.legado:
            cfg = _de_sala(cfg)
        self.id = cfg["id"]
        self.dispositivos = cfg["dispositivos"]
        self.comodos = {c["id"]: Comodo(c, self.dispositivos) for c in cfg["comodos"]}
        self.passagens = {p["id"]: Passagem(p) for p in cfg["passagens"]}
        self.ocupantes = cfg["ocupantes"]
        self.controle = cfg.get("controle", {})
        self.plataforma = cfg.get("plataforma", {})
        self.passo_ms = cfg.get("passo_ms", 100)

    # ------------------------------------------------------------------ consultas
    @property
    def ids(self) -> list[str]:
        return list(self.comodos)

    @property
    def multi(self) -> bool:
        return len(self.comodos) > 1

    @property
    def externa(self) -> Passagem:
        return next(p for p in self.passagens.values() if p.tipo == EXTERNA)

    def passagem_entre(self, a: str, b: str) -> Optional[Passagem]:
        return next((p for p in self.passagens.values() if p.tipo == INTERNA and set(p.comodos) == {a, b}), None)

    def rng_nome(self, dispositivo: str) -> str:
        return _RNG_LEGADO.get(dispositivo, dispositivo) if self.legado else dispositivo

    def comodos_do_dispositivo(self, dispositivo: str) -> list[str]:
        """Para quem vai a evidência de um dispositivo (RN-V1-01: SA de passagem interna vai aos dois)."""
        for p in self.passagens.values():
            if p.sa == dispositivo:
                return list(p.comodos)
        return [c.id for c in self.comodos.values() if dispositivo in c.dispositivos]

    def permitidos(self, comodo: str) -> set[str]:
        """Origens de evidência que o controlador de um cômodo pode receber (OR-13)."""
        c = self.comodos[comodo]
        sas = {p.sa for p in self.passagens.values() if comodo in p.comodos}
        return set(c.dispositivos) | sas | {"HUB", "PLATAFORMA"}

    def comodo_do_atuador(self, atuador: str) -> Optional[str]:
        return next((c.id for c in self.comodos.values() if c.atuador == atuador), None)

    def config_comodo(self, comodo: str, roteiro: Optional[dict] = None) -> dict:
        roteiro = roteiro or {}
        return {**self.controle, **self.comodos[comodo].controle, **roteiro.get("controle", {}),
                **roteiro.get("controle_comodos", {}).get(comodo, {})}

    def sala_da_vista(self, comodo: str) -> dict:
        """Configuração no formato da v0, para o oráculo avaliar um cômodo isolado."""
        c = self.comodos[comodo]
        return {"controle": {**self.controle, **c.controle},
                "dispositivos": {"LAMP-01": self.dispositivos[c.lampada]},
                "plataforma": self.plataforma}


def _de_sala(s: dict) -> dict:
    """Converte o formato sala (v0) em residência de um cômodo, sem mudar nada do que importa."""
    porta = s["porta"]
    return {
        "id": s.get("id", "SALA-01"), "passo_ms": s.get("passo_ms", 100),
        "dispositivos": s["dispositivos"], "ocupantes": s["ocupantes"],
        "controle": s.get("controle", {}), "plataforma": s.get("plataforma", {}),
        "comodos": [{
            "id": "sala", "nome": "Sala", "x0": 0.0, "y0": 0.0,
            "largura_m": s["largura_m"], "profundidade_m": s["profundidade_m"],
            "zonas_cegas": s.get("zonas_cegas", []), "sp": "SP-01", "atuador": "ATU-01",
            "lampada": s["lampada"], "interruptor": s["interruptor"],
        }],
        "passagens": [{
            "id": porta["id"], "tipo": EXTERNA, "comodos": ["sala"], "sa": "SA-01",
            "pontos": {"sala": [0.95, 0.4]}, "alvo": {"sala": [0.95, 1.0]},
        }],
    }
