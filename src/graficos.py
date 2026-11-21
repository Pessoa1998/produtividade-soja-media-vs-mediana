"""Gráficos do projeto, sempre com as mesmas cores para as três medidas:

    média dos municípios     azul
    mediana                  laranja
    produtividade agregada   verde-água

As barras e caixas ficam em cinza: são o contexto; as medidas são o destaque.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator, MultipleLocator

import metricas

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_FRACA = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
CONTEXTO = "#cfcdc6"  # barras do histograma
CONTEXTO_CLARO = "#e4e2dc"  # caixas do boxplot

CORES = {"media": "#2a78d6", "mediana": "#eb6834", "agregada": "#1baf7a"}
NOMES = {
    "media": "Média dos municípios",
    "mediana": "Mediana",
    "agregada": "Produtividade agregada (produção ÷ área)",
}

UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}  # fmt: skip

LARGURA = 9.0  # polegadas; salvo a 200 dpi = 1800 px


def _familia_fonte() -> str:
    disponiveis = {fonte.name for fonte in font_manager.fontManager.ttflist}
    preferidas = ["Inter", "Segoe UI", "Helvetica Neue", "Arial", "Liberation Sans"]
    return next((nome for nome in preferidas if nome in disponiveis), "DejaVu Sans")


def _estilo() -> dict:
    return {
        "font.family": _familia_fonte(),
        "font.size": 10,
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE,
        "savefig.dpi": 200,
        "axes.edgecolor": EIXO,
        "axes.linewidth": 0.8,
        "axes.labelcolor": TINTA_SECUNDARIA,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "xtick.color": EIXO,
        "ytick.color": EIXO,
        "xtick.labelcolor": TINTA_SECUNDARIA,
        "ytick.labelcolor": TINTA_SECUNDARIA,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "grid.color": GRADE,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "legend.frameon": False,
    }


def fmt(valor: float, casas: int = 1) -> str:
    """Número no formato brasileiro: 1.234,5."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def nota_fonte(ano: int, simulado: bool = False) -> str:
    if simulado:
        return "Dados SIMULADOS (src/simular.py), não são da PAM."
    return f"Fonte: IBGE, Produção Agrícola Municipal {ano} (SIDRA, tabela 5457). 1 saca = 60 kg."


def _cabecalho(fig, titulo: str, subtitulo: str, x: float = 0.035) -> None:
    fig.text(x, 0.955, titulo, ha="left", va="top", fontsize=14, fontweight="semibold", color=TINTA)
    fig.text(x, 0.905, subtitulo, ha="left", va="top", fontsize=10.5, color=TINTA_SECUNDARIA)


def _rodape(fig, texto: str, x: float = 0.035) -> None:
    fig.text(x, 0.025, texto, ha="left", va="bottom", fontsize=8.5, color=TINTA_FRACA)


def _legenda(fig, itens: list, rotulos: list[str], y: float, x: float = 0.035, ncol: int = 3) -> None:
    fig.legend(
        itens,
        rotulos,
        loc="upper left",
        bbox_to_anchor=(x - 0.008, y),
        ncol=ncol,
        fontsize=9.5,
        labelcolor=TINTA_SECUNDARIA,
        handlelength=1.6,
        columnspacing=1.6,
        borderaxespad=0,
    )


def _marcador(chave: str) -> dict:
    """Cada medida tem cor e forma próprias, para não depender só da cor."""
    if chave == "mediana":  # traço vertical, como a mediana no boxplot
        return {"marker": "|", "markersize": 15, "markeredgewidth": 2.6, "color": CORES[chave]}
    forma = {"media": ("o", 8.5), "agregada": ("D", 7.5)}[chave]
    return {
        "marker": forma[0],
        "markersize": forma[1],
        "markerfacecolor": CORES[chave],
        "markeredgecolor": SUPERFICIE,
        "markeredgewidth": 1.4,
    }


def _salvar(fig, caminho: str | Path | None) -> None:
    if caminho is not None:
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(caminho)


def _ano(df: pd.DataFrame) -> int:
    return int(df["ano"].iloc[0])


