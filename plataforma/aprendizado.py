"""Aprendizado do gêmeo remoto (nucleo-v1.4; plano v3dt.1 §3, DQ3-04 a DQ3-08).

Quem aprende é o DTReg10k-R, só com o que já recebe do hub (camada PLATAFORMA):
o estado de cada cômodo (ESTADO_REMOTO) e as evidências que chegam
(EVIDENCIA_RECEBIDA). Os sensores não identificam pessoas (RN09), e o modelo
também não: ele guarda só contagens agregadas por **cômodo e hora do dia**, com
retenção de 30 dias (V2/V3 §2.8). Nada aqui conhece a camada VERDADE.

O que se observa, por apagamento automático de um cômodo:

- **apagamento com alguém dentro**: depois da última passagem pelo cômodo, o PIR
  ainda viu movimento ali (mais de `MARGEM_PASSAGEM_MS` depois). Quem passou e
  saiu não conta;
- **reação**: o PIR vê movimento no cômodo até `JANELA_REACAO_MS` depois do
  apagamento, sem passagem no meio. Alguém parado e acordado reagiu ao escuro;
- **imóvel**: nenhum movimento nem passagem no cômodo por `JANELA_IMOVEL_MS`
  depois do apagamento. Provavelmente alguém dormindo.

Sugestões (regras simples e explicáveis, para o titular decidir):

- `reacoes / apagamentos ≥ LIMIAR_REACAO` → T_apagamento longo (`T_LONGO_MS`);
- `imoveis / apagamentos ≥ LIMIAR_IMOVEL` e nenhuma reação → T_apagamento curto
  (`T_CURTO_MS`, o mínimo da política);
- só com pelo menos `MIN_DIAS` dias e `MIN_APAGAMENTOS` apagamentos naquela hora;
- horas seguidas com a mesma sugestão viram uma faixa.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

MARGEM_PASSAGEM_MS = 10_000
JANELA_REACAO_MS = 30_000
JANELA_IMOVEL_MS = 600_000
LIMIAR_REACAO = 0.5
LIMIAR_IMOVEL = 0.8
MIN_DIAS = 5
MIN_APAGAMENTOS = 5
T_LONGO_MS = 300_000
T_CURTO_MS = 30_000
RETENCAO_DIAS = 30
CAMPOS = ("apagamentos", "reacoes", "imoveis")


class ModeloOcupacao:
    """Perfil agregado por (cômodo, hora): contagens por dia, sem identificar ninguém."""

    def __init__(self, retencao_dias: int = RETENCAO_DIAS):
        self.retencao = retencao_dias
        # dia → (cômodo, hora) → contagens
        self.dias: dict[int, dict[tuple[str, int], dict[str, int]]] = {}

    # ---------------------------------------------------------- observação
    def observar_dia(self, dia: int, eventos: Iterable[dict], hora_inicio_ms: int) -> dict:
        """Lê os eventos da camada PLATAFORMA de um dia e guarda só as contagens."""
        plat = [e for e in eventos if e.get("camada") == "PLATAFORMA"]
        luz: dict[str, Optional[str]] = {}
        apagamentos: list[tuple[str, int]] = []
        passagens: dict[str, list[int]] = defaultdict(list)
        movimentos: dict[str, list[int]] = defaultdict(list)
        for e in plat:
            if e["tipo"] == "ESTADO_REMOTO" and e.get("comodo"):
                c = e["comodo"]
                if luz.get(c) == "ACESA_AUTO" and e.get("luz") == "APAGADA":
                    apagamentos.append((c, e["t_ms"]))
                luz[c] = e.get("luz")
            elif e["tipo"] == "EVIDENCIA_RECEBIDA":
                t = e.get("t_origem_ms", e["t_ms"])
                for c in e.get("comodos") or []:
                    if e.get("evidencia") == "PASSAGEM":
                        passagens[c].append(t)
                    elif e.get("evidencia") == "MOVIMENTO":
                        movimentos[c].append(t)
        fim = max((e["t_ms"] for e in plat), default=0)
        cont: dict[tuple[str, int], dict[str, int]] = {}
        for c, t in apagamentos:
            ult_pass = max((x for x in passagens[c] if x <= t), default=None)
            ult_mov = max((x for x in movimentos[c] if x <= t), default=None)
            if ult_mov is None or (ult_pass is not None and ult_mov < ult_pass + MARGEM_PASSAGEM_MS):
                continue  # passou e saiu, ou ninguém foi visto parado ali
            hora = (hora_inicio_ms + t) // 3_600_000 % 24
            k = cont.setdefault((c, hora), dict.fromkeys(CAMPOS, 0))
            k["apagamentos"] += 1
            prox_pass = min((x for x in passagens[c] if x > t), default=None)
            prox_mov = min((x for x in movimentos[c] if x > t), default=None)
            if prox_mov is not None and prox_mov - t <= JANELA_REACAO_MS and (prox_pass is None or prox_mov < prox_pass):
                k["reacoes"] += 1
            elif (prox_mov is None or prox_mov - t >= JANELA_IMOVEL_MS) and \
                    (prox_pass is None or prox_pass - t >= JANELA_IMOVEL_MS) and fim - t >= JANELA_IMOVEL_MS:
                k["imoveis"] += 1
        self.dias[dia] = cont
        for velho in [d for d in self.dias if d <= dia - self.retencao]:
            del self.dias[velho]   # retenção de 30 dias (DQ3-08)
        return cont

    # ------------------------------------------------------------ consulta
    def perfil(self) -> dict[tuple[str, int], dict[str, int]]:
        tot: dict[tuple[str, int], dict[str, int]] = {}
        for cont in self.dias.values():
            for k, v in cont.items():
                acc = tot.setdefault(k, {**dict.fromkeys(CAMPOS, 0), "dias": 0})
                for c in CAMPOS:
                    acc[c] += v[c]
                acc["dias"] += 1 if v["apagamentos"] else 0
        return tot

    def exportar(self) -> dict:
        """Forma persistida do modelo: só cômodo, hora e contagens (sem nada por ocupante)."""
        return {"retencao_dias": self.retencao,
                "dias": {str(d): {f"{c}|{h:02d}": v for (c, h), v in cont.items()} for d, cont in self.dias.items()}}

    def sugestoes(self, t_base_ms: dict[str, int]) -> list[dict]:
        """Sugestões de T_apagamento por cômodo e faixa, com a evidência de cada uma."""
        propostas: dict[tuple[str, int], tuple[int, dict]] = {}
        for (c, h), v in self.perfil().items():
            if v["dias"] < MIN_DIAS or v["apagamentos"] < MIN_APAGAMENTOS:
                continue
            ap = v["apagamentos"]
            if v["reacoes"] / ap >= LIMIAR_REACAO:
                alvo = T_LONGO_MS
            elif v["reacoes"] == 0 and v["imoveis"] / ap >= LIMIAR_IMOVEL:
                alvo = T_CURTO_MS
            else:
                continue
            if alvo != t_base_ms.get(c):
                propostas[(c, h)] = (alvo, v)
        saida = []
        for c in sorted({c for c, _ in propostas}):
            horas = sorted(h for cc, h in propostas if cc == c)
            grupo: list[int] = []
            for h in horas + [None]:
                if grupo and (h is None or h != (grupo[-1] + 1) % 24 or propostas[(c, h)][0] != propostas[(c, grupo[0])][0]):
                    saida.append(_faixa(c, grupo, propostas))
                    grupo = []
                if h is not None:
                    grupo.append(h)
        return saida


def _faixa(c: str, horas: list[int], propostas: dict) -> dict:
    alvo = propostas[(c, horas[0])][0]
    ev = {k: sum(propostas[(c, h)][1][k] for h in horas) for k in CAMPOS}
    ev["dias"] = max(propostas[(c, h)][1]["dias"] for h in horas)
    de, ate = f"{horas[0]:02d}:00", f"{(horas[-1] + 1) % 24:02d}:00"
    if alvo == T_LONGO_MS:
        motivo = (f"em {ev['reacoes']} de {ev['apagamentos']} apagamentos com alguém dentro, houve movimento logo "
                  "depois: alguém parado e acordado ficou no escuro")
        efeito = "menos apagamentos com gente acordada; mais tempo aceso depois que o cômodo esvazia"
    else:
        motivo = (f"em {ev['imoveis']} de {ev['apagamentos']} apagamentos com alguém dentro, ninguém se mexeu por "
                  "10 min e nunca houve reação: provavelmente alguém dormindo")
        efeito = "menos tempo aceso com quem dorme; quem estiver acordado e parado fica no escuro mais cedo"
    return {"id": f"SUG-{c}-{de[:2]}-{ate[:2]}", "comodo": c, "de": de, "ate": ate, "t_apagamento_ms": alvo,
            "evidencia": ev, "motivo": motivo, "efeito": efeito}
