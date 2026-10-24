"""Tipos compartilhados entre simulador, hub e controladores.

Os nomes seguem a V2 (modelo de informação) da plataforma Reg10k:
Evidencia, Intencao, ResultadoAtuacao e EstadoComodo (aqui, EstadoSala).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Camadas do registro (plano §8.2)
VERDADE = "VERDADE"
PERCEPCAO = "PERCEPCAO"
DECISAO = "DECISAO"
ATUACAO = "ATUACAO"
ESTADO = "ESTADO"
SISTEMA = "SISTEMA"
# v0dt: canal simulado e plataforma (DTReg10k-R, comandos, configuração, app)
REDE = "REDE"
PLATAFORMA = "PLATAFORMA"
CAMADAS = (VERDADE, PERCEPCAO, DECISAO, ATUACAO, ESTADO, SISTEMA, REDE, PLATAFORMA)

# Ocupação inferida (Figura 3)
OCUPADA = "OCUPADA"
VAZIA = "VAZIA"
DESCONHECIDA = "DESCONHECIDA"

# Estados da luz (Figura 4)
APAGADA = "APAGADA"
ACESA_AUTO = "ACESA_AUTO"
ACESA_MANUAL = "ACESA_MANUAL"
APAGADA_MANUAL = "APAGADA_MANUAL"
LUZ_ACESA = (ACESA_AUTO, ACESA_MANUAL)

# Ações e precedência
ACENDER = "ACENDER"
APAGAR = "APAGAR"
AUTOMATICA = "AUTOMATICA"
MANUAL = "MANUAL"
REMOTA = "REMOTA"  # v0dt: comando do app; abaixo da manual, acima da automática

# Níveis de resultado da atuação (RN02 / RN-I0-06)
EFEITO_OBSERVADO = "EFEITO_OBSERVADO"
EXECUCAO_RELATADA = "EXECUCAO_RELATADA"
DESCONHECIDO = "DESCONHECIDO"
SUBSTITUIDA = "SUBSTITUIDA"
# Resultados exclusivos de comando remoto (RF-OPR-04)
REJEITADA = "REJEITADA"
EXPIRADA = "EXPIRADA"

# Atualidade de um atributo no DTReg10k-R (RN-DT-04)
ATUAL = "ATUAL"
DESATUALIZADO = "DESATUALIZADO"
SEM_EVIDENCIA = "SEM_EVIDENCIA"


@dataclass(frozen=True)
class Evidencia:
    """O que chega ao controlador. Nunca contém a camada de verdade."""

    id: str
    t_ms: int  # instante em que o dispositivo emitiu (tempo monotônico)
    origem: str  # SA-01, SP-01, INT-01, LAMP-01, ATU-01, HUB
    tipo: str  # PASSAGEM, MOVIMENTO, FIM_MOVIMENTO, HEARTBEAT, INTERRUPTOR,
    #            EFEITO, LEITURA_LAMPADA, CONFIRMACAO, RESULTADO,
    #            COMANDO_REMOTO e CONFIGURACAO (v0dt, origem PLATAFORMA)
    dados: dict = field(default_factory=dict)


@dataclass
class Intencao:
    """O que o controlador pede ao atuador."""

    acao: str  # ACENDER | APAGAR
    causa: str  # PASSAGEM_SA, MOVIMENTO_SP, AUSENCIA, INTERRUPTOR, ...
    regra: str  # RN-I0-xx que justifica a decisão
    precedencia: str = AUTOMATICA  # AUTOMATICA | MANUAL | REMOTA


@dataclass(frozen=True)
class EstadoSala:
    """Estado inferido pelo controlador (corresponde a EstadoComodo na V2)."""

    ocupacao: str
    luz: str
    precedencia: str
    idade_evidencia_ms: Optional[int]
    alertas: tuple = ()


@dataclass
class ConfigSala:
    """Parâmetros de controle (plano §5.2)."""

    t_apagamento_ms: int = 60_000
    t_manual_ms: int = 900_000
    t_heartbeat_falha_ms: int = 30_000
    t_confirmacao_ms: int = 10_000
    t_retentativa_ms: int = 2_000
    validade_evidencia_ms: int = 10_000

    @classmethod
    def de_dict(cls, d: dict) -> "ConfigSala":
        campos = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**campos)
