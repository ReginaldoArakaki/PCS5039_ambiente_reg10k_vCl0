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
from sim.mundo import MICRO_DORMINDO, PERFIS, Ocupante, mover
from sim.residencia import Residencia

ACOES_VALIDAS = {
    "ENTRAR", "SAIR", "ANDAR", "ANDAR_ALEATORIO", "PARADO", "MICROGESTOS",
    "GESTO", "PASSAR_PORTA_SEM_ENTRAR", "INTERRUPTOR",
    # v1dt: circulação entre cômodos
    "MUDAR_COMODO", "ESPIAR",
    # nucleo-v1.3: ocupante dormindo (PI-01)
    "DORMIR", "ACORDAR",
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
        # v1dt: o ambiente é uma residência (a sala da v0 é uma residência de um cômodo)
        self.res = Residencia(sala_cfg)
        self.dt = self.res.passo_ms
        self.duracao = roteiro["duracao_ms"]
        self.reg = Registro(roteiro["id"], semente)
        self.heap: list = []
        self._ordem = itertools.count()

        def rng(nome: str) -> random.Random:
            return random.Random(f"{semente}:{roteiro['id']}:{nome}")

        self.rng_mundo = rng("mundo")
        disp = self.res.dispositivos
        p = lambda nome: dict(disp[nome][chave_modo])
        r = lambda nome: rng(self.res.rng_nome(nome))

        def com_origem(dev, origem):
            dev.origem = origem
            return dev

        # SA de cada passagem; SP, lâmpada, atuador e interruptor de cada cômodo
        self.sas = {ps.sa: com_origem(SensorPassagem(p(ps.sa), r(ps.sa), self._emitir), ps.sa)
                    for ps in self.res.passagens.values()}
        self.sps, self.lampadas, self.atuadores, self.interruptores = {}, {}, {}, {}
        for c in self.res.comodos.values():
            self.sps[c.id] = com_origem(SensorPresencaPIR(p(c.sp), r(c.sp), self._emitir), c.sp)
            lamp = Lampada(p(c.lampada), r(c.lampada), self._emitir, self._agendar, self._verdade_luz(c.id))
            self.lampadas[c.id] = com_origem(lamp, c.lampada)
            atu = Atuador(p(c.atuador), r(c.atuador), self._emitir, self._agendar, self._comutacao(c.id, c.atuador), lamp)
            self.atuadores[c.id] = com_origem(atu, c.atuador)
            self.interruptores[c.id] = com_origem(Interruptor(p(c.interruptor), r(c.interruptor), self._emitir), c.interruptor)
        if self.modo == "REALISTA":
            self.reg.deriva_ppm = rng("relogio").uniform(-50, 50)

        cfgs = {cid: ConfigSala.de_dict(self.res.config_comodo(cid, roteiro)) for cid in self.res.ids}
        self.hub = Hub(self.reg, fabrica_controlador, cfgs, {cid: a.comando for cid, a in self.atuadores.items()}, self.res)
        self.ocupantes = {o["id"]: Ocupante(o["id"], o["tipo"], o.get("perfil", "ADULTO"), o.get("visitante", False))
                          for o in self.res.ocupantes}

        # v0dt: canal, plataforma (DTReg10k-R) e agente de sincronização (DTReg10k-L)
        plat = self.res.plataforma
        self.modo_rede = (roteiro.get("rede", {}).get("modo") or self.modo).upper()
        chave_rede = "ideal" if self.modo_rede == "IDEAL" else "realista"
        self.canal = Canal(dict(plat["canal"][chave_rede]), rng("canal"), self._agendar, self.reg)
        self.plataforma = Plataforma(self.reg, self.canal, plat, dict(plat["app"][chave_rede]), rng("plataforma"),
                                     self._agendar, cfgs[self.res.ids[0]], self.res.ids)
        p_agente = {**plat, "reconexao_jitter": plat["reconexao_jitter"][chave_rede]}
        self.agente = AgenteSincronizacao(self.hub, self.reg, self.canal, p_agente, rng("agente"), self.plataforma)
        self.plataforma.agente = self.agente
        self.hub.agente = self.agente
        self.acoes = sorted(roteiro.get("acoes", []), key=lambda a: a["t_ms"])
        self.falhas = sorted(roteiro.get("falhas", []), key=lambda f: f["t_ms"])
        self._ia = 0
        self._if = 0
        self._ultimos_presentes: tuple = ()
        self._ultimos_por_comodo: dict = {}
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

    def _verdade_luz(self, comodo: str):
        return lambda t, tipo, **dados: self._verdade(t, tipo, comodo=comodo, **dados)

    def _comutacao(self, comodo: str, atuador: str):
        def registrar(t: float, chave: str, ligado: bool) -> None:
            self.reg.add(ATUACAO, "COMUTACAO", t, origem=atuador, chave=chave, ligado=ligado, comodo=comodo)
        return registrar

    def _presentes(self) -> tuple:
        return tuple(sorted(o.id for o in self.ocupantes.values() if o.na_sala))

    def _dormindo(self) -> tuple:
        return tuple(sorted(o.id for o in self.ocupantes.values() if o.na_sala and o.dormindo))

    def _por_comodo(self) -> dict:
        return {cid: sorted(o.id for o in self.ocupantes.values() if o.comodo == cid) for cid in self.res.ids}

    def _alvo(self, f: dict, mapa: dict, padrao: str):
        """Dispositivo-alvo de uma falha: por 'dispositivo', por 'comodo' ou o padrão (1º cômodo)."""
        if f.get("dispositivo"):
            for d in mapa.values():
                if d.origem == f["dispositivo"]:
                    return d
            raise ValueError(f"{self.roteiro['id']}: dispositivo desconhecido {f['dispositivo']}")
        return mapa[f.get("comodo") or padrao]

    # -------------------------------------------------------------------- ações
    def _aplicar_acao(self, a: dict) -> None:
        if a["acao"] in ACOES_APP:
            self._acao_app(a)
            return
        o = self.ocupantes[a["ocupante"]]
        t = a["t_ms"]
        acao = a["acao"]
        v_andar, v_aleatorio = PERFIS[o.perfil]
        vel = float(a.get("vel_m_s", v_andar))
        if o.dormindo and acao not in ("DORMIR", "GESTO"):
            # nucleo-v1.3: qualquer outra ação acorda o ocupante
            o.dormindo = False
            self._verdade(t, "ACORDOU", ocupante=o.id, comodo=o.comodo)
        ext = self.res.externa
        if acao == "ENTRAR":
            if o.na_sala:
                raise ValueError(f"{self.roteiro['id']}: {o.id} já está na casa em t={t}")
            cid = ext.comodos[0]
            self._verdade(t, "CRUZOU_PORTA", ocupante=o.id, sentido="ENTRADA", vel_m_s=vel, comodo=cid, passagem=ext.id)
            self.sas[ext.sa].estimulo(t, vel)
            o.pos, o.comodo = ext.pontos[cid], cid
            o.modo, o.alvo, o.vel = "ANDAR", ext.alvo.get(cid, self.res.comodos[cid].centro()), min(vel, 1.5)
        elif acao == "SAIR":
            if not o.na_sala:
                raise ValueError(f"{self.roteiro['id']}: {o.id} não está na casa em t={t}")
            if o.comodo not in ext.comodos:
                raise ValueError(f"{self.roteiro['id']}: {o.id} está em {o.comodo} e só sai pela {ext.id} em t={t}")
            self._verdade(t, "CRUZOU_PORTA", ocupante=o.id, sentido="SAIDA", vel_m_s=vel, comodo=o.comodo, passagem=ext.id)
            self.sas[ext.sa].estimulo(t, vel)
            o.pos, o.modo, o.alvo, o.comodo = None, "FORA", None, None
        elif acao == "MUDAR_COMODO":
            ps = self.res.passagem_entre(o.comodo, a["para"]) if o.comodo else None
            if ps is None:
                raise ValueError(f"{self.roteiro['id']}: não há passagem de {o.comodo} para {a['para']} em t={t}")
            o.modo, o.alvo, o.vel = "PASSANDO", ps.pontos[o.comodo], vel
            o.destino = (ps, a["para"], tuple(a["ate"]) if a.get("ate") else None)
        elif acao == "ESPIAR":
            ps = self.res.passagem_entre(o.comodo, a["comodo"]) if o.comodo else None
            if ps is None:
                raise ValueError(f"{self.roteiro['id']}: não há passagem de {o.comodo} para {a['comodo']} em t={t}")
            self._verdade(t, "ESPIOU", ocupante=o.id, passagem=ps.id, de=o.comodo, comodo=a["comodo"])
            self.sas[ps.sa].estimulo(t, vel)
        elif acao == "ANDAR":
            o.modo, o.alvo, o.vel = "ANDAR", tuple(a["ate"]), vel
        elif acao == "ANDAR_ALEATORIO":
            o.modo, o.vel = "ALEATORIO", float(a.get("vel_m_s", v_aleatorio))
            o.area = tuple(a["area"]) if a.get("area") else None
            o.fim_ms = t + a["duracao_ms"]
            o.alvo = self.res.comodos[o.comodo].ponto_aleatorio(self.rng_mundo, o.area)
        elif acao == "PARADO":
            o.modo, o.alvo = "PARADO", None
        elif acao == "DORMIR":
            # nucleo-v1.3 (PI-01): imóvel, com microgestos raros; o ideal é a luz apagada
            if not o.na_sala:
                raise ValueError(f"{self.roteiro['id']}: {o.id} não está na casa para dormir em t={t}")
            o.modo, o.alvo, o.dormindo = "MICRO", None, True
            o.micro_intervalo = tuple(a.get("intervalo_ms", MICRO_DORMINDO))
            o.micro_prox = t + self.rng_mundo.randint(*o.micro_intervalo)
            self._verdade(t, "ADORMECEU", ocupante=o.id, comodo=o.comodo)
        elif acao == "ACORDAR":
            # já acordado acima; um gesto ao acordar
            o.modo, o.alvo = "PARADO", None
            o.gesto_ate = t + 2_000
        elif acao == "MICROGESTOS":
            o.modo, o.alvo = "MICRO", None
            o.micro_intervalo = (a.get("intervalo_min_ms", 120_000), a.get("intervalo_max_ms", 240_000))
            o.micro_prox = t + self.rng_mundo.randint(*o.micro_intervalo)
        elif acao == "GESTO":
            o.gesto_ate = t + a.get("duracao_ms", 1000)
            self._verdade(t, "GESTO", ocupante=o.id)
        elif acao == "PASSAR_PORTA_SEM_ENTRAR":
            self._verdade(t, "PASSOU_PORTA_SEM_ENTRAR", ocupante=o.id, passagem=ext.id)
            self.sas[ext.sa].estimulo(t, vel)
        elif acao == "INTERRUPTOR":
            cid = a.get("comodo") or o.comodo or self.res.ids[0]
            self._verdade(t, "INTERRUPTOR_ACIONADO", ocupante=o.id, comodo=cid)
            self.interruptores[cid].acionar(t)

    def _cruzar(self, t: int, o) -> None:
        """v1dt: o ocupante chegou ao vão e passa para o outro cômodo."""
        ps, para, ate = o.destino
        self._verdade(t, "CRUZOU_PASSAGEM", ocupante=o.id, passagem=ps.id, de=o.comodo, para=para, vel_m_s=o.vel)
        self.sas[ps.sa].estimulo(t, o.vel)
        o.comodo, o.pos = para, ps.pontos[para]
        o.modo, o.alvo = "ANDAR", ate or ps.alvo.get(para, self.res.comodos[para].centro())
        o.chegou_passagem, o.destino = False, None

    def _acao_app(self, a: dict) -> None:
        t = a["t_ms"]
        if a["acao"] == "APP_COMANDO":
            self.plataforma.app_comando(t, a["comando"], a.get("comodo"))
        elif a["acao"] == "APP_PREFERENCIA":
            par = {"t_apagamento_ms": a["t_apagamento_ms"]}
            if a.get("comodo"):
                par["comodo"] = a["comodo"]
            self.plataforma.app_preferencia(t, par)
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
        c0 = self.res.ids[0]
        if tipo == "SP_SEM_RESPOSTA":
            sp = self._alvo(f, self.sps, c0)
            sp.sem_resposta = True
            if f.get("duracao_ms"):
                self._agendar(t + f["duracao_ms"], lambda tt, sp=sp: setattr(sp, "sem_resposta", False))
        elif tipo == "BATERIA_BAIXA":
            self._alvo(f, self.sps, c0).bateria = f.get("nivel", 12)
        elif tipo == "SP_FALSO_DISPARO":
            self._alvo(f, self.sps, c0).forcar_disparo = True
        elif tipo == "SA_ESPURIO":
            self._alvo(f, self.sas, self.res.externa.sa).espurio(t)
        elif tipo == "SA_PERDE_PROXIMA":
            self._alvo(f, self.sas, self.res.externa.sa).perder_proxima = True
        elif tipo == "LAMPADA_QUEIMADA":
            self._alvo(f, self.lampadas, c0).queimar(t)
        elif tipo == "ATUADOR_TRAVADO":
            self._alvo(f, self.atuadores, c0).travado = True
        elif tipo == "HUB_REINICIO":
            self.hub.desligar(t)
            self._agendar(t + f.get("duracao_ms", 20_000),
                          lambda tt: self.hub.ligar(int(tt), {cid: l.fisica for cid, l in self.lampadas.items()}))
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
            o.comodo = item.get("comodo", self.res.ids[0])
            o.pos = tuple(item.get("pos", self.res.comodos[o.comodo].centro() if self.res.multi else (2.5, 2.0)))
            o.modo = "PARADO"
        self.reg.add(VERDADE, "INICIO", 0, roteiro=self.roteiro["id"], modo=self.modo, semente=self.semente,
                     controlador=self.hub.nome_controlador, ambiente=self.res.id, comodos=self.res.ids)
        self._verdade(0, "OCUPANTES", **self._ocupantes_verdade())
        for cid in self.res.ids:
            self._verdade(0, "LUZ_FISICA", acesa=False, comodo=cid)
        self._ultimos_presentes = (self._presentes(), self._por_comodo(), self._dormindo())
        vazia = lambda: {cid: {oid: {"movendo": False, "microgesto": False, "parado": False} for oid in self.ocupantes}
                         for cid in self.res.ids}
        janela = vazia()

        t = 0
        while t <= self.duracao:
            self._agora = t
            while self._if < len(self.falhas) and self.falhas[self._if]["t_ms"] <= t:
                self._aplicar_falha(self.falhas[self._if]); self._if += 1
            while self._ia < len(self.acoes) and self.acoes[self._ia]["t_ms"] <= t:
                self._aplicar_acao(self.acoes[self._ia]); self._ia += 1

            for o in self.ocupantes.values():
                comodo = self.res.comodos[o.comodo] if o.comodo else None
                mover(o, comodo, t, self.dt, self.rng_mundo)
                if o.chegou_passagem:
                    self._cruzar(t, o)
                    comodo = self.res.comodos[o.comodo]
                if comodo is not None and comodo.coberto_pelo_sp(o.pos):
                    j = janela[comodo.id][o.id]
                    if o.movendo:
                        j["movendo"] = True
                    elif o.microgesto:
                        j["microgesto"] = True
                    else:
                        j["parado"] = True

            for sa in self.sas.values():
                sa.passo(t, self.dt)
            for sp in self.sps.values():
                sp.passo(t)
            if t > 0 and t % 1000 == 0:
                for cid, sp in self.sps.items():
                    leituras = [dict(tipo=self.ocupantes[oid].tipo, **j) for oid, j in janela[cid].items()]
                    sp.janela(t, leituras)
                janela = vazia()

            while self.heap and self.heap[0][0] <= t:
                tt, _, fn = heapq.heappop(self.heap)
                fn(tt)

            self.hub.tick(t)
            self.hub.registrar_estado(t, periodico=(t % 1000 == 0))
            self.agente.tick(t)
            self.plataforma.tick(t)

            atual = (self._presentes(), self._por_comodo(), self._dormindo())
            if atual != self._ultimos_presentes:
                self._verdade(t, "OCUPANTES", **self._ocupantes_verdade())
                self._ultimos_presentes = atual
            if t % 1000 == 0:
                self._verdade(t, "POSICOES", ocupantes={
                    o.id: (None if o.pos is None else [round(o.pos[0], 2), round(o.pos[1], 2), int(o.movendo)])
                    for o in self.ocupantes.values()})
            t += self.dt

        self.reg.add(SISTEMA, "SINCRONIZACAO", self.duracao, modo_rede=self.modo_rede, canal=dict(self.canal.contagem),
                     hub=self.agente.balanco(), plataforma=self.plataforma.balanco())
        self.reg.add(SISTEMA, "FIM", self.duracao, entregas_ao_controlador=dict(self.hub.entregas),
                     entregas_por_comodo=self.hub.entregas_por_comodo)
        return self.reg

    def _ocupantes_verdade(self) -> dict:
        d = self._dormindo()
        # nucleo-v1.3: "dormindo" só aparece quando alguém dorme (registros antigos ficam iguais)
        return {"presentes": list(self._presentes()), "por_comodo": self._por_comodo(), **({"dormindo": list(d)} if d else {})}


def simular(sala_cfg: dict, roteiro: dict, fabrica_controlador, semente: int = 42, modo: str | None = None) -> Registro:
    return Simulacao(sala_cfg, roteiro, fabrica_controlador, semente, modo).executar()
