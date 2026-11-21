import numpy as np
import pandas as pd
import pytest

import metricas


def municipios(rendimentos_sc, areas, uf="XX"):
    """Municípios de teste em que rendimento = produção / área, como na PAM."""
    rendimento = np.asarray(rendimentos_sc, dtype=float)
    area = np.asarray(areas, dtype=float)
    return pd.DataFrame(
        {
            "uf": uf,
            "area_colhida_ha": area,
            "producao_t": area * rendimento * 60 / 1000,
            "rendimento_kg_ha": rendimento * 60,
            "rendimento_sc_ha": rendimento,
        }
    )


def test_agregada_e_producao_total_sobre_area_total():
    df = municipios([50, 70], [100, 300])  # (100*50 + 300*70) / 400 = 65
    assert metricas.produtividade_agregada(df) == pytest.approx(65)


def test_media_ponderada_pela_area_e_a_propria_agregada():
    rng = np.random.default_rng(0)
    df = municipios(rng.uniform(20, 75, 200), rng.uniform(10, 50_000, 200))
    linha = metricas.resumo(df).loc["XX"]
    assert linha["media_ponderada_area"] == pytest.approx(linha["agregada"])


def test_resumo_media_mediana_quartis_e_diferenca():
    linha = metricas.resumo(municipios([10, 50, 55, 60, 65], [1] * 5)).loc["XX"]
    assert linha["n_municipios"] == 5
    assert linha["media"] == pytest.approx(48)
    assert linha["mediana"] == pytest.approx(55)
    assert (linha["p25"], linha["p75"]) == (pytest.approx(50), pytest.approx(60))
    assert linha["dif_media_mediana_pct"] == pytest.approx((48 / 55 - 1) * 100)


def test_resumo_total_junta_todas_as_ufs():
    df = pd.concat([municipios([40, 60], [1, 1], "AA"), municipios([50], [2], "BB")])
    total = metricas.resumo_total(df)
    assert total.index.tolist() == ["Brasil"]
    assert total.loc["Brasil", "n_municipios"] == 3
    assert total.loc["Brasil", "media"] == pytest.approx(50)


def test_destacar_compara_o_modulo_da_diferenca():
    tabela = pd.DataFrame({"dif_media_mediana_pct": [-7.0, 3.0, 6.0]}, index=["A", "B", "C"])
    assert metricas.destacar(tabela, limiar_pct=5).index.tolist() == ["A", "C"]


def test_maior_distorcao_respeita_candidatas_e_exclusao():
    tabela = pd.DataFrame({"dif_media_mediana_pct": [-9.0, 4.0, -6.0]}, index=["MT", "PR", "BA"])
    assert metricas.maior_distorcao(tabela) == "MT"
    assert metricas.maior_distorcao(tabela, excluir=("MT",)) == "BA"
    assert metricas.maior_distorcao(tabela, candidatas=["PR", "BA"], excluir=("BA",)) == "PR"


def test_remover_extremos_corta_no_percentil_da_cauda():
    df = municipios(np.arange(1, 101), np.ones(100))
    sem_topo = metricas.remover_extremos(df, frac=0.05, cauda="superior")
    sem_base = metricas.remover_extremos(df, frac=0.05, cauda="inferior")
    assert len(sem_topo) == 95 and sem_topo["rendimento_sc_ha"].max() == 95  # P95 = 95,05
    assert len(sem_base) == 95 and sem_base["rendimento_sc_ha"].min() == 6  # P5 = 5,95
    with pytest.raises(ValueError):
        metricas.remover_extremos(df, cauda="meio")


def test_remover_extremos_trabalha_dentro_de_cada_uf():
    df = pd.concat(
        [municipios(np.arange(1, 21), np.ones(20), "AA"), municipios(np.arange(101, 121), np.ones(20), "BB")]
    )
    assert metricas.remover_extremos(df).groupby("uf").size().to_dict() == {"AA": 19, "BB": 19}


def test_experimento_um_extremo_move_a_media_e_quase_nao_move_a_mediana():
    df = municipios(list(range(45, 64)) + [150], np.ones(20))
    linha = metricas.experimento_extremos(df).loc["XX"]
    assert linha["removidos"] == 1
    assert linha["delta_media"] == pytest.approx(54 - 58.8)  # 58,8 -> 54,0
    assert linha["delta_mediana"] == pytest.approx(-0.5)  # 54,5 -> 54,0


def test_correlacao_area_rendimento_tem_o_sinal_certo():
    sobe = municipios([40, 50, 60, 70], [10, 20, 30, 40], "AA")
    desce = municipios([70, 60, 50, 40], [10, 20, 30, 40], "BB")
    correlacao = metricas.correlacao_area_rendimento(pd.concat([sobe, desce]))
    assert correlacao["AA"] == pytest.approx(1)
    assert correlacao["BB"] == pytest.approx(-1)
