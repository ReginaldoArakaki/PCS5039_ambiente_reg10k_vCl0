"""Os arquivos de entrada seguem os JSON Schema; arquivos inválidos são rejeitados."""
import copy

from catalogo.executar import carregar_roteiros
from catalogo.validar import erros, validar_tudo


def test_entradas_validas():
    assert validar_tudo(com_saida=False) == []


def test_roteiro_invalido_e_rejeitado():
    r = copy.deepcopy(carregar_roteiros(["N01"])[0])
    r["acoes"][0]["acao"] = "VOAR"
    r["modo"] = "TURBO"
    del r["duracao_ms"]
    msgs = " ".join(erros("roteiro", r))
    assert "VOAR" in msgs and "TURBO" in msgs and "duracao_ms" in msgs


def test_andar_exige_destino():
    r = copy.deepcopy(carregar_roteiros(["N01"])[0])
    r["acoes"].append({"t_ms": 1000, "ocupante": "morador", "acao": "ANDAR"})
    assert any("ate" in m for m in erros("roteiro", r))


def test_evento_de_intencao_exige_campos():
    ev = {"id": "x", "t_ms": 1, "seq": 1, "camada": "DECISAO", "tipo": "INTENCAO",
          "relogio_hub_ms": 1, "relogio_confiavel": True, "acao": "ACENDER"}
    assert erros("evento", ev)
