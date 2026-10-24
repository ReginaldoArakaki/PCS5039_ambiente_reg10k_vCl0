"""Motor de simulação de passo fixo (100 ms), determinístico por semente.

v0dt: além do mundo, dos dispositivos e do hub, o motor monta o canal
simulado, o agente de sincronização (DTReg10k-L), a plataforma (DTReg10k-R)
e o app. Cada um usa um gerador aleatório próprio, por isso ligar ou
desligar a rede não altera o que acontece na sala.
"""
from __future__ import annotations

import heapq
import itertools
import random
from typing import Callable

from hub.hub import Hub
from hub.registro import Registro
from hub.sincronizacao import AgenteSincronizacao
from plataforma.canal import DESCE, SOBE, Canal
from plataforma.plataforma import Plataforma
from sim.dispositivos import Atuador, Interruptor, Lampada, SensorPassagem, SensorPresencaPIR
from sim.modelos import ATUACAO, REDE, SISTEMA, VERDADE, ConfigSala
from sim.mundo import PONTO_ENTRADA, Ocupante, Sala, mover

ACOES_VALIDAS = {
    "ENTRAR", "SAIR", "ANDAR", "ANDAR_ALEATORIO", "PARADO", "MICROGESTOS",
    "GESTO", "PASSAR_PORTA_SEM_ENTRAR", "INTERRUPTOR",
}
FALHAS_VALIDAS = {
    "SP_SEM_RESPOSTA", "BATERIA_BAIXA", "SP_FALSO_DISPARO", "SA_ESPURIO",
    "SA_PERDE_PROXIMA", "LAMPADA_QUEIMADA", "ATUADOR_TRAVADO", "HUB_REINICIO",
    "RELOGIO_SALTO",
    # v0dt: rede e plataforma
    "CANAL_DESCONECTA", "PLATAFORMA_FORA", "CANAL_LATENCIA", "CANAL_DUPLICA", "CANAL_PERDE",
}
ACOES_APP = {"APP_COMANDO", "APP_PREFERENCIA", "APP_CONSULTA"}
ATOR_APP = "app"


