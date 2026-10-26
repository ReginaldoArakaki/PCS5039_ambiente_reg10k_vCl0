"""Execução de cenários e geração do catálogo (plano §8 e §12)."""
from __future__ import annotations

import importlib
import json
import pkgutil
import statistics
from pathlib import Path
from typing import Callable, Iterable, Optional

from avaliacao.espelho import salvar_amostras
from avaliacao.oraculo import avaliar, roteiro_sem_rede, tem_app, tem_falha_de_rede
from hub.controlador import Controlador, ControladorReferencia
from sim.motor import simular

RAIZ = Path(__file__).resolve().parent.parent
CENARIOS = RAIZ / "cenarios"
SAIDA = RAIZ / "saida"
SEMENTE_REFERENCIA = 42
METRICAS_NUMERICAS = (
    "desperdicio_s", "escuro_com_ocupante_s", "apagamentos_indevidos", "acionamentos",
    "latencia_reacao_ms_p95", "atraso_percebido_ms_max", "desperdicio_por_saida_s_max",
    "ocupacao_desconhecida_s",
    # v0dt
    "atualidade_gemeo_ms_p95", "comando_remoto_ms_p95", "comandos_vencidos_executados",
    "efeitos_duplicados_remotos", "reconciliacao_ms_max", "divergencia_alem_prazo_s",
    # v0dta
    "espelho_fiel_s", "erro_de_percepcao_s", "erro_de_sincronizacao_s", "espelho_nao_afirma_s",
)
VERSAO = "v0dta"


# --------------------------------------------------------------- carregamento
def ler_json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_sala() -> dict:
    return ler_json(CENARIOS / "sala.json")


def carregar_roteiros(ids: Optional[Iterable[str]] = None) -> list[dict]:
    todos = [ler_json(p) for p in sorted((CENARIOS / "roteiros").glob("*.json"))]
    ordem = {"NORMAL": 0, "FALSO_POSITIVO": 1, "FALSO_NEGATIVO": 2, "FALHA": 3, "GEMEO_DIGITAL": 4}
    todos.sort(key=lambda r: (ordem.get(r["tipo"], 9), r["id"]))
    if ids:
        ids = set(ids)
        todos = [r for r in todos if r["id"] in ids]
    return todos


def carregar_esperado(cid: str) -> Optional[dict]:
    p = CENARIOS / "esperado" / f"{cid}.json"
    return ler_json(p) if p.exists() else None


def carregar_controlador(spec: str) -> Callable[[], object]:
    """'referencia', 'alunos.grupo3' ou 'pacote.modulo:Classe'."""
    if spec in ("referencia", "ref"):
        return ControladorReferencia
    if ":" in spec:
        mod, cls = spec.split(":", 1)
        fab = getattr(importlib.import_module(mod), cls)
    else:
        fab = getattr(importlib.import_module(spec), "Controlador")
    inst = fab()
    if not isinstance(inst, Controlador):
        raise TypeError(f"{spec} não implementa a interface Controlador (hub/controlador.py)")
    return fab


def descobrir_controladores() -> dict[str, Callable[[], object]]:
    """Referência mais todo pacote em alunos/ que exporte `Controlador`."""
    achados: dict[str, Callable[[], object]] = {"referencia": ControladorReferencia}
    pasta = RAIZ / "alunos"
    for m in sorted(pkgutil.iter_modules([str(pasta)]), key=lambda m: m.name):
        if not m.ispkg:
            continue
        fab = carregar_controlador(f"alunos.{m.name}")
        nome = getattr(fab, "nome", m.name)
        achados[nome] = fab
    return achados


