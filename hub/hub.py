"""Hub simulado: barramento, executor de atuações e ciclo de vida do controlador.

- Barramento: entrega evidências ao controlador (nunca a verdade) e registra
  percepção, decisões e estado (plano §7.1).
- Executor: aplica RN-I0-06 (classificação), RN-I0-07 (nova tentativa com a
  mesma chave) e RN-I0-08 (reinício com lacuna e leitura da lâmpada).
- v0dt: recebe do agente de sincronização os comandos remotos (como evidência
  COMANDO_REMOTO) e as novas versões de configuração (evidência CONFIGURACAO),
  e devolve ao agente o resultado de cada comando remoto.
"""
from __future__ import annotations

from typing import Callable, Optional

from sim.modelos import (
    ACENDER, ATUACAO, DECISAO, DESCONHECIDO, EFEITO_OBSERVADO, ESTADO,
    EXECUCAO_RELATADA, MANUAL, PERCEPCAO, SISTEMA, SUBSTITUIDA, VERDADE,
    ConfigSala, Evidencia, Intencao,
)
from hub.registro import Registro


class Executor:
    """Envia intenções ao atuador e classifica o resultado."""

    def __init__(self, hub: "Hub", boot: int):
        self.hub = hub
        self.boot = boot
        self.n = 0
        self.pend: dict[str, dict] = {}
        self.lampada_observada: Optional[bool] = None

    def nova_chave(self) -> str:
        self.n += 1
        return f"I-{self.boot}-{self.n:04d}"

    def enviar(self, intencao: Intencao, t: int, evidencia_id: Optional[str], ocupacao: str,
               chave_remota: Optional[str] = None) -> None:
        # Uma intenção nova substitui as pendentes (o último pedido vale)
        for chave in list(self.pend):
            p = self.pend.pop(chave)
            self._resultado(t, chave, p["acao"], SUBSTITUIDA, False)
        chave = self.nova_chave()
        extra = {"chave_remota": chave_remota} if chave_remota else {}
        if chave_remota:
            self.hub.remotas[chave] = chave_remota
        self.hub.reg.add(
            DECISAO, "INTENCAO", t, acao=intencao.acao, causa=intencao.causa,
            regra=intencao.regra, precedencia=intencao.precedencia, chave=chave,
            evidencia_id=evidencia_id, ocupacao_no_momento=ocupacao,
            controlador=self.hub.ctrl.nome, **extra,
        )
        self.pend[chave] = {"acao": intencao.acao, "t_envio": t, "tentativas": 1, "confirmado": False}
        self.hub.comandar_atuador(chave, intencao.acao, t)

    def observar(self, ev: Evidencia) -> None:
        if ev.tipo == "CONFIRMACAO":
            p = self.pend.get(ev.dados.get("chave"))
            if p:
                p["confirmado"] = True
        elif ev.tipo in ("EFEITO", "LEITURA_LAMPADA"):
            self.lampada_observada = bool(ev.dados.get("acesa"))

    def tick(self, t: int) -> None:
        cfg = self.hub.cfg
        for chave in list(self.pend):
            p = self.pend[chave]
            desejado = p["acao"] == ACENDER
            if p["confirmado"] and self.lampada_observada == desejado:
                self.pend.pop(chave)
                self._resultado(t, chave, p["acao"], EFEITO_OBSERVADO, False)
                continue
            decorrido = t - p["t_envio"]
            if not p["confirmado"] and p["tentativas"] == 1 and decorrido >= cfg.t_retentativa_ms:
                p["tentativas"] = 2
                self.hub.reg.add(SISTEMA, "RETENTATIVA", t, chave=chave, acao=p["acao"])
                self.hub.comandar_atuador(chave, p["acao"], t)
            if decorrido >= cfg.t_confirmacao_ms:
                self.pend.pop(chave)
                if p["confirmado"]:
                    self._resultado(t, chave, p["acao"], EXECUCAO_RELATADA, True)
                else:
                    self._resultado(t, chave, p["acao"], DESCONHECIDO, False)

    def _resultado(self, t: int, chave: str, acao: str, nivel: str, divergencia: bool) -> None:
        self.hub.reg.add(ATUACAO, "RESULTADO", t, chave=chave, acao=acao, nivel=nivel, divergencia=divergencia)
        remota = self.hub.remotas.pop(chave, None)
        if remota and self.hub.agente is not None:
            self.hub.agente.resultado_comando(t, remota, nivel)
        self.hub.resultados_a_entregar.append(
            Evidencia(f"res-{chave}", t, "HUB", "RESULTADO",
                      {"chave": chave, "acao": acao, "nivel": nivel, "divergencia": divergencia})
        )


