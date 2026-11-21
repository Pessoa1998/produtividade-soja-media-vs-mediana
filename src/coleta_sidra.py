"""Coleta a Produção Agrícola Municipal (PAM/IBGE) de soja por município na API do SIDRA.

Consulta usada (tabela 5457, todos os municípios, Soja (em grão)):

    https://apisidra.ibge.gov.br/values/t/5457/n6/all/v/216,214,112/p/2025/c782/40124

    t/5457        tabela 5457 da PAM (lavouras temporárias e permanentes)
    n6/all        nível territorial 6 = município, todos
    v/216,214,112 área colhida (ha), quantidade produzida (t), rendimento médio (kg/ha)
    p/2025        ano (sem --ano, usa "last 1" = o mais recente publicado)
    c782/40124    classificação "Produto das lavouras", categoria Soja (em grão)

Arquivos gerados:

    data/raw/pam_5457_soja_municipios_<ano>.csv    registros exatamente como vieram da API
    data/processed/soja_municipios_<ano>.csv       uma linha por município com soja colhida

Uso:

    python src/coleta_sidra.py                     # ano mais recente
    python src/coleta_sidra.py --ano 2024
    python src/coleta_sidra.py --json resposta.json  # resposta da API salva antes (sem rede)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"

API = "https://apisidra.ibge.gov.br/values"
TABELA = 5457
VARIAVEIS = {  # código da variável no SIDRA -> nome da coluna
    "216": "area_colhida_ha",  # Área colhida (Hectares)
    "214": "producao_t",  # Quantidade produzida (Toneladas)
    "112": "rendimento_kg_ha",  # Rendimento médio da produção (Quilogramas por Hectare)
}
CLASSIFICACAO, SOJA = 782, 40124  # Produto das lavouras temporárias e permanentes / Soja (em grão)
KG_POR_SACA = 60

# Sinais convencionais do IBGE que não são números:
#   "-"   zero absoluto, não resultante de arredondamento
#   ".."  não se aplica dado numérico
#   "..." dado numérico não disponível
#   "X"   dado omitido para não identificar o informante
SINAIS_SEM_VALOR = ["-", "..", "...", "X"]

COLUNAS = [
    "cod_municipio",
    "municipio",
    "uf",
    "ano",
    "area_colhida_ha",
    "producao_t",
    "rendimento_kg_ha",
    "rendimento_sc_ha",
]


def montar_url(ano: int | str = "last") -> str:
    """URL da consulta na API do SIDRA. ``ano="last"`` pede o ano mais recente."""
    periodo = "last%201" if str(ano) == "last" else str(int(ano))
    variaveis = ",".join(VARIAVEIS)
    return f"{API}/t/{TABELA}/n6/all/v/{variaveis}/p/{periodo}/c{CLASSIFICACAO}/{SOJA}"


def baixar(url: str, timeout: int = 180) -> list[dict]:
    """Baixa a consulta. Sem o Accept JSON a API pode responder em XML."""
    resposta = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
    resposta.raise_for_status()
    return resposta.json()


def registros_para_bruto(registros: list[dict]) -> pd.DataFrame:
    """Converte a resposta da API em tabela, sem alterar nenhum valor.

    O primeiro registro é o cabeçalho (rótulo de cada chave: D1N = "Município" etc.)
    e fica de fora; as colunas mantêm as chaves originais da API (NC, NN, MC, MN, V,
    D1C, D1N, D2C, D2N, D3C, D3N, D4C, D4N).
    """
    cabecalho, *linhas = registros
    if cabecalho.get("V") != "Valor" or not linhas:
        raise ValueError("Resposta inesperada da API: esperava cabeçalho + registros.")
    return pd.DataFrame(linhas, columns=list(cabecalho)).astype(str)


def ler_bruto(caminho: str | Path) -> pd.DataFrame:
    """Lê o CSV de data/raw mantendo tudo como texto (códigos e sinais como "-")."""
    return pd.read_csv(caminho, dtype=str, keep_default_na=False)


def limpar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município com soja colhida, no esquema descrito no README.

    1. Sinais do IBGE ("-", "...", "..", "X") viram nulo; o resto vira número.
    2. Formato longo (uma linha por variável) vira largo (uma coluna por variável).
    3. "Lucas do Rio Verde - MT" é separado em município e UF.
    4. Saem os municípios sem área colhida (nula ou zero).
    """
    longo = bruto[bruto["D2C"].isin(VARIAVEIS)].copy()
    sem_valor = longo["V"].isin(SINAIS_SEM_VALOR)
    longo["valor"] = pd.to_numeric(longo["V"].where(~sem_valor), errors="raise")

    largo = (
        longo.pivot(index=["D1C", "D1N", "D3N"], columns="D2C", values="valor")
        .rename(columns=VARIAVEIS)
        .reset_index()
    )
    largo.columns.name = None

    nome_uf = largo["D1N"].str.rsplit(" - ", n=1, expand=True)
    largo["cod_municipio"] = largo["D1C"].astype(str)
    largo["municipio"] = nome_uf[0]
    largo["uf"] = nome_uf[1]
    largo["ano"] = largo["D3N"].astype(int)

    largo = largo[largo["area_colhida_ha"] > 0]
    largo = largo.dropna(subset=["producao_t", "rendimento_kg_ha"]).copy()
    for coluna in ["area_colhida_ha", "producao_t", "rendimento_kg_ha"]:
        largo[coluna] = largo[coluna].astype(float)
    largo["rendimento_sc_ha"] = largo["rendimento_kg_ha"] / KG_POR_SACA

    return largo[COLUNAS].sort_values(["uf", "municipio"]).reset_index(drop=True)


