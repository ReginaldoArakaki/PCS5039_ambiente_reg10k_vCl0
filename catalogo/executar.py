"""Execução de cenários e geração do catálogo (plano §8 e §12)."""
from __future__ import annotations

import importlib
import json
import os
import pkgutil
import statistics
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional

from avaliacao.espelho import salvar_amostras
from avaliacao.oraculo import avaliar, roteiro_sem_rede, tem_app, tem_falha_de_rede
from hub.controlador import Controlador, ControladorReferencia
from sim.motor import simular

RAIZ = Path(__file__).resolve().parent.parent   # raiz do núcleo
NUCLEO_CENARIOS = RAIZ / "cenarios"
# nucleo-v1.0: pasta da versão em uso. Por padrão é o próprio núcleo; um repositório de versão
# (reg10k-V0 … V4) passa a sua raiz com --raiz ou com a variável REG10K_RAIZ.
RAIZ_VERSAO = RAIZ
CENARIOS = NUCLEO_CENARIOS
AMBIENTES = [NUCLEO_CENARIOS]
ALUNOS = RAIZ / "alunos"
SAIDA = RAIZ / "saida"
SITE = RAIZ / "site" / "index.html"
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
VERSAO = "nucleo-v1.1"


IDENTIDADE_NUCLEO = {"nome": VERSAO, "titulo": "sala e cozinha, com gêmeo digital e espelho",
                     "descricao": "Núcleo com o conjunto de regressão (v0 a v1dtb)"}


def identidade() -> dict:
    """Nome e título da versão em uso (versao.json na raiz da versão; senão, o núcleo)."""
    p = RAIZ_VERSAO / "versao.json"
    ident = ler_json(p) if RAIZ_VERSAO != RAIZ and p.exists() else dict(IDENTIDADE_NUCLEO)
    return {**ident, "nucleo": VERSAO}


def configurar_raiz(raiz) -> Path:
    """Aponta o executor para a pasta de uma versão.

    Estrutura esperada (as pastas que faltarem caem no núcleo):
        <raiz>/cenarios/roteiros/*.json, <raiz>/cenarios/esperado/*.json
        <raiz>/ambiente/*.json  (ou <raiz>/cenarios/*.json)
        <raiz>/alunos/<grupo>/  (pacotes com `Controlador`)
        <raiz>/saida/, <raiz>/site/index.html
    """
    global RAIZ_VERSAO, CENARIOS, AMBIENTES, ALUNOS, SAIDA, SITE
    raiz = Path(raiz).resolve()
    RAIZ_VERSAO = raiz
    CENARIOS = raiz / "cenarios" if (raiz / "cenarios" / "roteiros").is_dir() else NUCLEO_CENARIOS
    AMBIENTES = [d for d in (raiz / "ambiente", raiz / "cenarios") if d.is_dir()] + [NUCLEO_CENARIOS]
    ALUNOS = raiz / "alunos"
    SAIDA = raiz / "saida"
    SITE = raiz / "site" / "index.html"
    _AMBIENTES.clear()
    if raiz != RAIZ:
        # os controladores da versão (alunos.<grupo>) vêm da pasta da versão
        for k in [k for k in sys.modules if k == "alunos" or k.startswith("alunos.")]:
            del sys.modules[k]
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
    return raiz


# --------------------------------------------------------------- carregamento
def ler_json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


_AMBIENTES: dict = {}


def caminho_ambiente(nome: str) -> Path:
    for d in AMBIENTES:
        if (d / f"{nome}.json").exists():
            return d / f"{nome}.json"
    raise FileNotFoundError(f"ambiente {nome}.json não encontrado em {[str(d) for d in AMBIENTES]}")


def carregar_sala() -> dict:
    return ambiente_de({})


def ambiente_de(roteiro: dict) -> dict:
    """v1dt: arquivo de ambiente do roteiro (padrão: a sala da v0)."""
    nome = roteiro.get("ambiente", "sala")
    if nome not in _AMBIENTES:
        _AMBIENTES[nome] = ler_json(caminho_ambiente(nome))
    return _AMBIENTES[nome]


def carregar_roteiros(ids: Optional[Iterable[str]] = None) -> list[dict]:
    todos = [ler_json(p) for p in sorted((CENARIOS / "roteiros").glob("*.json"))]
    ordem = {"NORMAL": 0, "FALSO_POSITIVO": 1, "FALSO_NEGATIVO": 2, "FALHA": 3, "GEMEO_DIGITAL": 4}
    todos.sort(key=lambda r: (ordem_versao(r.get("versao", "v0")), ordem.get(r["tipo"], 9), r["id"]))
    if ids:
        ids = set(ids)
        todos = [r for r in todos if r["id"] in ids]
    return todos


def ordem_versao(v: str) -> tuple:
    """v0 < v0dt < v0dta < v1dt < v1dt.1 < v2dt …: porte, ponto e o resto do nome."""
    import re
    m = re.match(r"v(\d+)([^\d.]*)(?:\.(\d+))?", v or "v0")
    return (int(m.group(1)), int(m.group(3) or 0), m.group(2)) if m else (99, 0, v)


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
    pasta = ALUNOS
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
    sala = sala or ambiente_de(roteiro)
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
    roteiros = carregar_roteiros(ids)
    execucoes: list[dict] = []
    problemas: list[str] = []
    for r in roteiros:
        sala = ambiente_de(r)
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
        "identidade": identidade(),
        "incremento": 2,
        # nucleo-v1.0: o ambiente "de referência" da página é o do primeiro cenário da versão
        "sala": ambiente_de(roteiros[0]) if roteiros else carregar_sala(),
        "ambientes": {r.get("ambiente", "sala"): ambiente_de(r) for r in roteiros},
        "cenarios": [
            {"versao": r.get("versao", "v0"),
             **{k: r[k] for k in ("id", "titulo", "tipo", "modo", "duracao_ms", "descricao",
                                  "comportamento_ideal", "comportamento_referencia", "requisitos", "regras", "rede", "amostras_ms")
                if k in r},
             "ambiente": r.get("ambiente", "sala"),
             "esperado": carregar_esperado(r["id"])}
            for r in roteiros
        ],
        "controladores": list(controladores),
        "execucoes": [{k: v for k, v in e.items() if k != "_eventos"} for e in execucoes],
        "problemas": problemas,
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    catalogo["_eventos"] = {(e["cenario"], e["controlador"]): e["_eventos"] for e in execucoes}
    catalogo["_roteiros"] = {r["id"]: r for r in roteiros}
    return catalogo


if os.environ.get("REG10K_RAIZ"):
    configurar_raiz(os.environ["REG10K_RAIZ"])