def histograma_uf(
    df: pd.DataFrame,
    uf: str,
    largura_classe: float = 2.0,
    limites: tuple[float, float] | None = None,
    simulado: bool = False,
    caminho: str | Path | None = None,
):
    """Distribuição do rendimento dos municípios de uma UF com média, mediana e agregada."""
    dados = df[df["uf"] == uf]
    rendimento = dados[metricas.REND]
    valores = {
        "media": rendimento.mean(),
        "mediana": rendimento.median(),
        "agregada": metricas.produtividade_agregada(dados),
    }
    if limites is None:
        limites = (np.floor(rendimento.min() / 10) * 10, np.ceil(rendimento.max() / 10) * 10)
    classes = np.arange(limites[0], limites[1] + largura_classe, largura_classe)

    with matplotlib.rc_context(_estilo()):
        fig = Figure(figsize=(LARGURA, 5.6))
        ax = fig.subplots()
        fig.subplots_adjust(left=0.075, right=0.975, top=0.73, bottom=0.17)
        ax.hist(rendimento, bins=classes, color=CONTEXTO, edgecolor=SUPERFICIE, linewidth=0.7, zorder=2)
        for chave in ["agregada", "mediana", "media"]:
            ax.axvline(valores[chave], color=CORES[chave], linewidth=2, zorder=3)

        ax.set_xlim(*limites)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.tick_params(pad=6)
        ax.set_xlabel("Rendimento (sc/ha)")
        ax.set_ylabel("Municípios")

        nome = UF_NOMES.get(uf, uf)
        _cabecalho(
            fig,
            f"{nome}: rendimento de soja por município, {_ano(df)}",
            f"{len(dados)} municípios com soja colhida; cada barra agrupa "
            f"{fmt(largura_classe, 0)} sc/ha. Três jeitos de resumir a mesma distribuição:",
        )
        # A legenda preenche por coluna; nesta ordem as linhas ficam
        # "média | mediana" e, embaixo, "agregada".
        ordem = ["media", "agregada", "mediana"]
        itens = [Line2D([], [], color=CORES[c], linewidth=2) for c in ordem]
        rotulos = [f"{NOMES[c]}: {fmt(valores[c])} sc/ha" for c in ordem]
        _legenda(fig, itens, rotulos, y=0.85, ncol=2)
        _rodape(fig, nota_fonte(_ano(df), simulado))
        _salvar(fig, caminho)
    return fig


