"""Gera municípios FICTÍCIOS de soja com rendimento assimétrico (mistura de normais).

Serve para rodar o projeto sem depender da API do IBGE. A saída segue o mesmo
esquema de data/processed/ e é identificada como simulada em três lugares: no nome
do arquivo (soja_municipios_simulado.csv), nas UFs (SIM-A, SIM-B, SIM-C) e nos
nomes dos municípios ("Município simulado 001").

Cada UF fictícia mostra um caso:

    SIM-A  cauda inferior: parte dos municípios teve quebra (seca); média < mediana
    SIM-B  cauda superior: poucos municípios bem acima do resto; média > mediana
    SIM-C  quase simétrica: média ≈ mediana (controle)

Uso:

    python src/simular.py
    python src/simular.py --semente 7
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from coleta_sidra import COLUNAS, DIR_PROCESSED, KG_POR_SACA, RAIZ

ARQUIVO_SIMULADO = DIR_PROCESSED / "soja_municipios_simulado.csv"

# Por UF: número de municípios e componentes da mistura, cada um como
# (peso, média em sc/ha, desvio em sc/ha, área colhida típica em ha).
PERFIS = {
    "SIM-A": {"n": 140, "componentes": [(0.82, 64, 4, 12_000), (0.18, 40, 8, 4_000)]},
    "SIM-B": {"n": 90, "componentes": [(0.85, 54, 4, 6_000), (0.15, 78, 4, 15_000)]},
    "SIM-C": {"n": 110, "componentes": [(1.00, 60, 5, 8_000)]},
}


def simular(semente: int = 42, ano: int = 2025, perfis: dict = PERFIS) -> pd.DataFrame:
    """Sorteia municípios por UF; o rendimento é recalculado como produção / área, como na PAM."""
    rng = np.random.default_rng(semente)
    partes = []
    for uf, perfil in perfis.items():
        n = perfil["n"]
        colunas = zip(*perfil["componentes"], strict=True)
        pesos, medias, desvios, areas = (np.array(c, dtype=float) for c in colunas)
        componente = rng.choice(len(pesos), size=n, p=pesos / pesos.sum())

        rendimento_sc = np.clip(rng.normal(medias[componente], desvios[componente]), 5, 95)
        area = np.maximum(10, np.round(rng.lognormal(np.log(areas[componente]), 0.9)))
        producao_t = np.round(area * rendimento_sc * KG_POR_SACA / 1000)
        rendimento_kg = np.round(producao_t * 1000 / area)

        partes.append(
            pd.DataFrame(
                {
                    "municipio": [f"Município simulado {i:03d}" for i in range(1, n + 1)],
                    "uf": uf,
                    "ano": ano,
                    "area_colhida_ha": area,
                    "producao_t": producao_t,
                    "rendimento_kg_ha": rendimento_kg,
                }
            )
        )

    df = pd.concat(partes, ignore_index=True)
    df["cod_municipio"] = [f"SIM{i:04d}" for i in range(1, len(df) + 1)]
    df["rendimento_sc_ha"] = df["rendimento_kg_ha"] / KG_POR_SACA
    return df[COLUNAS]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gera municípios fictícios de soja.")
    parser.add_argument("--semente", type=int, default=42, help="semente do sorteio (padrão: 42)")
    parser.add_argument("--ano", type=int, default=2025, help="ano gravado na coluna ano")
    args = parser.parse_args(argv)

    df = simular(semente=args.semente, ano=args.ano)
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQUIVO_SIMULADO, index=False, float_format="%.10g")

    resumo = df.groupby("uf")["rendimento_sc_ha"].agg(n="size", media="mean", mediana="median")
    print("Dados SIMULADOS (não são da PAM):")
    print(resumo.round(1).to_string())
    print(f"Salvo: {ARQUIVO_SIMULADO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
