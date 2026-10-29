"""Protocolo do aprendizado do gêmeo (nucleo-v1.4; plano v3dt.1 §3.2 e §3.3).

Para cada semente:

1. **Treino** (dias 1 a N): a rotina da família roda dia a dia; o gêmeo remoto
   (DTReg10k-R) observa a camada PLATAFORMA de cada dia e guarda o perfil
   agregado (`plataforma.aprendizado.ModeloOcupacao`). Cada dia é uma execução
   separada, e o modelo passa de um dia para o outro, como na plataforma.
2. **Sugestões**: ao fim do treino, o gêmeo propõe T_apagamento por cômodo e
   faixa horária.
3. **Teste** (dias N+1 a N+M), em dois braços com as mesmas rotinas e sementes:
   ``aceitar`` (o titular aceita no app, no primeiro dia de teste, o que a
   política escolher: por padrão, todas; `--politica`) e ``recusar`` (recusa
   tudo; é o controle). O que muda entre os braços é só a
   decisão do titular.

Medidas por cômodo e hora, tiradas da camada VERDADE (o oráculo é o único que a
lê): escuro com alguém acordado, aceso com todos dormindo, aceso sem ninguém e
apagamentos com alguém acordado. O cachorro não conta como "alguém".

Uso, na raiz do repositório da versão:
    python nucleo/reg10k.py aprendizado --rotina experimentos/rotina-familia.json --sementes 10
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path
from typing import Optional

NUCLEO = Path(__file__).resolve().parent.parent
if str(NUCLEO) not in sys.path:
    sys.path.insert(0, str(NUCLEO))

from experimentos.rotina import gerar_dia  # noqa: E402
from plataforma.aprendizado import ModeloOcupacao  # noqa: E402

MEDIDAS = ("escuro_acordado_s", "aceso_dormindo_s", "aceso_vazio_s", "apagamentos_acordado")
RESSALVA = "Resultados de simulação, não de medição (P7): valem para o modelo, a rotina e os parâmetros declarados."


# ------------------------------------------------------------------ medidas
def medir_dia(eventos: list[dict], amb: dict, hora_inicio_ms: int, duracao_ms: int) -> dict:
    """(cômodo, hora) → medidas, a partir da verdade (luz física e ocupantes)."""
    pessoas = {o["id"] for o in amb["ocupantes"] if o["tipo"] == "PESSOA"}
    comodos = [c["id"] for c in amb["comodos"]]
    luz = dict.fromkeys(comodos, False)
    dentro: dict[str, set] = {c: set() for c in comodos}
    dormindo: set = set()
    out: dict[tuple[str, int], dict] = {}

    def acc(c: str, h: int) -> dict:
        return out.setdefault((c, h), dict.fromkeys(MEDIDAS, 0.0))

    def situacao(c: str) -> str:
        ps = dentro[c] & pessoas
        if not ps:
            return "VAZIO"
        return "DORMINDO" if ps <= dormindo else "ACORDADO"

    def avancar(t0: int, t1: int) -> None:
        t = t0
        while t < t1:
            h_abs = hora_inicio_ms + t
            prox_hora = (h_abs // 3_600_000 + 1) * 3_600_000 - hora_inicio_ms
            fim = min(t1, prox_hora)
            h = h_abs // 3_600_000 % 24
            for c in comodos:
                s = situacao(c)
                d = (fim - t) / 1000
                if not luz[c] and s == "ACORDADO":
                    acc(c, h)["escuro_acordado_s"] += d
                elif luz[c] and s == "DORMINDO":
                    acc(c, h)["aceso_dormindo_s"] += d
                elif luz[c] and s == "VAZIO":
                    acc(c, h)["aceso_vazio_s"] += d
            t = fim

    agora = 0
    for e in eventos:
        if e["camada"] != "VERDADE" or e["tipo"] not in ("LUZ_FISICA", "OCUPANTES"):
            continue
        avancar(agora, e["t_ms"])
        agora = e["t_ms"]
        if e["tipo"] == "LUZ_FISICA":
            c = e["comodo"]
            if luz[c] and not e["acesa"] and situacao(c) == "ACORDADO":
                acc(c, (hora_inicio_ms + agora) // 3_600_000 % 24)["apagamentos_acordado"] += 1
            luz[c] = e["acesa"]
        else:
            for c in comodos:
                dentro[c] = set(e.get("por_comodo", {}).get(c, []))
            dormindo = set(e.get("dormindo", []))
    avancar(agora, duracao_ms)
    return out


# ------------------------------------------------------------------ execução
def escolher(sugestoes: list, politica: str, t_base: dict) -> list:
    """Sugestões que o titular aceita no braço "aceitar" (as demais ele recusa).

    `politica`: ``todas``; ``longas`` (só as que aumentam o T_apagamento); ``curtas`` (só as que diminuem);
    ou ``comodos:sala,quarto`` (só as desses cômodos). E15.2: troque pela sua escolha.
    """
    if politica == "todas":
        return list(sugestoes)
    if politica == "longas":
        return [s for s in sugestoes if s["t_apagamento_ms"] > t_base.get(s["comodo"], 60_000)]
    if politica == "curtas":
        return [s for s in sugestoes if s["t_apagamento_ms"] < t_base.get(s["comodo"], 60_000)]
    if politica.startswith("comodos:"):
        alvo = set(politica.split(":", 1)[1].split(","))
        return [s for s in sugestoes if s["comodo"] in alvo]
    raise ValueError(f"política desconhecida: {politica}")


def _dia(amb: dict, rot: dict, semente: int, dia: int, estado: dict, sugestoes: list, decisao: Optional[dict]):
    from hub.controlador import ControladorReferencia
    from avaliacao.residencia import avaliar_residencia
    from sim.motor import simular
    from sim.residencia import Residencia
    r = gerar_dia(amb, rot, dia, semente)
    if estado["faixas"]:
        r["config_inicial"] = {"versao": estado["versao"], "faixas": estado["faixas"],
                               "sugestoes_aceitas": estado["aceitas"]}
    if sugestoes:
        r["sugestoes"] = sugestoes
        if decisao:
            aceitas = decisao["aceitar"]
            recusadas = [s["id"] for s in sugestoes if s["id"] not in aceitas]
            if aceitas:
                r["acoes"].append({"t_ms": 60_000, "ocupante": "app", "acao": "APP_ACEITAR", "sugestoes": aceitas})
            if recusadas:
                r["acoes"].append({"t_ms": 61_000, "ocupante": "app", "acao": "APP_RECUSAR", "sugestoes": recusadas})
            r["acoes"].sort(key=lambda a: a["t_ms"])
    reg = simular(amb, r, ControladorReferencia, semente * 1000 + dia)
    ev = reg.eventos
    av = avaliar_residencia(ev, r, Residencia(amb), None, None)
    inv_falhas = [k for k, v in av["invariantes"].items() if not v["ok"]]
    medidas = medir_dia(ev, amb, reg.hora_inicio_ms, r["duracao_ms"])
    novo = dict(estado)
    aplicadas = [e for e in ev if e["camada"] == "SISTEMA" and e["tipo"] == "CONFIG_APLICADA" and e.get("faixas")]
    if aplicadas:
        ult = aplicadas[-1]
        novo = {"versao": ult["versao"], "faixas": ult["faixas"],
                "aceitas": sorted(set(estado["aceitas"]) | {e["sugestao"] for e in ev if e["camada"] == "PLATAFORMA"
                                                            and e["tipo"] == "SUGESTAO" and e["estado"] == "ACEITA"})}
    plat = [e for e in ev if e["camada"] == "PLATAFORMA"]
    return {"medidas": medidas, "invariantes_falhas": inv_falhas, "estado": novo, "plataforma": plat,
            "hora_inicio_ms": reg.hora_inicio_ms, "or17": av["invariantes"]["OR-17"],
            "metricas": {k: av["metricas"].get(k) for k in ("desperdicio_s", "escuro_com_ocupante_s",
                                                             "apagamentos_indevidos", "luz_com_todos_dormindo_s")}}


def rodar_semente(args) -> dict:
    amb, rot, semente, treino, teste, politica = args
    t_base = {c["id"]: {**amb.get("controle", {}), **c.get("controle", {})}.get("t_apagamento_ms", 60_000)
              for c in amb["comodos"]}
    modelo = ModeloOcupacao()
    estado = {"versao": 1, "faixas": {}, "aceitas": []}
    linhas, dias = [], []
    for dia in range(1, treino + 1):
        d = _dia(amb, rot, semente, dia, estado, [], None)
        modelo.observar_dia(dia, d["plataforma"], d["hora_inicio_ms"])
        linhas += _linhas(semente, "treino", dia, d)
        dias.append(_resumo(semente, "treino", dia, d))
    sugestoes = modelo.sugestoes(t_base)
    escolhidas = [s["id"] for s in escolher(sugestoes, politica, t_base)]
    for braco in ("aceitar", "recusar"):
        est = dict(estado)
        decisao = {"aceitar": escolhidas if braco == "aceitar" else []}
        for dia in range(treino + 1, treino + teste + 1):
            primeiro = dia == treino + 1
            d = _dia(amb, rot, semente, dia, est, sugestoes if primeiro else [], decisao if primeiro else None)
            est = d["estado"]
            linhas += _linhas(semente, braco, dia, d)
            dias.append(_resumo(semente, braco, dia, d))
    return {"semente": semente, "linhas": linhas, "dias": dias, "sugestoes": sugestoes, "aceitas": escolhidas,
            "modelo": modelo.exportar()}


def _linhas(semente: int, braco: str, dia: int, d: dict) -> list[dict]:
    return [{"semente": semente, "braco": braco, "dia": dia, "comodo": c, "hora": h,
             **{k: round(v, 1) for k, v in m.items()}} for (c, h), m in sorted(d["medidas"].items())]


def _resumo(semente: int, braco: str, dia: int, d: dict) -> dict:
    return {"semente": semente, "braco": braco, "dia": dia, "invariantes_ok": not d["invariantes_falhas"],
            "invariantes_falhas": d["invariantes_falhas"], "or17_aplica": d["or17"].get("aplica", True),
            "versao_config": d["estado"]["versao"], **d["metricas"]}


# -------------------------------------------------------------------- resumo
def resumir(linhas: list[dict], treino: int) -> list[dict]:
    """Média por dia de teste, por cômodo e hora, nos dois braços, e a diferença (aceitar − recusar)."""
    soma: dict[tuple, dict] = {}
    n_dias: dict[str, set] = {}
    for r in linhas:
        if r["braco"] == "treino":
            continue
        n_dias.setdefault(r["braco"], set()).add((r["semente"], r["dia"]))
        k = (r["comodo"], r["hora"], r["braco"])
        acc = soma.setdefault(k, dict.fromkeys(MEDIDAS, 0.0))
        for m in MEDIDAS:
            acc[m] += r[m]
    saida = []
    for (c, h) in sorted({(c, h) for c, h, _ in soma}, key=lambda x: (x[0], (x[1] - 12) % 24)):
        lin = {"comodo": c, "hora": f"{h:02d}h"}
        for m in MEDIDAS:
            a = soma.get((c, h, "aceitar"), {}).get(m, 0.0) / max(1, len(n_dias.get("aceitar", ())))
            b = soma.get((c, h, "recusar"), {}).get(m, 0.0) / max(1, len(n_dias.get("recusar", ())))
            lin[f"{m}_aceitar"], lin[f"{m}_recusar"], lin[f"{m}_dif"] = round(a, 1), round(b, 1), round(a - b, 1)
        saida.append(lin)
    return saida


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Protocolo de aprendizado do gêmeo (nucleo-v1.4, v3dt.1)")
    ap.add_argument("--raiz", default=None, help="pasta do repositório da versão (padrão: a atual)")
    ap.add_argument("--rotina", default="experimentos/rotina-familia.json")
    ap.add_argument("--sementes", type=int, default=10)
    ap.add_argument("--primeira", type=int, default=0, help="primeira semente")
    ap.add_argument("--treino", type=int, default=14)
    ap.add_argument("--teste", type=int, default=7)
    ap.add_argument("--processos", type=int, default=2)
    ap.add_argument("--politica", default="todas",
                    help="o que o titular aceita no braço 'aceitar': todas, longas, curtas ou comodos:sala,quarto (E15.2)")
    ap.add_argument("--saida", default=None, help="prefixo dos arquivos (padrão: dados/aprendizado-<versão>-<data>)")
    a = ap.parse_args(argv)
    import os
    raiz = Path(a.raiz or os.environ.get("REG10K_RAIZ") or ".").resolve()
    rot = json.loads((raiz / a.rotina).read_text(encoding="utf-8"))
    amb_path = raiz / "ambiente" / f"{rot['ambiente']}.json"
    amb = json.loads(amb_path.read_text(encoding="utf-8"))
    versao = json.loads((raiz / "versao.json").read_text(encoding="utf-8"))["nome"] if (raiz / "versao.json").exists() else "nucleo"
    prefixo = Path(a.saida) if a.saida else raiz / "dados" / f"aprendizado-{versao}-{date.today():%Y%m%d}"
    prefixo.parent.mkdir(parents=True, exist_ok=True)
    sementes = list(range(a.primeira, a.primeira + a.sementes))
    t0 = time.time()
    tarefas = [(amb, rot, s, a.treino, a.teste, a.politica) for s in sementes]
    if a.processos > 1:
        with ProcessPoolExecutor(a.processos) as ex:
            res = list(ex.map(rodar_semente, tarefas))
    else:
        res = [rodar_semente(t) for t in tarefas]
    linhas = [l for r in res for l in r["linhas"]]
    dias = [d for r in res for d in r["dias"]]
    resumo = resumir(linhas, a.treino)
    _csv(prefixo.with_suffix(".csv"), linhas)
    _csv(prefixo.parent / (prefixo.name + "-dias.csv"), dias)
    _csv(prefixo.parent / (prefixo.name + "-resumo.csv"), resumo)
    (prefixo.parent / (prefixo.name + "-sugestoes.json")).write_text(json.dumps(
        {str(r["semente"]): {"sugestoes": r["sugestoes"], "aceitas": r["aceitas"], "modelo": r["modelo"]} for r in res},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    import catalogo.executar as ex
    from experimentos.rodar import _git
    manifesto = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "comando": " ".join(sys.argv),
                 "protocolo": {"treino_dias": a.treino, "teste_dias": a.teste, "sementes": sementes,
                               "bracos": ["aceitar", "recusar"], "politica_de_aceite": a.politica,
                               "controlador": "referencia",
                               "janela": f"{rot['hora_inicio']} por {rot['duracao_h']} h", "modo": rot.get("modo", "IDEAL")},
                 "entradas": {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (raiz / a.rotina, amb_path)},
                 "versao": ex.identidade(),
                 "nucleo": {"nome": ex.VERSAO, "commit": _git(NUCLEO, "rev-parse", "HEAD"),
                            "descricao_git": _git(NUCLEO, "describe", "--tags", "--always", "--dirty")},
                 "repositorio_versao": {"commit": _git(raiz, "rev-parse", "HEAD"),
                                        "descricao_git": _git(raiz, "describe", "--tags", "--always", "--dirty")},
                 "dias_simulados": len(dias), "duracao_s": round(time.time() - t0, 1),
                 "invariantes_ok_em_todos_os_dias": all(d["invariantes_ok"] for d in dias), "ressalva": RESSALVA}
    (prefixo.parent / (prefixo.name + ".manifesto.json")).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _imprimir(res, dias, resumo, a.treino)
    print(f"\nArquivos: {prefixo}.csv, -dias.csv, -resumo.csv, -sugestoes.json e .manifesto.json")
    print(RESSALVA)
    return 0


def _csv(p: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        for l in linhas:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in l.items()})


def _imprimir(res: list, dias: list, resumo: list, treino: int) -> None:
    print(f"{len(dias)} dias simulados; invariantes respeitadas em todos: {all(d['invariantes_ok'] for d in dias)}")
    for r in res:
        print(f"semente {r['semente']}: " + "; ".join(f"{s['comodo']} {s['de']}–{s['ate']} → {s['t_apagamento_ms'] // 1000} s"
                                                      for s in r["sugestoes"]))
    print("\nPor dia de teste (média), aceitar × recusar:")
    tot = {m: [0.0, 0.0] for m in MEDIDAS}
    for l in resumo:
        for m in MEDIDAS:
            tot[m][0] += l[f"{m}_aceitar"]
            tot[m][1] += l[f"{m}_recusar"]
    for m, (x, y) in tot.items():
        print(f"  {m:24s} aceitar {x:9.1f}   recusar {y:9.1f}   diferença {x - y:+9.1f}")


if __name__ == "__main__":
    raise SystemExit(main())