def boxplot_ufs(
    df: pd.DataFrame,
    ufs: list[str] | None = None,
    simulado: bool = False,
    caminho: str | Path | None = None,
):
    """Um boxplot por UF, ordenado pela mediana, com a média marcada."""
    ufs = list(ufs) if ufs is not None else sorted(df["uf"].unique())
    medianas = df[df["uf"].isin(ufs)].groupby("uf")[metricas.REND].median()
    ordem = medianas.sort_values(ascending=False).index.tolist()
    grupos = [df.loc[df["uf"] == uf, metricas.REND].to_numpy() for uf in ordem]
    posicoes = np.arange(len(ordem), 0, -1)

    altura = 2.2 + 0.36 * len(ordem)
    with matplotlib.rc_context(_estilo()):
        fig = Figure(figsize=(LARGURA, altura))
        ax = fig.subplots()
        fig.subplots_adjust(left=0.115, right=0.975, top=1 - 1.35 / altura, bottom=1.0 / altura)
        caixas = ax.boxplot(
            grupos,
            positions=posicoes,
            orientation="horizontal",
            widths=0.42,
            patch_artist=True,
            showmeans=True,
            boxprops={"facecolor": CONTEXTO_CLARO, "linewidth": 0},
            medianprops={"color": CORES["mediana"], "linewidth": 2.6, "solid_capstyle": "butt"},
            meanprops=_marcador("media"),
            whiskerprops={"color": TINTA_FRACA, "linewidth": 0.8},
            capprops={"linewidth": 0},
            flierprops={
                "marker": "o",
                "markersize": 2.6,
                "markerfacecolor": TINTA_FRACA,
                "markeredgewidth": 0,
                "alpha": 0.55,
            },
        )
        for mediana in caixas["medians"]:  # mediana por cima da média quando coincidem
            mediana.set_zorder(4)
        n = df[df["uf"].isin(ordem)].groupby("uf").size()
        ax.set_yticks(posicoes, [f"{uf}  ({n[uf]})" for uf in ordem])
        ax.xaxis.set_major_locator(MultipleLocator(10))
        ax.xaxis.grid(True)
        ax.set_axisbelow(True)
        ax.tick_params(pad=6)
        ax.set_xlabel("Rendimento (sc/ha)")
        ax.set_ylim(0.4, len(ordem) + 0.6)

        _cabecalho(
            fig,
            f"Rendimento de soja por município, por UF, {_ano(df)}",
            "UFs ordenadas pela mediana; entre parênteses, o número de municípios com soja colhida.",
        )
        itens = [
            Line2D([], [], linestyle="", **_marcador("mediana")),
            Line2D([], [], linestyle="", **_marcador("media")),
            Patch(facecolor=CONTEXTO_CLARO, linewidth=0),
            Line2D([], [], marker="o", linestyle="", markersize=3, color=TINTA_FRACA, alpha=0.7),
        ]
        rotulos = ["Mediana", "Média", "Metade central dos municípios (P25 a P75)", "Municípios atípicos"]
        _legenda(fig, itens, rotulos, y=1 - 0.95 / altura, ncol=4)
        _rodape(fig, nota_fonte(_ano(df), simulado))
        _salvar(fig, caminho)
    return fig


def comparacao_ufs(
    tabela: pd.DataFrame,
    ano: int,
    total: pd.DataFrame | None = None,
    simulado: bool = False,
    caminho: str | Path | None = None,
):
    """Média, mediana e agregada lado a lado, uma linha por UF (saída de metricas.resumo)."""
    linhas = tabela.sort_values("agregada", ascending=True)
    if total is not None:
        linhas = pd.concat([linhas, total])
    rotulos_y = list(linhas.index)
    posicoes = np.arange(len(linhas))

    altura = 2.2 + 0.36 * len(linhas)
    with matplotlib.rc_context(_estilo()):
        fig = Figure(figsize=(LARGURA, altura))
        ax = fig.subplots()
        fig.subplots_adjust(left=0.115, right=0.975, top=1 - 1.35 / altura, bottom=1.0 / altura)
        for y, (_, linha) in zip(posicoes, linhas.iterrows(), strict=True):
            valores = [linha["media"], linha["mediana"], linha["agregada"]]
            ax.hlines(y, min(valores), max(valores), color=EIXO, linewidth=1.2, zorder=2)
            for camada, chave in enumerate(["agregada", "media", "mediana"], start=3):
                ax.plot([linha[chave]], [y], linestyle="", zorder=camada, **_marcador(chave))
        if total is not None:
            ax.axhline(len(linhas) - 1.5, color=GRADE, linewidth=0.8)
        ax.set_yticks(posicoes, rotulos_y)
        if total is not None:
            ax.get_yticklabels()[-1].set_fontweight("semibold")
            ax.get_yticklabels()[-1].set_color(TINTA)
        ax.xaxis.grid(True)
        ax.set_axisbelow(True)
        ax.tick_params(pad=6)
        ax.set_xlabel("Rendimento (sc/ha)")
        ax.set_ylim(-0.6, len(linhas) - 0.4)

        _cabecalho(
            fig,
            f"Três números para a mesma safra de soja, {ano}",
            "UFs ordenadas pela produtividade agregada. Quanto mais longa a linha cinza, "
            "mais os três números discordam.",
        )
        itens = [Line2D([], [], linestyle="", **_marcador(c)) for c in CORES]
        _legenda(fig, itens, [NOMES[c] for c in CORES], y=1 - 0.95 / altura, ncol=3)
        _rodape(fig, nota_fonte(ano, simulado))
        _salvar(fig, caminho)
    return fig