def ler_processado(caminho: str | Path) -> pd.DataFrame:
    """Lê um CSV de data/processed com os tipos do esquema."""
    tipos = {"cod_municipio": str, "municipio": str, "uf": str, "ano": int}
    df = pd.read_csv(caminho, dtype=tipos)
    numericas = ["area_colhida_ha", "producao_t", "rendimento_kg_ha", "rendimento_sc_ha"]
    df[numericas] = df[numericas].astype(float)
    return df[COLUNAS]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Baixa e limpa a PAM de soja por município.")
    parser.add_argument("--ano", default="last", help="ano da PAM (padrão: o mais recente)")
    parser.add_argument("--json", type=Path, help="resposta da API já salva (pula o download)")
    args = parser.parse_args(argv)

    if args.json:
        print(f"Lendo {args.json}")
        registros = json.loads(args.json.read_text(encoding="utf-8"))
    else:
        url = montar_url(args.ano)
        print(f"Baixando {url}")
        registros = baixar(url)

    bruto = registros_para_bruto(registros)
    anos = bruto["D3N"].unique()
    if len(anos) != 1:
        raise ValueError(f"Esperava um único ano na resposta, veio {list(anos)}.")
    ano = int(anos[0])
    if args.ano != "last" and int(args.ano) != ano:
        raise ValueError(f"Pedido o ano {args.ano}, mas os dados são de {ano}.")

    DIR_RAW.mkdir(parents=True, exist_ok=True)
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    caminho_raw = DIR_RAW / f"pam_5457_soja_municipios_{ano}.csv"
    caminho_processado = DIR_PROCESSED / f"soja_municipios_{ano}.csv"

    bruto.to_csv(caminho_raw, index=False)
    limpo = limpar(bruto)
    limpo.to_csv(caminho_processado, index=False, float_format="%.10g")

    n_total = bruto["D1C"].nunique()
    print(f"Ano {ano}: {n_total} municípios na resposta, {len(limpo)} com soja colhida.")
    area, producao = limpo["area_colhida_ha"].sum(), limpo["producao_t"].sum()
    print(f"Área colhida: {area:,.0f} ha | Produção: {producao:,.0f} t".replace(",", "."))
    print(f"Salvo: {caminho_raw.relative_to(RAIZ)} e {caminho_processado.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