class Simulacao:
    def __init__(self, sala_cfg: dict, roteiro: dict, fabrica_controlador: Callable[[], object],
                 semente: int = 42, modo: str | None = None):
        self.sala_cfg = sala_cfg
        self.roteiro = roteiro
        self.semente = semente
        self.modo = (modo or roteiro.get("modo", "IDEAL")).upper()
        chave_modo = "ideal" if self.modo == "IDEAL" else "realista"
        self.dt = sala_cfg.get("passo_ms", 100)
        self.duracao = roteiro["duracao_ms"]
        self.sala = Sala(sala_cfg)
        self.reg = Registro(roteiro["id"], semente)
        self.heap: list = []
        self._ordem = itertools.count()

        def rng(nome: str) -> random.Random:
            return random.Random(f"{semente}:{roteiro['id']}:{nome}")

        self.rng_mundo = rng("mundo")
        disp = sala_cfg["dispositivos"]
        p = lambda nome: dict(disp[nome][chave_modo])
        self.sa = SensorPassagem(p("SA-01"), rng("SA"), self._emitir)
        self.sp = SensorPresencaPIR(p("SP-01"), rng("SP"), self._emitir)
        self.lampada = Lampada(p("LAMP-01"), rng("LAMP"), self._emitir, self._agendar, self._verdade)
        self.atuador = Atuador(p("ATU-01"), rng("ATU"), self._emitir, self._agendar, self._comutacao, self.lampada)
        self.interruptor = Interruptor(p("INT-01"), rng("INT"), self._emitir)
        if self.modo == "REALISTA":
            self.reg.deriva_ppm = rng("relogio").uniform(-50, 50)

        cfg = ConfigSala.de_dict({**sala_cfg.get("controle", {}), **roteiro.get("controle", {})})
        self.hub = Hub(self.reg, fabrica_controlador, cfg, self.atuador.comando)
        self.ocupantes = {o["id"]: Ocupante(o["id"], o["tipo"]) for o in sala_cfg["ocupantes"]}

        # v0dt: canal, plataforma (DTReg10k-R) e agente de sincronização (DTReg10k-L)
        plat = sala_cfg["plataforma"]
        self.modo_rede = (roteiro.get("rede", {}).get("modo") or self.modo).upper()
        chave_rede = "ideal" if self.modo_rede == "IDEAL" else "realista"
        self.canal = Canal(dict(plat["canal"][chave_rede]), rng("canal"), self._agendar, self.reg)
        self.plataforma = Plataforma(self.reg, self.canal, plat, dict(plat["app"][chave_rede]), rng("plataforma"),
                                     self._agendar, cfg)
        p_agente = {**plat, "reconexao_jitter": plat["reconexao_jitter"][chave_rede]}
        self.agente = AgenteSincronizacao(self.hub, self.reg, self.canal, p_agente, rng("agente"), self.plataforma)
        self.plataforma.agente = self.agente
        self.hub.agente = self.agente
        self.acoes = sorted(roteiro.get("acoes", []), key=lambda a: a["t_ms"])
        self.falhas = sorted(roteiro.get("falhas", []), key=lambda f: f["t_ms"])
        self._ia = 0
        self._if = 0
        self._ultimos_presentes: tuple = ()
        self._validar()

    # ---------------------------------------------------------------- utilidades
    def _validar(self) -> None:
        for a in self.acoes:
            if a["acao"] in ACOES_APP:
                if a.get("ocupante") != ATOR_APP:
                    raise ValueError(f"{self.roteiro['id']}: {a['acao']} é ação do ator 'app'")
                continue
            if a["acao"] not in ACOES_VALIDAS:
                raise ValueError(f"{self.roteiro['id']}: ação desconhecida {a['acao']}")
            if a.get("ocupante") not in self.ocupantes:
                raise ValueError(f"{self.roteiro['id']}: ocupante desconhecido {a.get('ocupante')}")
        for f in self.falhas:
            if f["tipo"] not in FALHAS_VALIDAS:
                raise ValueError(f"{self.roteiro['id']}: falha desconhecida {f['tipo']}")

    def _agendar(self, t: float, fn) -> None:
        heapq.heappush(self.heap, (t, next(self._ordem), fn))

    def _emitir(self, t: float, origem: str, tipo: str, dados: dict) -> None:
        self._agendar(t, lambda tt, agora=None: self.hub.receber(tt, origem, tipo, dados, self._agora))

    def _verdade(self, t: float, tipo: str, **dados) -> None:
        self.reg.add(VERDADE, tipo, t, **dados)

    def _comutacao(self, t: float, chave: str, ligado: bool) -> None:
        self.reg.add(ATUACAO, "COMUTACAO", t, origem="ATU-01", chave=chave, ligado=ligado)

    def _presentes(self) -> tuple:
        return tuple(sorted(o.id for o in self.ocupantes.values() if o.na_sala))

    # -------------------------------------------------------------------- ações
    def _aplicar_acao(self, a: dict) -> None:
        if a["acao"] in ACOES_APP:
            self._acao_app(a)
            return
        o = self.ocupantes[a["ocupante"]]
        t = a["t_ms"]
        acao = a["acao"]
        vel = float(a.get("vel_m_s", 1.0))
        if acao == "ENTRAR":
            if o.na_sala:
                raise ValueError(f"{self.roteiro['id']}: {o.id} já está na sala em t={t}")
            self._verdade(t, "CRUZOU_PORTA", ocupante=o.id, sentido="ENTRADA", vel_m_s=vel)
            self.sa.estimulo(t, vel)
            o.pos = PONTO_ENTRADA
            o.modo, o.alvo, o.vel = "ANDAR", (0.95, 1.0), min(vel, 1.5)
        elif acao == "SAIR":
            if not o.na_sala:
                raise ValueError(f"{self.roteiro['id']}: {o.id} não está na sala em t={t}")
            self._verdade(t, "CRUZOU_PORTA", ocupante=o.id, sentido="SAIDA", vel_m_s=vel)
            self.sa.estimulo(t, vel)
            o.pos, o.modo, o.alvo = None, "FORA", None
        elif acao == "ANDAR":
            o.modo, o.alvo, o.vel = "ANDAR", tuple(a["ate"]), vel
        elif acao == "ANDAR_ALEATORIO":
            o.modo, o.vel = "ALEATORIO", float(a.get("vel_m_s", 0.8))
            o.area = tuple(a["area"]) if a.get("area") else None
            o.fim_ms = t + a["duracao_ms"]
            o.alvo = self.sala.ponto_aleatorio(self.rng_mundo, o.area)
        elif acao == "PARADO":
            o.modo, o.alvo = "PARADO", None
        elif acao == "MICROGESTOS":
            o.modo, o.alvo = "MICRO", None
            o.micro_intervalo = (a.get("intervalo_min_ms", 120_000), a.get("intervalo_max_ms", 240_000))
            o.micro_prox = t + self.rng_mundo.randint(*o.micro_intervalo)
        elif acao == "GESTO":
            o.gesto_ate = t + a.get("duracao_ms", 1000)
            self._verdade(t, "GESTO", ocupante=o.id)
        elif acao == "PASSAR_PORTA_SEM_ENTRAR":
            self._verdade(t, "PASSOU_PORTA_SEM_ENTRAR", ocupante=o.id)
            self.sa.estimulo(t, vel)
        elif acao == "INTERRUPTOR":
            self._verdade(t, "INTERRUPTOR_ACIONADO", ocupante=o.id)
            self.interruptor.acionar(t)

    def _acao_app(self, a: dict) -> None:
        t = a["t_ms"]
        if a["acao"] == "APP_COMANDO":
            self.plataforma.app_comando(t, a["comando"])
        elif a["acao"] == "APP_PREFERENCIA":
            self.plataforma.app_preferencia(t, {"t_apagamento_ms": a["t_apagamento_ms"]})
        else:
            self.plataforma.app_consulta(t)

    def _sentidos(self, f: dict) -> tuple:
        s = f.get("sentido", "AMBOS")
        return (SOBE, DESCE) if s == "AMBOS" else (s,)

    def _enlace(self, t: float, ativo: bool) -> None:
        self.canal.enlace = ativo
        if ativo:
            self.reg.add(REDE, "ENLACE_VOLTOU", t)
        else:
            self.reg.add(REDE, "ENLACE_CAIU", t)
            self.agente.sessao_caiu(t, "ENLACE_FORA")
            self.plataforma.sessao_caiu(t, "ENLACE_FORA")

    def _plataforma(self, t: float, ativa: bool) -> None:
        if ativa:
            self.plataforma.voltar(t)
        else:
            self.plataforma.cair(t)
            self.agente.sessao_caiu(t, "PLATAFORMA_FORA")

    def _aplicar_falha(self, f: dict) -> None:
        t, tipo = f["t_ms"], f["tipo"]
        self._verdade(t, "FALHA_INJETADA", falha=tipo, **{k: v for k, v in f.items() if k not in ("t_ms", "tipo")})
        if tipo == "SP_SEM_RESPOSTA":
            self.sp.sem_resposta = True
            if f.get("duracao_ms"):
                self._agendar(t + f["duracao_ms"], lambda tt: setattr(self.sp, "sem_resposta", False))
        elif tipo == "BATERIA_BAIXA":
            self.sp.bateria = f.get("nivel", 12)
        elif tipo == "SP_FALSO_DISPARO":
            self.sp.forcar_disparo = True
        elif tipo == "SA_ESPURIO":
            self.sa.espurio(t)
        elif tipo == "SA_PERDE_PROXIMA":
            self.sa.perder_proxima = True
        elif tipo == "LAMPADA_QUEIMADA":
            self.lampada.queimar(t)
        elif tipo == "ATUADOR_TRAVADO":
            self.atuador.travado = True
        elif tipo == "HUB_REINICIO":
            self.hub.desligar(t)
            self._agendar(t + f.get("duracao_ms", 20_000), lambda tt: self.hub.ligar(int(tt), self.lampada.fisica))
        elif tipo == "CANAL_DESCONECTA":
            self._enlace(t, False)
            self._agendar(t + f.get("duracao_ms", 60_000), lambda tt: self._enlace(tt, True))
        elif tipo == "PLATAFORMA_FORA":
            self._plataforma(t, False)
            self._agendar(t + f.get("duracao_ms", 60_000), lambda tt: self._plataforma(tt, True))
        elif tipo == "CANAL_LATENCIA":
            sent = self._sentidos(f)
            for s in sent:
                self.canal.latencia_extra[s] = f["latencia_ms"]
            self.reg.add(REDE, "LATENCIA_ALTERADA", t, latencia_extra_ms=f["latencia_ms"], sentidos=list(sent))

            def normalizar(tt, sent=sent):
                for s in sent:
                    self.canal.latencia_extra[s] = 0
                self.reg.add(REDE, "LATENCIA_ALTERADA", tt, latencia_extra_ms=0, sentidos=list(sent))
            self._agendar(t + f.get("duracao_ms", 60_000), normalizar)
        elif tipo == "CANAL_DUPLICA":
            for s in self._sentidos(f):
                self.canal.duplicar[s].add(f["mensagem"])
        elif tipo == "CANAL_PERDE":
            for s in self._sentidos(f):
                self.canal.perder[s].add(f["mensagem"])
        elif tipo == "RELOGIO_SALTO":
            delta = f.get("delta_ms", -300_000)
            self.reg.offset_ms += delta
            self.reg.relogio_confiavel = False
            self.reg.add(SISTEMA, "RELOGIO_SALTO", t, delta_ms=delta)

    # ---------------------------------------------------------------- execução
    def executar(self) -> Registro:
        ini = self.roteiro.get("estado_inicial", {})
        for item in ini.get("ocupantes_na_sala", []):
            o = self.ocupantes[item["id"]]
            o.pos = tuple(item.get("pos", (2.5, 2.0)))
            o.modo = "PARADO"
        self.reg.add(VERDADE, "INICIO", 0, roteiro=self.roteiro["id"], modo=self.modo, semente=self.semente,
                     controlador=self.hub.ctrl.nome)
        self._verdade(0, "OCUPANTES", presentes=list(self._presentes()))
        self._verdade(0, "LUZ_FISICA", acesa=False)
        self._ultimos_presentes = self._presentes()
        janela = {oid: {"movendo": False, "microgesto": False, "parado": False} for oid in self.ocupantes}

        t = 0
        while t <= self.duracao:
            self._agora = t
            while self._if < len(self.falhas) and self.falhas[self._if]["t_ms"] <= t:
                self._aplicar_falha(self.falhas[self._if]); self._if += 1
            while self._ia < len(self.acoes) and self.acoes[self._ia]["t_ms"] <= t:
                self._aplicar_acao(self.acoes[self._ia]); self._ia += 1

            for o in self.ocupantes.values():
                mover(o, self.sala, t, self.dt, self.rng_mundo)
                if self.sala.coberto_pelo_sp(o.pos):
                    j = janela[o.id]
                    if o.movendo:
                        j["movendo"] = True
                    elif o.microgesto:
                        j["microgesto"] = True
                    else:
                        j["parado"] = True

            self.sa.passo(t, self.dt)
            self.sp.passo(t)
            if t > 0 and t % 1000 == 0:
                leituras = [dict(tipo=self.ocupantes[oid].tipo, **j) for oid, j in janela.items()]
                self.sp.janela(t, leituras)
                janela = {oid: {"movendo": False, "microgesto": False, "parado": False} for oid in self.ocupantes}

            while self.heap and self.heap[0][0] <= t:
                tt, _, fn = heapq.heappop(self.heap)
                fn(tt)

            self.hub.tick(t)
            self.hub.registrar_estado(t, periodico=(t % 1000 == 0))
            self.agente.tick(t)
            self.plataforma.tick(t)

            presentes = self._presentes()
            if presentes != self._ultimos_presentes:
                self._verdade(t, "OCUPANTES", presentes=list(presentes))
                self._ultimos_presentes = presentes
            if t % 1000 == 0:
                self._verdade(t, "POSICOES", ocupantes={
                    o.id: (None if o.pos is None else [round(o.pos[0], 2), round(o.pos[1], 2), int(o.movendo)])
                    for o in self.ocupantes.values()})
            t += self.dt

        self.reg.add(SISTEMA, "SINCRONIZACAO", self.duracao, modo_rede=self.modo_rede, canal=dict(self.canal.contagem),
                     hub=self.agente.balanco(), plataforma=self.plataforma.balanco())
        self.reg.add(SISTEMA, "FIM", self.duracao, entregas_ao_controlador=dict(self.hub.entregas))
        return self.reg


def simular(sala_cfg: dict, roteiro: dict, fabrica_controlador, semente: int = 42, modo: str | None = None) -> Registro:
    return Simulacao(sala_cfg, roteiro, fabrica_controlador, semente, modo).executar()
