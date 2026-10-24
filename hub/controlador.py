"""Interface do controlador (plano §7.2) e controlador de referência (plano §5).

Os alunos implementam a interface `Controlador`. O controlador recebe
apenas evidências (nunca a verdade do simulador), devolve intenções e
informa o estado inferido.

v0dt: duas evidências novas chegam pelo mesmo `ao_evento`, com origem
PLATAFORMA. COMANDO_REMOTO (acao, chave_remota) já chega validado quanto à
validade e à duplicidade; toda intenção devolvida ao tratá-lo responde ao
comando, e devolver lista vazia é recusá-lo. CONFIGURACAO (versao e
parâmetros) avisa que a configuração mudou; o objeto ConfigSala recebido em
`iniciar` já vem atualizado pelo hub. O tempo `agora_ms` é monotônico: não salta
quando o relógio de parede do hub é ajustado (cenário F06).
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from sim.modelos import (
    ACENDER, ACESA_AUTO, ACESA_MANUAL, APAGADA, APAGADA_MANUAL, APAGAR,
    AUTOMATICA, DESCONHECIDA, DESCONHECIDO, LUZ_ACESA, MANUAL, OCUPADA, REMOTA, VAZIA,
    ConfigSala, EstadoSala, Evidencia, Intencao,
)


@runtime_checkable
class Controlador(Protocol):
    nome: str

    def iniciar(self, config: ConfigSala) -> None:
        """Recebe os parâmetros. Chamado no início e após cada reinício do hub."""

    def ao_evento(self, ev: Evidencia, agora_ms: int) -> list[Intencao]:
        """Chamado a cada evidência entregue pelo barramento."""

    def ao_tick(self, agora_ms: int) -> list[Intencao]:
        """Chamado a cada 100 ms; usado para temporizações."""

    def estado(self) -> EstadoSala:
        """Ocupação inferida, luz, precedência, idade da evidência e alertas."""


class ControladorReferencia:
    """Implementa as regras RN-I0-01 a RN-I0-05 do plano e a RN-DT-09 da v0dt.

    RN-I0-06 a RN-I0-08 (classificação, nova tentativa e reinício) ficam no
    executor do hub, para que os controladores dos alunos tratem só da decisão.
    """

    nome = "referencia"

    # ------------------------------------------------------------------ ciclo
    def iniciar(self, config: ConfigSala) -> None:
        self.cfg = config
        self.t0: Optional[int] = None
        self.agora = 0
        self.ocupacao = DESCONHECIDA          # Figura 3: início em Desconhecida
        self.luz = APAGADA
        self.manual_ate: Optional[int] = None
        self.tipo_intervencao = MANUAL       # MANUAL (interruptor) ou REMOTA (app)
        self.ultima_det: Optional[int] = None
        self.causa_det = ""
        self.detectou_agora = False
        self.sp_alto = False
        self.ultimo_hb: Optional[int] = None
        self.saudavel_desde: Optional[int] = None
        self.sp_estava_saudavel = True
        self.alertas: set[str] = set()

    def ao_evento(self, ev: Evidencia, agora_ms: int) -> list[Intencao]:
        self._marcar_tempo(agora_ms)
        t = ev.tipo
        if t == "PASSAGEM":
            self._deteccao(agora_ms, "PASSAGEM_SA")
        elif t == "MOVIMENTO":
            self.sp_alto = True
            self._deteccao(agora_ms, "MOVIMENTO_SP")
        elif t == "FIM_MOVIMENTO":
            self.sp_alto = False
            self.ultima_det = agora_ms
        elif t == "HEARTBEAT":
            self._heartbeat(ev, agora_ms)
        elif t == "INTERRUPTOR":
            return self._manual(agora_ms) + self._avaliar(agora_ms)
        elif t == "COMANDO_REMOTO":
            return self._remoto(ev, agora_ms) + self._avaliar(agora_ms)
        elif t == "CONFIGURACAO":
            for k, v in ev.dados.items():
                if k in self.cfg.__dataclass_fields__:
                    setattr(self.cfg, k, v)
        elif t == "LEITURA_LAMPADA":
            # RN-I0-08: após reinício, adota o estado observado da lâmpada
            self.luz = ACESA_AUTO if ev.dados.get("acesa") else APAGADA
        elif t == "RESULTADO":
            nivel = ev.dados.get("nivel")
            if nivel == DESCONHECIDO:
                self.alertas.add("FALHA_ATUADOR")
            if ev.dados.get("divergencia"):
                self.alertas.add("DIVERGENCIA_EFEITO")
        return self._avaliar(agora_ms)

    def ao_tick(self, agora_ms: int) -> list[Intencao]:
        self._marcar_tempo(agora_ms)
        return self._avaliar(agora_ms)

    def estado(self) -> EstadoSala:
        idade = None if self.ultima_det is None else self.agora - self.ultima_det
        return EstadoSala(
            ocupacao=self.ocupacao,
            luz=self.luz,
            precedencia=self.tipo_intervencao if self.manual_ate is not None else AUTOMATICA,
            idade_evidencia_ms=idade,
            alertas=tuple(sorted(self.alertas)),
        )

    # ----------------------------------------------------------- auxiliares
    def _marcar_tempo(self, agora: int) -> None:
        if self.t0 is None:
            self.t0 = agora
        self.agora = agora

    def _sp_saudavel(self, agora: int) -> bool:
        ref = self.ultimo_hb if self.ultimo_hb is not None else self.t0
        return agora - ref <= self.cfg.t_heartbeat_falha_ms

    def _dispara_acendimento(self, causa: str, agora: int) -> bool:
        """Gancho para variações: decide se esta detecção pode acender a luz."""
        return True

    def _deteccao(self, agora: int, causa: str) -> None:
        self.ultima_det = agora
        self.causa_det = causa
        if self._dispara_acendimento(causa, agora):
            self.detectou_agora = True
            if self._sp_saudavel(agora):
                self.ocupacao = OCUPADA

    def _heartbeat(self, ev: Evidencia, agora: int) -> None:
        if not self.sp_estava_saudavel:
            self.saudavel_desde = agora
            self.sp_estava_saudavel = True
        self.ultimo_hb = agora
        self.alertas.discard("SP_SEM_RESPOSTA")
        bateria = ev.dados.get("bateria", 100)
        if bateria < 15:
            self.alertas.add("BATERIA_BAIXA")
        else:
            self.alertas.discard("BATERIA_BAIXA")
        alto = bool(ev.dados.get("alto"))
        if alto:
            # Informação de nível: recupera o estado do SP (útil após reinício)
            self.sp_alto = True
            self._deteccao(agora, "HEARTBEAT_SP")
        elif self.sp_alto:
            self.sp_alto = False
            self.ultima_det = agora

    def _manual(self, agora: int) -> list[Intencao]:
        """RN-I0-05: o interruptor alterna a luz e cria precedência de 15 min."""
        self.manual_ate = agora + self.cfg.t_manual_ms
        self.tipo_intervencao = MANUAL
        if self.luz in LUZ_ACESA:
            self.luz = APAGADA_MANUAL
            return [Intencao(APAGAR, "INTERRUPTOR", "RN-I0-05", MANUAL)]
        self.luz = ACESA_MANUAL
        return [Intencao(ACENDER, "INTERRUPTOR", "RN-I0-05", MANUAL)]

    def _remoto(self, ev: Evidencia, agora: int) -> list[Intencao]:
        """RN-DT-09: comando do app cria precedência REMOTA por T_manual.

        É recusado (lista vazia) se houver precedência manual ativa; o
        interruptor, depois, sempre prevalece sobre a precedência remota.
        """
        if self.manual_ate is not None and self.tipo_intervencao == MANUAL:
            return []
        acao = ev.dados.get("acao")
        self.manual_ate = agora + self.cfg.t_manual_ms
        self.tipo_intervencao = REMOTA
        if acao == ACENDER:
            self.luz = ACESA_MANUAL
            return [Intencao(ACENDER, "COMANDO_REMOTO", "RN-DT-09", REMOTA)]
        self.luz = APAGADA_MANUAL
        return [Intencao(APAGAR, "COMANDO_REMOTO", "RN-DT-09", REMOTA)]

    def _avaliar(self, agora: int) -> list[Intencao]:
        saida: list[Intencao] = []
        saudavel = self._sp_saudavel(agora)

        # RN-I0-04: SP sem heartbeat → ocupação desconhecida, nunca apaga por silêncio
        if not saudavel:
            if self.sp_estava_saudavel:
                self.sp_estava_saudavel = False
            self.ocupacao = DESCONHECIDA
            self.sp_alto = False
            self.alertas.add("SP_SEM_RESPOSTA")
        elif self.sp_alto:
            self.ultima_det = agora
            self.ocupacao = OCUPADA

        # RN-I0-03: 60 s sem detecção → vazia (exige SP saudável)
        if saudavel and self.ocupacao != VAZIA and not self.sp_alto:
            refs = [r for r in (self.ultima_det, self.saudavel_desde, self.t0) if r is not None]
            if agora - max(refs) >= self.cfg.t_apagamento_ms:
                self.ocupacao = VAZIA

        # Fim da precedência manual (Figura 4)
        if self.manual_ate is not None and agora >= self.manual_ate:
            self.manual_ate = None
            if self.luz == ACESA_MANUAL:
                self.luz = ACESA_AUTO
            elif self.luz == APAGADA_MANUAL:
                self.luz = APAGADA
                if self.ocupacao == OCUPADA:
                    self.causa_det = "FIM_PRECEDENCIA_MANUAL"

        if self.manual_ate is None:
            if self.luz == ACESA_AUTO and self.ocupacao == VAZIA:
                self.luz = APAGADA
                saida.append(Intencao(APAGAR, "AUSENCIA", "RN-I0-03"))
            elif self.luz == APAGADA and (self.ocupacao == OCUPADA or self.detectou_agora):
                self.luz = ACESA_AUTO
                saida.append(Intencao(ACENDER, self.causa_det or "DETECCAO", "RN-I0-02"))

        self.detectou_agora = False
        return saida
