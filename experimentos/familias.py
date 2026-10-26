"""Famílias de cenários do protocolo de experimentos (plano das versões paralelas §5).

As mesmas famílias valem para todas as versões; cada versão diz quais dos seus
cenários pertencem a cada família em `experimentos/familias.json`. Sem esse
arquivo, vale o mapeamento do conjunto de regressão do núcleo (abaixo).
"""
from __future__ import annotations

import json
from pathlib import Path

FAMILIAS = {
    "F1": {"nome": "Uso normal: entrar, sair, permanecer, interruptor",
           "mede": ["atraso_percebido_ms_max", "latencia_reacao_ms_p95", "desperdicio_s", "desperdicio_por_saida_s_max"]},
    "F2": {"nome": "Permanência parada (falso negativo)",
           "mede": ["escuro_com_ocupante_s", "apagamentos_indevidos", "ocupacao_desconhecida_s"]},
    "F3": {"nome": "Passagem sem entrar e disparos espúrios (falso positivo)",
           "mede": ["desperdicio_s", "acionamentos"]},
    "F4": {"nome": "Falha de dispositivo",
           "mede": ["escuro_com_ocupante_s", "desperdicio_s", "ocupacao_desconhecida_s"]},
    "F5": {"nome": "Queda de rede, plataforma ou hub",
           "mede": ["atualidade_gemeo_ms_p95", "reconciliacao_ms_max", "divergencia_alem_prazo_s", "gemeo_nao_atual_s"]},
    "F6": {"nome": "Comando remoto e preferência",
           "mede": ["comando_remoto_ms_p95", "comandos_vencidos_executados", "efeitos_duplicados_remotos"]},
    "F7": {"nome": "Espelho e consulta pelo app",
           "mede": ["espelho_fiel_pct", "erro_de_percepcao_s", "erro_de_sincronizacao_s", "espelho_nao_afirma_s"]},
}

# Conjunto de regressão do núcleo: V0 (sala) e V1 (sala e cozinha)
PADRAO = {
    "F1": ["N01", "N02", "N03", "N04", "N05", "N06", "M01", "M02", "M04", "M06", "M09", "M10"],
    "F2": ["FN01", "FN02", "FN03", "FN04", "FN05", "M05"],
    "F3": ["FP01", "FP02", "FP03", "M03"],
    "F4": ["F01", "F02", "F03", "F04", "M07", "M08"],
    "F5": ["DT02", "DT05", "DT07", "DT08", "DT10", "DT11", "F05", "F06", "M13"],
    "F6": ["DT01", "DT03", "DT04", "DT06", "DT09", "M11", "M12"],
    "F7": ["DT12", "M14"],
}


def carregar(raiz: Path, ids_existentes: set[str]) -> dict[str, list[str]]:
    """Mapeamento família → cenários da versão, só com cenários que existem."""
    p = raiz / "experimentos" / "familias.json"
    mapa = json.loads(p.read_text(encoding="utf-8"))["familias"] if p.exists() else PADRAO
    desconhecidas = set(mapa) - set(FAMILIAS)
    if desconhecidas:
        raise ValueError(f"famílias desconhecidas em {p}: {sorted(desconhecidas)}")
    return {f: [c for c in ids if c in ids_existentes] for f, ids in mapa.items()}
