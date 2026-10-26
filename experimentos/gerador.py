"""Gerador de cenários por planta (nucleo-v1.1; plano da v2dt §3.2).

Dada a planta de uma residência (ou a sala da v0), gera para cada família do
protocolo (F1–F7) os mesmos episódios em qualquer casa, com asserções de
janela relativa a um evento (§3.1). É isso que torna as famílias comparáveis
entre as versões: na sala, na residência da V1 e na Casa A, a F2 é sempre
"fica parado 5 min num cômodo", a F3 é sempre "espia pela passagem sem entrar".

Uso:
    python -m experimentos.gerador --ambiente casa-a --versao v2dt            # na raiz de uma versão
    python nucleo/reg10k.py gerador --ambiente casa-a --versao v2dt           # idem, pelo lançador

Grava cenarios/roteiros/G*.json e cenarios/esperado/G*.json e atualiza
experimentos/familias.json com os cenários gerados.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from sim.residencia import Residencia

PASSO = 12_000          # tempo reservado para cada troca de cômodo
ENTRA = {"evento": "CRUZOU_PORTA", "sentido": "ENTRADA"}
INV = {"id": "INV", "nivel": "REQUISITO", "dado": "qualquer controlador", "quando": "o cenário termina",
       "entao": {"tipo": "invariantes"}}
# requisitos e regras de cada família (os mesmos dos cenários escritos à mão que as originaram)
RASTRO = {
    "F1": (["RF-OPR-01", "RNF-DES-03"], ["RN-I0-02", "RN-I0-03", "RN-V1-01"]),
    "F2": (["RF-OPR-01", "CF05"], ["RN-I0-03"]),
    "F3": (["RN09", "RF-OPR-01"], ["RN-V1-01"]),
    "F4": (["RF-OPR-09", "CV03", "CF05"], ["RN-I0-04"]),
    "F5": (["RF-SYN-03", "RF-SYN-04", "RNF-CON-01", "CF06"], ["RN-DT-03", "RN-DT-04", "RN-DT-08"]),
    "F6": (["RF-OPR-03", "RF-OPR-04", "RNF-DES-02", "CF04"], ["RN-DT-05", "RN-DT-09", "RN-V1-03"]),
    "F7": (["RN-V1-04", "RN34"], ["RN-V1-04", "RN-I0-01"]),
}
TIPO = {"F1": "NORMAL", "F2": "FALSO_NEGATIVO", "F3": "FALSO_POSITIVO", "F4": "FALHA",
        "F5": "GEMEO_DIGITAL", "F6": "GEMEO_DIGITAL", "F7": "GEMEO_DIGITAL"}


class Planta:
    def __init__(self, cfg: dict, nome: str):
        self.cfg, self.nome = cfg, nome
        self.res = Residencia(cfg)
        self.multi = self.res.multi
        self.ext = self.res.externa
        self.entrada = self.ext.comodos[0]
        self.nomes = {cid: c.nome for cid, c in self.res.comodos.items()}
        ocup = cfg["ocupantes"]
        self.pessoa = next(o["id"] for o in ocup if o["tipo"] == "PESSOA")
        self.cao = next((o["id"] for o in ocup if o["tipo"] == "CACHORRO"), None)
        self.viz: dict[str, list[str]] = {cid: [] for cid in self.res.ids}
        for ps in self.res.passagens.values():
            if ps.tipo == "INTERNA":
                a, b = ps.comodos
                self.viz[a].append(b)
                self.viz[b].append(a)

    def caminho(self, a: str, b: str) -> list[str]:
        """Cômodos de a até b pelo menor número de passagens (inclui os dois)."""
        ant, fila = {a: None}, deque([a])
        while fila:
            x = fila.popleft()
            for y in sorted(self.viz[x]):
                if y not in ant:
                    ant[y] = x
                    fila.append(y)
        if b not in ant:
            raise ValueError(f"{b} não é alcançável a partir de {a}")
        out, x = [], b
        while x is not None:
            out.append(x)
            x = ant[x]
        return out[::-1]

    def t_apagamento(self, cid: str) -> int:
        c = {**self.res.controle, **self.res.comodos[cid].controle}
        return c.get("t_apagamento_ms", 60_000)

    def com(self, cid: str) -> dict:
        """Campo `comodo` das ações e asserções (omitido na sala da v0)."""
        return {"comodo": cid} if self.multi else {}


class Roteiro:
    def __init__(self, p: Planta):
        self.p, self.acoes, self.falhas, self.t = p, [], [], 5_000
        self.onde = {p.pessoa: None}

    def acao(self, quem: str, acao: str, **kw) -> None:
        self.acoes.append({"t_ms": self.t, "ocupante": quem, "acao": acao, **kw})

    def entrar(self, quem: str) -> None:
        self.acao(quem, "ENTRAR")
        self.onde[quem] = self.p.entrada
        self.t += 3_000

    def ir(self, quem: str, destino: str) -> None:
        for prox in self.p.caminho(self.onde[quem], destino)[1:]:
            self.acao(quem, "MUDAR_COMODO", para=prox)
            self.onde[quem] = prox
            self.t += PASSO

    def andar(self, quem: str, ms: int) -> None:
        self.acao(quem, "ANDAR_ALEATORIO", duracao_ms=ms)
        self.t += ms + 2_000

    def sair(self, quem: str) -> None:
        self.ir(quem, self.p.entrada)
        self.acao(quem, "ANDAR", ate=list(self.p.ext.pontos[self.p.entrada]))
        self.t += 8_000
        self.acao(quem, "SAIR")
        self.onde[quem] = None
        self.t += 2_000


def _cenario(p: Planta, fam: str, sufixo: str, versao: str, titulo: str, descricao: str, ideal: str,
             ref: str, r: Roteiro, duracao: int, assercoes: list[dict]) -> tuple[dict, dict]:
    cid = f"G{fam[1:].zfill(2)}-{sufixo}"
    req, regras = RASTRO[fam]
    roteiro = {"id": cid, "versao": versao, **({"ambiente": p.nome} if p.nome != "sala" else {}),
               "titulo": titulo, "tipo": TIPO[fam], "modo": "IDEAL", "duracao_ms": duracao,
               "descricao": descricao, "comportamento_ideal": ideal, "comportamento_referencia": ref,
               "requisitos": req, "regras": regras, "familia": fam, "gerado": True,
               "estado_inicial": {"ocupantes_na_sala": [], "luz": "APAGADA"},
               "acoes": sorted(r.acoes, key=lambda a: a["t_ms"]), "falhas": r.falhas}
    esperado = {"cenario": cid, "modo": "IDEAL", "semente_referencia": 42, "requisitos": req,
                "gerado": True, "assercoes": assercoes + [INV]}
    return roteiro, esperado


def _acende(p: Planta, cid: str, i: int, ocorrencia: int = 1) -> dict:
    return {"id": f"L{i}", "nivel": "REQUISITO", "dado": f"{p.nomes[cid]} escuro",
            "quando": "alguém entra", "entao": {"tipo": "luz", **p.com(cid), "valor": "ACESA",
                                                 "apos": {**ENTRA, "ocorrencia": ocorrencia}, "ate_ms": 1000}}


def gerar(cfg: dict, nome: str, versao: str) -> list[tuple[dict, dict]]:
    p = Planta(cfg, nome)
    out: list[tuple[dict, dict]] = []
    ids = p.res.ids

    for cid in ids:  # F1: percorre a casa até o cômodo e volta
        r = Roteiro(p)
        r.entrar(p.pessoa)
        r.andar(p.pessoa, 20_000)
        rota = p.caminho(p.entrada, cid)
        for prox in rota[1:]:
            r.ir(p.pessoa, prox)
            r.andar(p.pessoa, 20_000 if prox != cid else 30_000)
        r.sair(p.pessoa)
        fim = r.t + max(p.t_apagamento(c) for c in ids) + 60_000
        asserc = [_acende(p, c, i + 1) for i, c in enumerate(rota)]
        asserc += [{"id": "D1", "nivel": "REQUISITO", "dado": "cômodo esvaziado", "quando": "a luz apaga",
                    "entao": {"tipo": "metrica", **p.com(c), "nome": "desperdicio_por_saida_s_max",
                              "max": p.t_apagamento(c) / 1000 + 30}} for c in rota]
        for i, a in enumerate(asserc[len(rota):], 1):
            a["id"] = f"D{i}"
        asserc += [{"id": "M1", "nivel": "REQUISITO", "dado": "morador sempre presente em algum cômodo",
                    "quando": "o cenário termina", "entao": {"tipo": "metrica", "nome": "apagamentos_indevidos", "igual": 0}},
                   {"id": "M2", "nivel": "REQUISITO", "dado": "entrada em cômodo escuro", "quando": "a lâmpada acende",
                    "entao": {"tipo": "metrica", "nome": "atraso_percebido_ms_max", "max": 1000}}]
        out.append(_cenario(p, "F1", cid, versao, f"Vai até {p.nomes[cid].lower()} e volta",
                            f"O morador entra, percorre {' → '.join(p.nomes[c] for c in rota)}, volta e sai.",
                            "A luz acompanha o morador cômodo a cômodo e apaga nos que ficam vazios.",
                            "Acende em até 1 s a cada entrada; cada cômodo apaga T_apagamento depois da última evidência.",
                            r, fim, asserc))

    for cid in ids:  # F2: parado 5 min
        r = Roteiro(p)
        r.entrar(p.pessoa)
        r.ir(p.pessoa, cid)
        c = p.res.comodos[cid]
        r.acao(p.pessoa, "ANDAR", ate=list(c.centro()))
        r.t += 8_000
        r.acao(p.pessoa, "PARADO")
        fim = r.t + 300_000
        asserc = [_acende(p, cid, 1)]
        out.append(_cenario(p, "F2", cid, versao, f"Fica parado em {p.nomes[cid].lower()} por 5 min",
                            f"O morador vai até {p.nomes[cid].lower()} e fica parado; o PIR não o vê.",
                            "A luz fica acesa enquanto ele está lá.",
                            f"Limitação conhecida: apaga T_apagamento ({p.t_apagamento(cid) // 1000} s) depois da última evidência.",
                            r, fim, asserc))

    for ps in p.res.passagens.values():  # F3: espia pela passagem interna sem entrar
        if ps.tipo != "INTERNA":
            continue
        a, b = sorted(ps.comodos, key=lambda x: len(p.caminho(p.entrada, x)))
        r = Roteiro(p)
        r.entrar(p.pessoa)
        r.ir(p.pessoa, a)
        r.acao(p.pessoa, "ANDAR", ate=list(ps.pontos[a]))
        r.t += 10_000
        r.acao(p.pessoa, "ESPIAR", comodo=b)
        r.t += 5_000
        r.andar(p.pessoa, 60_000)
        r.sair(p.pessoa)
        fim = r.t + 90_000
        asserc = [_acende(p, a, 1)]
        out.append(_cenario(p, "F3", ps.id, versao, f"Espia {p.nomes[b].lower()} pela {ps.id} sem entrar",
                            f"O morador vai até a {ps.id}, olha {p.nomes[b].lower()} sem entrar e volta.",
                            f"{p.nomes[b]} não acende: ninguém entrou.",
                            f"Limitação conhecida (RN-V1-01): o SA da passagem vai aos dois cômodos e {p.nomes[b].lower()} acende.",
                            r, fim, asserc))

    for cid in ids:  # F4: o SP do cômodo para de responder com o morador dentro
        r = Roteiro(p)
        r.entrar(p.pessoa)
        r.ir(p.pessoa, cid)
        r.t += 20_000
        tf = r.t
        r.falhas.append({"t_ms": tf, "tipo": "SP_SEM_RESPOSTA", "dispositivo": p.res.comodos[cid].sp})
        r.andar(p.pessoa, 200_000)
        fim = r.t + 30_000
        asserc = [
            {"id": "A1", "nivel": "REQUISITO", "dado": "SP sem heartbeat", "quando": "passa o prazo",
             "entao": {"tipo": "alerta", **p.com(cid), "alerta": "SP_SEM_RESPOSTA", "entre_ms": [tf + 5_000, tf + 40_000]}},
            {"id": "A2", "nivel": "REQUISITO", "dado": "SP sem heartbeat", "quando": "passa o prazo",
             "entao": {"tipo": "ocupacao", **p.com(cid), "valor": "DESCONHECIDA", "em_ms": tf + 60_000}},
            {"id": "A3", "nivel": "REQUISITO", "dado": "ocupação desconhecida", "quando": "o silêncio continua",
             "entao": {"tipo": "sem_intencao", **p.com(cid), "acao": "APAGAR", "entre_ms": [tf, fim]}},
        ]
        out.append(_cenario(p, "F4", cid, versao, f"SP de {p.nomes[cid].lower()} para de responder",
                            f"O morador está em {p.nomes[cid].lower()} quando o SP dali para de responder.",
                            "O sistema sinaliza a falha e não apaga por silêncio.",
                            "Alerta SP_SEM_RESPOSTA; ocupação desconhecida; a luz fica como está (RN-I0-04).",
                            r, fim, asserc))

    # F5: desconexão de 10 min com circulação (entre a entrada e o vizinho mais próximo, se houver)
    r = Roteiro(p)
    r.t = 10_000
    r.entrar(p.pessoa)
    r.andar(p.pessoa, 40_000)
    vizinho = sorted(p.viz[p.entrada])[0] if p.viz[p.entrada] else None
    if vizinho:
        r.ir(p.pessoa, vizinho)
        r.andar(p.pessoa, 200_000)
        r.ir(p.pessoa, p.entrada)
    r.andar(p.pessoa, 200_000 if vizinho else 400_000)
    r.sair(p.pessoa)
    r.falhas.append({"t_ms": 60_000, "tipo": "CANAL_DESCONECTA", "duracao_ms": 600_000})
    fim = max(r.t, 660_000) + 120_000
    asserc = [
        {"id": "A1", "nivel": "REQUISITO", "dado": "canal caído", "quando": "logo depois da queda",
         "entao": {"tipo": "gemeo", **p.com(p.entrada), "em_ms": 61_000, "atualidade": "DESATUALIZADO", "conexao": "DESCONECTADO"}},
        {"id": "A2", "nivel": "REQUISITO", "dado": "canal volta", "quando": "o hub reconcilia",
         "entao": {"tipo": "metrica", "nome": "reconciliacao_ms_max", "max": 5000}},
        {"id": "A3", "nivel": "REQUISITO", "dado": "fila persistente", "quando": "o cenário termina",
         "entao": {"tipo": "metrica", "nome": "eventos_nao_entregues", "igual": 0}},
    ]
    out.append(_cenario(p, "F5", "casa", versao, "Desconexão de 10 min com circulação",
                        "O canal hub ↔ plataforma cai por 10 min enquanto o morador circula pela casa.",
                        "A automação local segue; o gêmeo remoto se declara desatualizado e reconcilia ao voltar.",
                        "Fila persistente; estado atual antes do histórico; reconciliação em até 5 s.",
                        r, fim, asserc))

    for cid in ids:  # F6: comando remoto acende um cômodo vazio
        r = Roteiro(p)
        r.acoes += [{"t_ms": 70_000, "ocupante": "app", "acao": "APP_COMANDO", "comando": "ACENDER", **p.com(cid)},
                    {"t_ms": 75_000, "ocupante": "app", "acao": "APP_CONSULTA"}]
        asserc = [
            {"id": "A1", "nivel": "REQUISITO", "dado": "casa vazia, sessão ativa", "quando": "o titular comanda",
             "entao": {"tipo": "comando", **p.com(cid), "indice": 1, "nivel": "EFEITO_OBSERVADO", "latencia_max_ms": 3000}},
            {"id": "A2", "nivel": "REQUISITO", "dado": "comando aceito", "quando": "o hub executa",
             "entao": {"tipo": "luz", **p.com(cid), "valor": "ACESA", "desde_ms": 70_000, "ate_ms": 73_000}},
        ]
        out.append(_cenario(p, "F6", cid, versao, f"Comando remoto acende {p.nomes[cid].lower()}",
                            f"Com a casa vazia, o titular acende {p.nomes[cid].lower()} pelo app.",
                            "Só o cômodo pedido acende, em até 3 s, com efeito observado.",
                            "Validade de 30 s, chave de idempotência e precedência remota (RN-DT-09).",
                            r, 200_000, asserc))

    if p.cao:
        for cid in ids:  # F7: o Rex vai a um cômodo e deita (espelho)
            r = Roteiro(p)
            r.entrar(p.pessoa)
            r.entrar(p.cao)
            r.ir(p.cao, cid)
            t_rex = r.t
            r.acao(p.cao, "ANDAR_ALEATORIO", duracao_ms=60_000)
            r.t = t_rex + 62_000
            r.acao(p.cao, "PARADO")
            r.t = 10_000
            r.acao(p.pessoa, "ANDAR_ALEATORIO", duracao_ms=290_000)
            asserc = [{"id": "A1", "nivel": "REQUISITO", "dado": "morador andando na entrada", "quando": "o cenário corre",
                       "entao": {"tipo": "luz_constante", **p.com(p.entrada), "valor": "ACESA", "entre_ms": [6_000, 300_000]}}]
            out.append(_cenario(p, "F7", cid, versao, f"Rex deita em {p.nomes[cid].lower()}",
                                f"O morador anda em {p.nomes[p.entrada].lower()}; o Rex vai a {p.nomes[cid].lower()}, anda e deita.",
                                "O gêmeo mostra presença enquanto o Rex está lá.",
                                "Com o Rex parado, o PIR deixa de vê-lo: o espelho passa a afirmar vazio (erro de percepção).",
                                r, 310_000, asserc))
    return out


def gravar(raiz: Path, cenarios: list[tuple[dict, dict]]) -> dict[str, list[str]]:
    for sub in ("roteiros", "esperado"):
        (raiz / "cenarios" / sub).mkdir(parents=True, exist_ok=True)
    fam: dict[str, list[str]] = {}
    for rot, esp in cenarios:
        (raiz / "cenarios" / "roteiros" / f"{rot['id']}.json").write_text(json.dumps(rot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (raiz / "cenarios" / "esperado" / f"{rot['id']}.json").write_text(json.dumps(esp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        fam.setdefault(rot["familia"], []).append(rot["id"])
    return fam


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m experimentos.gerador", description=__doc__.split("\n")[0])
    ap.add_argument("--raiz", help="pasta da versão (padrão: REG10K_RAIZ ou a atual)")
    ap.add_argument("--ambiente", required=True)
    ap.add_argument("--versao", required=True)
    a = ap.parse_args(argv)
    from catalogo import executar as ex
    if a.raiz:
        ex.configurar_raiz(a.raiz)
    raiz = ex.RAIZ_VERSAO
    cfg = json.loads(ex.caminho_ambiente(a.ambiente).read_text(encoding="utf-8"))
    fam = gravar(raiz, gerar(cfg, a.ambiente, a.versao))
    p = raiz / "experimentos" / "familias.json"
    atual = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"familias": {}}
    for f, novos in fam.items():
        atual["familias"][f] = sorted(set(atual["familias"].get(f, [])) | set(novos))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(len(v) for v in fam.values())} cenários gerados em {raiz / 'cenarios'}: "
          + ", ".join(f"{f}={len(v)}" for f, v in sorted(fam.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
