"""Controlador de exemplo de um grupo (exercício E3 do plano §13.2).

Ideia: a passagem pela porta (SA) sozinha não acende a luz, porque o SA não
sabe a direção (RN09). A luz só acende quando o SP confirma presença. Isso
elimina os falsos positivos FP01 e FP03, ao custo de um pequeno atraso na
entrada (latência do PIR) e de não acender quando o PIR falha.

O controlador reaproveita a referência e altera só o gancho de decisão. Um
grupo pode, em vez disso, implementar a interface `Controlador` do zero.
"""
from __future__ import annotations

from hub.controlador import ControladorReferencia


class ControladorConfirmaSP(ControladorReferencia):
    nome = "grupo_exemplo"

    def _dispara_acendimento(self, causa: str, agora: int) -> bool:
        # A passagem só renova o contador de ausência; quem acende é o SP.
        return causa != "PASSAGEM_SA"