class Hub:
    def __init__(self, reg: Registro, fabrica_controlador: Callable[[], object], cfg: ConfigSala,
                 comandar_atuador: Callable[[str, str, int], None]):
        self.reg = reg
        self.cfg = cfg
        self.fabrica = fabrica_controlador
        self.comandar_atuador = comandar_atuador
        self.ligado = True
        self.boot = 1
        self.ctrl = None
        self.executor: Optional[Executor] = None
        self.resultados_a_entregar: list[Evidencia] = []
        self.ultimo_estado = None
        self.alertas_ativos: set[str] = set()
        self.desligado_em: Optional[int] = None
        self.entregas = {c: 0 for c in ("PERCEPCAO", "VERDADE")}
        self.agente = None                     # v0dt: agente de sincronização
        self.remotas: dict[str, str] = {}      # chave do executor → chave do comando remoto
        self._chave_remota: Optional[str] = None
        self._intencoes_remotas = 0
        self._iniciar_controlador()

    # ----------------------------------------------------------- ciclo de vida
    def _iniciar_controlador(self) -> None:
        self.ctrl = self.fabrica()
        self.ctrl.iniciar(self.cfg)
        self.executor = Executor(self, self.boot)
        self.ultimo_estado = None
        self.resultados_a_entregar = []

    def desligar(self, t: int) -> None:
        self.reg.add(SISTEMA, "HUB_DESLIGADO", t)
        self.ligado = False
        self.desligado_em = t
        self.ctrl = None
        self.executor = None
        self.alertas_ativos = set()
        self.remotas = {}
        if self.agente is not None:
            self.agente.desligar(t)

    def ligar(self, t: int, lampada_acesa: bool) -> None:
        self.boot += 1
        self.ligado = True
        self.reg.add(SISTEMA, "HUB_LIGADO", t, boot=self.boot)
        self.reg.add(SISTEMA, "LACUNA", t, inicio_ms=self.desligado_em, fim_ms=t)
        self._iniciar_controlador()
        # RN-I0-08: lê o estado da lâmpada pelo sensor de efeito
        self.receber(t, "LAMP-01", "LEITURA_LAMPADA", {"acesa": lampada_acesa}, t)
        if self.agente is not None:
            self.agente.ligar(t)

    # ------------------------------------------------------------------ v0dt
    def comando_remoto(self, t: int, chave: str, acao: str, solicitante: str) -> Optional[str]:
        """Entrega o comando remoto ao controlador. Devolve o motivo da recusa, ou None se virou intenção."""
        if not self.ligado:
            return "HUB_DESLIGADO"
        self._chave_remota = chave
        self._intencoes_remotas = 0
        try:
            self.receber(t, "PLATAFORMA", "COMANDO_REMOTO",
                         {"chave_remota": chave, "acao": acao, "solicitante": solicitante}, t)
        finally:
            self._chave_remota = None
        if self._intencoes_remotas:
            return None
        e = self.ctrl.estado()
        return "PRECEDENCIA_MANUAL" if e.precedencia == MANUAL else "SEM_DECISAO_DO_CONTROLADOR"

    def aplicar_config(self, t: int, versao: int, parametros: dict) -> None:
        """RN-DT-07: aplica a versão (o agente já garantiu que é maior que a aplicada)."""
        for k, v in parametros.items():
            if k in self.cfg.__dataclass_fields__:
                setattr(self.cfg, k, v)
        self.reg.add(SISTEMA, "CONFIG_APLICADA", t, versao=versao, **parametros)
        if self.ligado:
            self.receber(t, "PLATAFORMA", "CONFIGURACAO", {"versao": versao, **parametros}, t)

    # --------------------------------------------------------------- barramento
    def receber(self, t_emissao: float, origem: str, tipo: str, dados: dict, agora: int) -> None:
        if not self.ligado:
            return
        reg_ev = self.reg.add(PERCEPCAO, tipo, t_emissao, origem=origem, **dados)
        ev = Evidencia(reg_ev["id"], reg_ev["t_ms"], origem, tipo, dict(dados))
        self._entregar(ev, agora)

    def _entregar(self, ev: Evidencia, agora: int) -> None:
        # Contrato §7.2 / OR-06: o controlador só recebe percepção
        self.entregas["PERCEPCAO"] += 1
        self.executor.observar(ev)
        intencoes = self.ctrl.ao_evento(ev, agora)
        self._executar(intencoes, agora, ev.id if not ev.id.startswith("res-") else None)

    def _executar(self, intencoes, agora: int, evidencia_id: Optional[str]) -> None:
        for it in intencoes or []:
            ocup = self.ctrl.estado().ocupacao
            # Toda intenção devolvida ao tratar o COMANDO_REMOTO responde a ele
            remota = self._chave_remota
            if remota:
                self._intencoes_remotas += 1
            self.executor.enviar(it, agora, evidencia_id, ocup, remota)

    def tick(self, t: int) -> None:
        if not self.ligado:
            return
        pendentes, self.resultados_a_entregar = self.resultados_a_entregar, []
        for ev in pendentes:
            self._entregar(ev, t)
        self._executar(self.ctrl.ao_tick(t), t, None)
        self.executor.tick(t)

    def registrar_estado(self, t: int, periodico: bool) -> None:
        if not self.ligado:
            return
        e = self.ctrl.estado()
        chave = (e.ocupacao, e.luz, e.precedencia, e.alertas)
        mudou = chave != self.ultimo_estado
        if mudou or periodico:
            self.reg.add(ESTADO, "ESTADO_SALA", t, ocupacao=e.ocupacao, luz=e.luz,
                         precedencia=e.precedencia, idade_evidencia_ms=e.idade_evidencia_ms,
                         alertas=list(e.alertas), mudanca=mudou)
        self.ultimo_estado = chave
        atuais = set(e.alertas)
        for a in sorted(atuais - self.alertas_ativos):
            self.reg.add(SISTEMA, "ALERTA", t, alerta=a, ativo=True)
        for a in sorted(self.alertas_ativos - atuais):
            self.reg.add(SISTEMA, "ALERTA", t, alerta=a, ativo=False)
        self.alertas_ativos = atuais
