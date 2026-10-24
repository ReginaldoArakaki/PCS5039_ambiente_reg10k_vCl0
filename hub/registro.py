"""Registrador do hub: registro somente acréscimo, em JSON Lines (plano §8)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sim.modelos import VERDADE


class Registro:
    def __init__(self, cenario: str, semente: int):
        self.cenario = cenario
        self.semente = semente
        self.eventos: list[dict] = []
        self._seq = 0
        # Relógio de parede do hub (pode saltar ou derivar); o tempo de
        # simulação t_ms é sempre monotônico.
        self.offset_ms = 0
        self.deriva_ppm = 0.0
        self.relogio_confiavel = True
        # v0dt: o agente de sincronização observa o registro para publicar no DTReg10k-R
        self.ouvintes: list = []

    def relogio_hub(self, t_ms: int) -> int:
        return int(round(t_ms * (1 + self.deriva_ppm / 1e6))) + self.offset_ms

    def add(self, camada: str, tipo: str, t_ms: float, **dados) -> dict:
        self._seq += 1
        ev = {
            "id": f"{self.cenario}-{self.semente}-{self._seq:06d}",
            "t_ms": int(round(t_ms)),
            "seq": self._seq,
            "camada": camada,
            "tipo": tipo,
        }
        # O relógio de parede é do hub: a verdade, o canal e a plataforma não o usam
        if camada not in (VERDADE, "REDE", "PLATAFORMA"):
            ev["relogio_hub_ms"] = self.relogio_hub(int(round(t_ms)))
            ev["relogio_confiavel"] = self.relogio_confiavel
        ev.update(dados)
        self.eventos.append(ev)
        for ouvir in self.ouvintes:
            ouvir(ev)
        return ev

    # ------------------------------------------------------------ persistência
    def linhas(self) -> list[str]:
        return [json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in self.eventos]

    def salvar(self, caminho: Path) -> str:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = "\n".join(self.linhas()) + "\n"
        caminho.write_text(texto, encoding="utf-8")
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()

    def hash(self) -> str:
        texto = "\n".join(self.linhas()) + "\n"
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()
