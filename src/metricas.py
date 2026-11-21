"""Medidas de produtividade de soja por UF a partir do rendimento de cada município.

Três números que costumam ser chamados de "produtividade média" e respondem
perguntas diferentes:

    media     média simples dos municípios: cada município pesa igual,
              do maior produtor ao que colheu 50 ha
    mediana   o município do meio: metade rende mais, metade rende menos
    agregada  produção total / área total; é a conta da produtividade oficial
              da UF ou do país e equivale à média dos municípios ponderada pela área
"""

from __future__ import annotations

import pandas as pd

KG_POR_SACA = 60
REND = "rendimento_sc_ha"


def produtividade_agregada(df: pd.DataFrame) -> float:
    """Produção total / área colhida total, em sc/ha."""
    return df["producao_t"].sum() * 1000 / df["area_colhida_ha"].sum() / KG_POR_SACA


def resumo(df: pd.DataFrame, por: str = "uf") -> pd.DataFrame:
    """Uma linha por grupo: n, área, produção e as medidas do rendimento (sc/ha).

    ``dif_media_mediana_pct`` é (média / mediana - 1) * 100: positiva quando a cauda
    de municípios com rendimento alto puxa a média para cima, negativa quando a
    cauda de rendimento baixo puxa para baixo.
    """
    dados = df.assign(_rend_x_area=df[REND] * df["area_colhida_ha"])
    grupos = dados.groupby(por)
    tabela = grupos.agg(
        n_municipios=(REND, "size"),
        area_colhida_ha=("area_colhida_ha", "sum"),
        producao_t=("producao_t", "sum"),
        media=(REND, "mean"),
        mediana=(REND, "median"),
        p25=(REND, lambda s: s.quantile(0.25)),
        p75=(REND, lambda s: s.quantile(0.75)),
        assimetria=(REND, "skew"),
        _soma_rend_x_area=("_rend_x_area", "sum"),
    )
    tabela["media_ponderada_area"] = tabela.pop("_soma_rend_x_area") / tabela["area_colhida_ha"]
    tabela["agregada"] = tabela["producao_t"] * 1000 / tabela["area_colhida_ha"] / KG_POR_SACA
    tabela["dif_media_mediana_pct"] = (tabela["media"] / tabela["mediana"] - 1) * 100
    tabela["dif_media_agregada_pct"] = (tabela["media"] / tabela["agregada"] - 1) * 100
    return tabela.sort_values("producao_t", ascending=False)


def resumo_total(df: pd.DataFrame, rotulo: str = "Brasil") -> pd.DataFrame:
    """O mesmo resumo, com todos os municípios num grupo só."""
    return resumo(df.assign(_grupo=rotulo), por="_grupo").rename_axis("uf")


def destacar(tabela: pd.DataFrame, limiar_pct: float = 5.0) -> pd.DataFrame:
    """Grupos em que média e mediana se afastam mais que ``limiar_pct`` (em módulo)."""
    return tabela[tabela["dif_media_mediana_pct"].abs() > limiar_pct]


def maior_distorcao(tabela: pd.DataFrame, candidatas=None, excluir=()) -> str:
    """Grupo com a maior diferença |média - mediana| (%) entre as candidatas."""
    candidatas = tabela.index if candidatas is None else candidatas
    escolha = tabela.loc[[uf for uf in candidatas if uf not in excluir]]
    return escolha["dif_media_mediana_pct"].abs().idxmax()


def correlacao_area_rendimento(df: pd.DataFrame, por: str = "uf") -> pd.Series:
    """Correlação de Spearman entre área colhida e rendimento, por grupo.

    Positiva: os municípios com mais área rendem mais, e a agregada fica acima da
    média simples. Negativa: o contrário. (Calculada sobre postos, sem scipy.)
    """
    postos = pd.DataFrame(
        {
            "area": df.groupby(por)["area_colhida_ha"].rank(),
            "rendimento": df.groupby(por)[REND].rank(),
            "grupo": df[por],
        }
    )
    correlacao = postos.groupby("grupo")[["area", "rendimento"]].apply(
        lambda g: g["area"].corr(g["rendimento"])
    )
    return correlacao.rename("spearman_area_rendimento").rename_axis(por)


def remover_extremos(
    df: pd.DataFrame, frac: float = 0.05, cauda: str = "superior", por: str = "uf"
) -> pd.DataFrame:
    """Tira, em cada grupo, os municípios além do percentil ``1 - frac`` (ou ``frac``).

    Com ``frac=0.05`` e ``cauda="superior"``, saem os municípios com rendimento acima
    do percentil 95 da própria UF, ou seja, os ~5% de maior rendimento.
    """
    grupos = df.groupby(por)[REND]
    if cauda == "superior":
        corte = grupos.transform(lambda s: s.quantile(1 - frac))
        manter = df[REND] <= corte
    elif cauda == "inferior":
        corte = grupos.transform(lambda s: s.quantile(frac))
        manter = df[REND] >= corte
    else:
        raise ValueError("cauda deve ser 'superior' ou 'inferior'")
    return df[manter]


def experimento_extremos(
    df: pd.DataFrame, frac: float = 0.05, cauda: str = "superior", por: str = "uf"
) -> pd.DataFrame:
    """Quanto média e mediana se movem quando os extremos de uma cauda saem."""
    antes = df.groupby(por)[REND].agg(n="size", media="mean", mediana="median")
    depois = (
        remover_extremos(df, frac=frac, cauda=cauda, por=por)
        .groupby(por)[REND]
        .agg(n="size", media="mean", mediana="median")
    )
    tabela = pd.DataFrame(
        {
            "n_municipios": antes["n"],
            "removidos": antes["n"] - depois["n"],
            "media": antes["media"],
            "media_sem": depois["media"],
            "mediana": antes["mediana"],
            "mediana_sem": depois["mediana"],
        }
    )
    tabela["delta_media"] = tabela["media_sem"] - tabela["media"]
    tabela["delta_mediana"] = tabela["mediana_sem"] - tabela["mediana"]
    tabela["delta_media_pct"] = tabela["delta_media"] / tabela["media"] * 100
    tabela["delta_mediana_pct"] = tabela["delta_mediana"] / tabela["mediana"] * 100
    return tabela
