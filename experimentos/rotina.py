"""Gerador de rotina diária (nucleo-v1.4; plano v3dt.1 §3.2, DQ3-06).

Cada dia da família vira um roteiro com relógio de parede (`hora_inicio`). A
rotina é descrita num JSON do repositório da versão (por exemplo
`experimentos/rotina-familia.json`): para cada ocupante, onde começa e uma lista
de passos, cada um com a hora (`as`), a variação em minutos (`var`), o cômodo e
o que fazer. O gerador acrescenta a variação do dia (semente e dia), calcula o
caminho pelas passagens e espaça as trocas de cômodo pelo passo do perfil.

Passos (`fazer`):
- ``ANDAR``: anda pelo cômodo até o próximo passo;
- ``LER``: parado e acordado (ler, ver TV, jantar); reage quando a luz apaga;
- ``DORMIR``: dorme até o próximo passo (ou até o fim do dia);
- ``ENTRAR``: chega da rua pela porta externa, vai ao cômodo do passo e faz
  `depois` (padrão ``ANDAR``);
- ``SAIR``: vai até a porta externa e sai.

Os horários do dia mantêm a ordem dos passos, com pelo menos 3 min entre um e
outro. `prob` (0 a 1) torna o passo eventual: com a probabilidade complementar, o dia
não tem aquele passo.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Optional

PASSO_TROCA_MS = {"ADULTO": 12_000, "CRIANCA": 12_000, "IDOSO": 20_000, "CACHORRO": 10_000}
INTERVALO_MIN_MS = 180_000   # um passo dura pelo menos 3 min


def _rel(hhmm: str, t0: int) -> int:
    """Instante do passo relativo ao início do dia (passos depois da meia-noite caem no dia seguinte)."""
    t = _ms(hhmm) - t0
    return t + 86_400_000 if t < -43_200_000 else t


def _ms(hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":")[:2])
    return (h * 60 + m) * 60_000


def caminho(amb: dict, de: str, para: str) -> list[str]:
    """Cômodos a atravessar de `de` até `para` (sem `de`), pelo menor número de passagens internas."""
    viz: dict[str, list[str]] = {}
    for p in amb["passagens"]:
        if p["tipo"] == "INTERNA":
            a, b = p["comodos"]
            viz.setdefault(a, []).append(b)
            viz.setdefault(b, []).append(a)
    ant: dict[str, Optional[str]] = {de: None}
    fila = deque([de])
    while fila:
        c = fila.popleft()
        for n in sorted(viz.get(c, [])):
            if n not in ant:
                ant[n] = c
                fila.append(n)
    if para not in ant:
        raise ValueError(f"sem caminho de {de} para {para}")
    rota = []
    c: Optional[str] = para
    while c is not None and c != de:
        rota.append(c)
        c = ant[c]
    return rota[::-1]


def gerar_dia(amb: dict, rotina: dict, dia: int, semente: int, versao: str = "v3dt.1") -> dict:
    """Roteiro de um dia. A mesma (semente, dia) gera sempre o mesmo roteiro."""
    rng = random.Random(f"rotina:{semente}:{dia}")
    t0 = _ms(rotina["hora_inicio"])
    dur = int(rotina["duracao_h"] * 3_600_000)
    ext = next(p for p in amb["passagens"] if p["tipo"] == "EXTERNA")
    sala_ext = ext["comodos"][0]
    porta = ext["alvo"][sala_ext]
    perfis = {o["id"]: (o.get("perfil") or ("CACHORRO" if o["tipo"] == "CACHORRO" else "ADULTO")) for o in amb["ocupantes"]}
    acoes: list[dict] = []
    iniciais: list[dict] = []
    for oid in sorted(rotina["ocupantes"]):
        r = rotina["ocupantes"][oid]
        passo_troca = PASSO_TROCA_MS[perfis[oid]]
        onde: Optional[str] = r.get("comeca_em")
        if onde:
            iniciais.append({"id": oid, "comodo": onde})
        passos = [p for p in r["passos"] if rng.random() < p.get("prob", 1.0)]
        # horários do dia: variação sorteada e intervalo mínimo entre passos (a ordem da rotina se mantém)
        tempos: list[int] = []
        for p in passos:
            t = _rel(p["as"], t0) + rng.randint(-p.get("var", 0), p.get("var", 0)) * 60_000
            tempos.append(max(t, tempos[-1] + INTERVALO_MIN_MS if tempos else 1_000, 1_000))
        for i, p in enumerate(passos):
            t = tempos[i]
            if t >= dur - 60_000:
                break
            fim = min(tempos[i + 1] if i + 1 < len(passos) else dur, dur)
            a = lambda tt, acao, **k: acoes.append({"t_ms": int(tt), "ocupante": oid, "acao": acao, **k})
            fazer, destino = p["fazer"], p.get("comodo")
            if fazer == "ENTRAR":
                if onde is not None:
                    continue
                a(t, "ENTRAR")
                onde, t = sala_ext, t + 4_000
                fazer = p.get("depois", "ANDAR")
            elif fazer == "SAIR":
                if onde is None:
                    continue
                for c in caminho(amb, onde, sala_ext) if onde != sala_ext else []:
                    a(t, "MUDAR_COMODO", para=c)
                    t += passo_troca
                a(t, "ANDAR", ate=porta)
                a(t + 8_000, "SAIR")
                onde = None
                continue
            if onde is None:
                continue  # fora de casa: o passo não se aplica
            if destino and destino != onde:
                for c in caminho(amb, onde, destino):
                    a(t, "MUDAR_COMODO", para=c)
                    t += passo_troca
                onde = destino
            t += 2_000
            if fazer == "ANDAR":
                a(t, "ANDAR_ALEATORIO", duracao_ms=max(10_000, fim - t))
            elif fazer == "LER":
                a(t, "LER")
            elif fazer == "DORMIR":
                a(t, "DORMIR")
    acoes.sort(key=lambda x: (x["t_ms"], x["ocupante"]))
    return {"id": f"D{dia:02d}", "versao": versao, "ambiente": rotina["ambiente"], "modo": rotina.get("modo", "IDEAL"),
            "titulo": f"Dia {dia} da rotina da família", "tipo": "ROTINA", "duracao_ms": dur,
            "hora_inicio": rotina["hora_inicio"],
            "descricao": f"Rotina gerada (semente {semente}, dia {dia}) de {rotina['hora_inicio']} por {rotina['duracao_h']} h",
            "estado_inicial": {"ocupantes_na_sala": iniciais, "luz": "APAGADA"}, "falhas": [], "acoes": acoes}
