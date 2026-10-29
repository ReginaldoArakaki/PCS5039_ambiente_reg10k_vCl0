"""Hub simulado: barramento, executor de atuações e ciclo de vida dos controladores.

- Barramento: entrega evidências ao controlador (nunca a verdade) e registra
  percepção, decisões e estado (plano §7.1).
- Executor: aplica RN-I0-06 (classificação), RN-I0-07 (nova tentativa com a
  mesma chave) e RN-I0-08 (reinício com lacuna e leitura da lâmpada).
- v0dt: recebe do agente de sincronização os comandos remotos (como evidência
  COMANDO_REMOTO) e as novas versões de configuração (evidência CONFIGURACAO),
  e devolve ao agente o resultado de cada comando remoto.
- v1dt: uma **célula** por cômodo (controlador, executor, configuração e
  atuador próprios, RN-V1-02). A evidência de um dispositivo vai às células
  dos cômodos a que ele pertence; o SA de uma passagem interna vai às duas
  (RN-V1-01). Com um cômodo só, tudo é como na v0.
"""
from __future__ import annotations

from typing import Callable, Optional

from sim.modelos import (
    ACENDER, ATUACAO, DECISAO, DESCONHECIDO, EFEITO_OBSERVADO, ESTADO,
    EXECUCAO_RELATADA, MANUAL, PERCEPCAO, SISTEMA, SUBSTITUIDA,
    ConfigSala, Evidencia, Intencao,
)
from hub.registro import Registro


class Executor:
    """Envia intenções ao atuador do cômodo e classifica o resultado."""

    def __init__(self, cel: "Celula", boot: int):
        self.cel = cel
        self.hub = cel.hub
        self.boot = boot
        self.n = 0
        self.pend: dict[str, dict] = {}
        self.lampada_observada: Optional[bool] = None

    def nova_chave(self) -> str:
        self.n += 1
        # Com um cômodo, a chave é a da v0 (regressão por assinatura)
        return f"I-{self.cel.comodo}-{self.boot}-{self.n:04d}" if self.hub.multi else f"I-{self.boot}-{self.n:04d}"

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
            controlador=self.cel.ctrl.nome, comodo=self.cel.comodo, **extra,
        )
        self.pend[chave] = {"acao": intencao.acao, "t_envio": t, "tentativas": 1, "confirmado": False}
        self.cel.comandar_atuador(chave, intencao.acao, t)

    def observar(self, ev: Evidencia) -> None:
        if ev.tipo == "CONFIRMACAO":
            p = self.pend.get(ev.dados.get("chave"))
            if p:
                p["confirmado"] = True
        elif ev.tipo in ("EFEITO", "LEITURA_LAMPADA"):
            self.lampada_observada = bool(ev.dados.get("acesa"))

    def tick(self, t: int) -> None:
        cfg = self.cel.cfg
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
                self.hub.reg.add(SISTEMA, "RETENTATIVA", t, chave=chave, acao=p["acao"], comodo=self.cel.comodo)
                self.cel.comandar_atuador(chave, p["acao"], t)
            if decorrido >= cfg.t_confirmacao_ms:
                self.pend.pop(chave)
                if p["confirmado"]:
                    self._resultado(t, chave, p["acao"], EXECUCAO_RELATADA, True)
                else:
                    self._resultado(t, chave, p["acao"], DESCONHECIDO, False)

    def _resultado(self, t: int, chave: str, acao: str, nivel: str, divergencia: bool) -> None:
        self.hub.reg.add(ATUACAO, "RESULTADO", t, chave=chave, acao=acao, nivel=nivel, divergencia=divergencia,
                         comodo=self.cel.comodo)
        remota = self.hub.remotas.pop(chave, None)
        if remota and self.hub.agente is not None:
            self.hub.agente.resultado_comando(t, remota, nivel)
        self.cel.resultados_a_entregar.append(
            Evidencia(f"res-{chave}", t, "HUB", "RESULTADO",
                      {"chave": chave, "acao": acao, "nivel": nivel, "divergencia": divergencia})
        )


class Celula:
    """Controle de um cômodo: controlador, executor, configuração e atuador."""

    def __init__(self, hub: "Hub", comodo: str, cfg: ConfigSala, comandar_atuador, lampada: str):
        self.hub = hub
        self.comodo = comodo
        self.cfg = cfg
        self.comandar_atuador = comandar_atuador
        self.lampada = lampada
        self.ctrl = None
        self.executor: Optional[Executor] = None
        self.resultados_a_entregar: list[Evidencia] = []
        self.ultimo_estado = None
        self.alertas_ativos: set[str] = set()

    def iniciar(self, boot: int) -> None:
        self.ctrl = self.hub.fabrica()
        self.ctrl.iniciar(self.cfg)
        self.executor = Executor(self, boot)
        self.ultimo_estado = None
        self.resultados_a_entregar = []

    def parar(self) -> None:
        self.ctrl = None
        self.executor = None
        self.alertas_ativos = set()