# ------------------------------------------------------------------ execução
def executar(roteiro: dict, fabrica, semente: int = SEMENTE_REFERENCIA, sala: Optional[dict] = None,
             salvar: bool = True) -> dict:
    sala = sala or carregar_sala()
    reg = simular(sala, roteiro, fabrica, semente)
    nome = getattr(fabrica, "nome", "controlador")
    esperado = carregar_esperado(roteiro["id"])
    # OR-12: execução pareada sem falhas de rede (só faz sentido sem ações do app)
    par = None
    if tem_falha_de_rede(roteiro) and not tem_app(roteiro):
        par = simular(sala, roteiro_sem_rede(roteiro), fabrica, semente).eventos
    av = avaliar(reg.eventos, roteiro, sala, esperado, par)
    resumo = {
        "cenario": roteiro["id"],
        "controlador": nome,
        "semente": semente,
        "modo": roteiro.get("modo", "IDEAL"),
        "modo_rede": (roteiro.get("rede", {}).get("modo") or roteiro.get("modo", "IDEAL")).upper(),
        "versao_cenario": roteiro.get("versao", "v0"),
        "execucao_pareada": par is not None,
        "hash_eventos": reg.hash(),
        "n_eventos": len(reg.eventos),
        **av,
    }
    if salvar:
        pasta = SAIDA / roteiro["id"] / nome / str(semente)
        reg.salvar(pasta / "eventos.jsonl")
        salvar_amostras(pasta / "espelho", sala, roteiro, nome, av["espelho"]["amostras"])  # v0dta
        (pasta / "metricas.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo["_eventos"] = reg.eventos
    return resumo


def distribuicao(roteiro: dict, fabrica, n: int, sala: dict) -> dict:
    """Modo realista: métricas de n sementes (plano §10.2)."""
    por_metrica: dict[str, list[float]] = {k: [] for k in METRICAS_NUMERICAS}
    for s in range(1, n + 1):
        m = avaliar(simular(sala, roteiro, fabrica, s).eventos, roteiro, sala, None)["metricas"]
        for k in METRICAS_NUMERICAS:
            if m.get(k) is not None:
                por_metrica[k].append(m[k])
    saida = {}
    for k, xs in por_metrica.items():
        if not xs:
            continue
        xs = sorted(xs)
        saida[k] = {
            "n": len(xs), "min": xs[0], "media": round(statistics.fmean(xs), 2),
            "mediana": statistics.median(xs), "p95": xs[max(0, int(0.95 * len(xs) + 0.999) - 1)], "max": xs[-1],
        }
    return saida


def gerar_catalogo(controladores: dict[str, Callable[[], object]], ids=None, n_sementes: int = 30,
                   verificar_determinacao: bool = True, log=print) -> dict:
    sala = carregar_sala()
    roteiros = carregar_roteiros(ids)
    execucoes: list[dict] = []
    problemas: list[str] = []
    for r in roteiros:
        for nome, fab in controladores.items():
            res = executar(r, fab, SEMENTE_REFERENCIA, sala)
            if verificar_determinacao:
                h2 = simular(sala, r, fab, SEMENTE_REFERENCIA).hash()
                res["determinismo_ok"] = h2 == res["hash_eventos"]
                if not res["determinismo_ok"]:
                    problemas.append(f"{r['id']}/{nome}: execução não determinística")
            realista = r.get("modo") == "REALISTA" or r.get("rede", {}).get("modo") == "REALISTA"
            if realista and n_sementes > 0:
                res["distribuicao"] = distribuicao(r, fab, n_sementes, sala)
            inv_falhas = [k for k, v in res["invariantes"].items() if not v["ok"]]
            if inv_falhas:
                problemas.append(f"{r['id']}/{nome}: invariantes violadas {inv_falhas}")
            if nome == "referencia" and not all(a["ok"] for a in res["assercoes"].values()):
                problemas.append(f"{r['id']}/referencia: asserções falharam")
            rq, ca = res["requisitos"], res["caracterizacao"]
            log(f"  {r['id']:5} {nome:16} requisitos {rq['ok']}/{rq['total']}  "
                f"igual à ref. {ca['igual_referencia']}/{ca['total']}  "
                f"invariantes {'ok' if not inv_falhas else 'FALHA'}  "
                f"desperdício {res['metricas']['desperdicio_s']:>7} s  "
                f"escuro {res['metricas']['escuro_com_ocupante_s']:>7} s  "
                f"indevidos {res['metricas']['apagamentos_indevidos']}")
            execucoes.append(res)
    catalogo = {
        "versao": VERSAO,
        "incremento": 1,
        "sala": sala,
        "cenarios": [
            {"versao": r.get("versao", "v0"),
             **{k: r[k] for k in ("id", "titulo", "tipo", "modo", "duracao_ms", "descricao",
                                  "comportamento_ideal", "comportamento_referencia", "requisitos", "regras", "rede", "amostras_ms")
                if k in r},
             "esperado": carregar_esperado(r["id"])}
            for r in roteiros
        ],
        "controladores": list(controladores),
        "execucoes": [{k: v for k, v in e.items() if k != "_eventos"} for e in execucoes],
        "problemas": problemas,
    }
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    catalogo["_eventos"] = {(e["cenario"], e["controlador"]): e["_eventos"] for e in execucoes}
    catalogo["_roteiros"] = {r["id"]: r for r in roteiros}
    return catalogo
