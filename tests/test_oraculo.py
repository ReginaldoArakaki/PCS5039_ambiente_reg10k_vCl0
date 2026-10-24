"""O oráculo detecta violações: controladores defeituosos de propósito."""
from avaliacao.oraculo import avaliar
from catalogo.executar import carregar_esperado, carregar_roteiros, carregar_sala
from hub.controlador import ControladorReferencia
from sim.modelos import APAGAR, AUTOMATICA, Intencao
from sim.motor import simular

SALA = carregar_sala()
R = {r["id"]: r for r in carregar_roteiros()}


class ApagaCedo(ControladorReferencia):
    """Apaga 10 s após a última detecção: viola OR-03 e gera apagamentos indevidos."""
    nome = "apaga_cedo"

    def iniciar(self, config):
        super().iniciar(config)
        self.cfg.t_apagamento_ms = 10_000


class ApagaNoSilencio(ControladorReferencia):
    """Apaga quando o SP some: viola OR-04 (RN01)."""
    nome = "apaga_no_silencio"

    def ao_tick(self, agora_ms):
        saida = super().ao_tick(agora_ms)
        if "SP_SEM_RESPOSTA" in self.alertas and self.luz != "APAGADA":
            self.luz = "APAGADA"
            saida.append(Intencao(APAGAR, "SILENCIO", "nenhuma", AUTOMATICA))
        return saida


def _avaliar(roteiro_id, fab):
    r = R[roteiro_id]
    return avaliar(simular(SALA, r, fab, 42).eventos, r, SALA, carregar_esperado(roteiro_id))


def test_apagar_cedo_viola_or03_e_requisito():
    res = _avaliar("FN01", ApagaCedo)
    ref = _avaliar("FN01", ControladorReferencia)
    assert not res["invariantes"]["OR-03"]["ok"]
    assert res["metricas"]["escuro_com_ocupante_s"] > ref["metricas"]["escuro_com_ocupante_s"] + 40
    assert not res["requisitos_ok"]


def test_apagar_no_silencio_viola_or04():
    res = _avaliar("F01", ApagaNoSilencio)
    assert not res["invariantes"]["OR-04"]["ok"]
    assert not res["requisitos_ok"]


def test_metricas_de_falso_positivo():
    res = _avaliar("FP01", ControladorReferencia)
    m = res["metricas"]
    assert m["tempo_ocupada_s"] == 0
    assert 55 <= m["desperdicio_s"] <= 65
    assert m["escuro_com_ocupante_s"] == 0


def test_controlador_nunca_recebe_a_verdade():
    reg = simular(SALA, R["N06"], ControladorReferencia, 42)
    fim = [e for e in reg.eventos if e["tipo"] == "FIM"][-1]
    assert fim["entregas_ao_controlador"]["VERDADE"] == 0
    assert fim["entregas_ao_controlador"]["PERCEPCAO"] > 0