class Hub:
    def __init__(self, reg: Registro, fabrica_controlador: Callable[[], object], cfgs: dict[str, ConfigSala],
                 comandar: dict[str, Callable[[str, str, int], None]], residencia):
        self.reg = reg
        self.fabrica = fabrica_controlador
        self.res = residencia
        self.multi = residencia.multi
        self.celulas = {cid: Celula(self, cid, cfgs[cid], comandar[cid], residencia.comodos[cid].lampada)
                        for cid in residencia.ids}
        self.ligado = True
        self.boot = 1
        self.desligado_em: Optional[int] = None
        self.entregas = {c: 0 for c in ("PERCEPCAO", "VERDADE")}
        self.entregas_por_comodo: dict[str, dict[str, int]] = {cid: {} for cid in residencia.ids}
        self.agente = None                     # v0dt: agente de sincronização
        self.remotas: dict[str, str] = {}      # chave do executor → chave do comando remoto
        self._chave_remota: Optional[str] = None
        self._intencoes_remotas = 0
        # nucleo-v1.3: detector de presença incompatível (OC-03), fora do controlador
        from hub.presenca import DetectorPresenca
        self.presenca = DetectorPresenca(reg, residencia.externa.sa)
        for c in self.celulas.values():
            c.iniciar(self.boot)

    # --------------------------------------------------------------- consultas
    @property
    def nome_controlador(self) -> str:
        return next(iter(self.celulas.values())).ctrl.nome

    @property
    def cfg(self) -> ConfigSala:
        """Configuração do primeiro cômodo (compatibilidade com a v0)."""
        return next(iter(self.celulas.values())).cfg

    @property
    def ctrl(self):
        """Controlador do primeiro cômodo (compatibilidade com a v0)."""
        return next(iter(self.celulas.values())).ctrl

    def estados(self) -> dict:
        return {cid: (c.ctrl.estado() if c.ctrl else None) for cid, c in self.celulas.items()}

    # ----------------------------------------------------------- ciclo de vida
    def desligar(self, t: int) -> None:
        self.reg.add(SISTEMA, "HUB_DESLIGADO", t)
        self.ligado = False
        self.desligado_em = t
        for c in self.celulas.values():
            c.parar()
        self.remotas = {}
        if self.agente is not None:
            self.agente.desligar(t)

    def ligar(self, t: int, lampadas_acesas) -> None:
        if not isinstance(lampadas_acesas, dict):
            lampadas_acesas = {cid: lampadas_acesas for cid in self.celulas}
        self.boot += 1
        self.ligado = True
        self.reg.add(SISTEMA, "HUB_LIGADO", t, boot=self.boot)
        self.reg.add(SISTEMA, "LACUNA", t, inicio_ms=self.desligado_em, fim_ms=t)
        for c in self.celulas.values():
            c.iniciar(self.boot)
        # RN-I0-08: lê o estado de cada lâmpada pelo sensor de efeito
        for cid, c in self.celulas.items():
            self.receber(t, c.lampada, "LEITURA_LAMPADA", {"acesa": lampadas_acesas[cid]}, t)
        if self.agente is not None:
            self.agente.ligar(t)

    # ------------------------------------------------------------------ v0dt
    def comando_remoto(self, t: int, chave: str, acao: str, solicitante: str,
                       comodo: Optional[str] = None) -> Optional[str]:
        """Entrega o comando remoto ao controlador do cômodo. Devolve o motivo da recusa, ou None."""
        if not self.ligado:
            return "HUB_DESLIGADO"
        cid = comodo or next(iter(self.celulas))
        if cid not in self.celulas:
            return "COMODO_DESCONHECIDO"
        self._chave_remota = chave
        self._intencoes_remotas = 0
        try:
            self.receber(t, "PLATAFORMA", "COMANDO_REMOTO",
                         {"chave_remota": chave, "acao": acao, "solicitante": solicitante}, t, comodos=[cid])
        finally:
            self._chave_remota = None
        if self._intencoes_remotas:
            return None
        e = self.celulas[cid].ctrl.estado()
        return "PRECEDENCIA_MANUAL" if e.precedencia == MANUAL else "SEM_DECISAO_DO_CONTROLADOR"

    def aplicar_config(self, t: int, versao: int, parametros: dict) -> None:
        """RN-DT-07: aplica a versão (o agente já garantiu que é maior que a aplicada).

        v1dt: `parametros["comodo"]` restringe a configuração a um cômodo (RN-V1-03).
        """
        alvo = parametros.get("comodo")
        cids = [alvo] if alvo in self.celulas else list(self.celulas)
        valores = {k: v for k, v in parametros.items() if k != "comodo"}
        for cid in cids:
            cfg = self.celulas[cid].cfg
            for k, v in valores.items():
                if k in cfg.__dataclass_fields__:
                    setattr(cfg, k, v)
        extra = {"comodo": alvo} if alvo else {}
        self.reg.add(SISTEMA, "CONFIG_APLICADA", t, versao=versao, **valores, **extra)
        if self.ligado:
            self.receber(t, "PLATAFORMA", "CONFIGURACAO", {"versao": versao, **valores}, t, comodos=cids)

    # --------------------------------------------------------------- barramento
    def receber(self, t_emissao: float, origem: str, tipo: str, dados: dict, agora: int,
                comodos: Optional[list[str]] = None) -> None:
        if not self.ligado:
            return
        cids = comodos or self.res.comodos_do_dispositivo(origem) or list(self.celulas)
        dados = dict(dados)
        if self.multi and tipo == "PASSAGEM":
            ps = next(p for p in self.res.passagens.values() if p.sa == origem)
            dados.update(passagem=ps.id, comodos=list(ps.comodos))
        reg_ev = self.reg.add(PERCEPCAO, tipo, t_emissao, origem=origem, **{**dados, "comodos": cids})
        ev = Evidencia(reg_ev["id"], reg_ev["t_ms"], origem, tipo, dados)
        self.presenca.observar(reg_ev["t_ms"], origem, tipo, cids)
        for cid in cids:
            self._entregar(self.celulas[cid], ev, agora)

    def _entregar(self, cel: Celula, ev: Evidencia, agora: int) -> None:
        # Contrato §7.2 / OR-06: o controlador só recebe percepção
        self.entregas["PERCEPCAO"] += 1
        conta = self.entregas_por_comodo[cel.comodo]
        conta[ev.origem] = conta.get(ev.origem, 0) + 1
        cel.executor.observar(ev)
        intencoes = cel.ctrl.ao_evento(ev, agora)
        self._executar(cel, intencoes, agora, ev.id if not ev.id.startswith("res-") else None)

    def _executar(self, cel: Celula, intencoes, agora: int, evidencia_id: Optional[str]) -> None:
        for it in intencoes or []:
            ocup = cel.ctrl.estado().ocupacao
            # Toda intenção devolvida ao tratar o COMANDO_REMOTO responde a ele
            remota = self._chave_remota
            if remota:
                self._intencoes_remotas += 1
            cel.executor.enviar(it, agora, evidencia_id, ocup, remota)

    def tick(self, t: int) -> None:
        if not self.ligado:
            return
        self.presenca.tick(t)
        for cel in self.celulas.values():
            pendentes, cel.resultados_a_entregar = cel.resultados_a_entregar, []
            for ev in pendentes:
                self._entregar(cel, ev, t)
            self._executar(cel, cel.ctrl.ao_tick(t), t, None)
            cel.executor.tick(t)

    def registrar_estado(self, t: int, periodico: bool) -> None:
        if not self.ligado:
            return
        for cid, cel in self.celulas.items():
            e = cel.ctrl.estado()
            chave = (e.ocupacao, e.luz, e.precedencia, e.alertas)
            mudou = chave != cel.ultimo_estado
            if mudou or periodico:
                self.reg.add(ESTADO, "ESTADO_SALA", t, ocupacao=e.ocupacao, luz=e.luz,
                             precedencia=e.precedencia, idade_evidencia_ms=e.idade_evidencia_ms,
                             alertas=list(e.alertas), mudanca=mudou, comodo=cid)
            cel.ultimo_estado = chave
            atuais = set(e.alertas)
            for a in sorted(atuais - cel.alertas_ativos):
                self.reg.add(SISTEMA, "ALERTA", t, alerta=a, ativo=True, comodo=cid)
            for a in sorted(cel.alertas_ativos - atuais):
                self.reg.add(SISTEMA, "ALERTA", t, alerta=a, ativo=False, comodo=cid)
            cel.alertas_ativos = atuais
