import pandas as pd
import pytest

import coleta_sidra as cs
import metricas
import simular

CABECALHO = {
    "NC": "Nível Territorial (Código)",
    "NN": "Nível Territorial",
    "MC": "Unidade de Medida (Código)",
    "MN": "Unidade de Medida",
    "V": "Valor",
    "D1C": "Município (Código)",
    "D1N": "Município",
    "D2C": "Variável (Código)",
    "D2N": "Variável",
    "D3C": "Ano (Código)",
    "D3N": "Ano",
    "D4C": "Produto das lavouras temporárias e permanentes (Código)",
    "D4N": "Produto das lavouras temporárias e permanentes",
}


def resposta_api():
    """Recorte no formato da API: cabeçalho + 3 registros (variáveis) por município."""
    municipios = [
        ("5105259", "Lucas do Rio Verde - MT", "232000", "918720", "3960"),
        ("4314902", "Porto Alegre - RS", "-", "-", "-"),
        ("2408102", "Natal - RN", "...", "...", "..."),
        ("5300108", "Brasília - DF", "87000", "328860", "3780"),
    ]
    registros = [CABECALHO]
    for codigo, nome, *valores in municipios:
        for variavel, valor in zip(["216", "214", "112"], valores, strict=True):
            registros.append(
                {
                    "NC": "6", "NN": "Município", "MC": "0", "MN": "unidade", "V": valor,
                    "D1C": codigo, "D1N": nome, "D2C": variavel, "D2N": "variável",
                    "D3C": "2025", "D3N": "2025", "D4C": "40124", "D4N": "Soja (em grão)",
                }
            )  # fmt: skip
    return registros


def test_montar_url():
    assert cs.montar_url(2025) == (
        "https://apisidra.ibge.gov.br/values/t/5457/n6/all/v/216,214,112/p/2025/c782/40124"
    )
    assert cs.montar_url().endswith("/p/last%201/c782/40124")


def test_bruto_descarta_so_o_cabecalho_e_nao_altera_valores():
    bruto = cs.registros_para_bruto(resposta_api())
    assert len(bruto) == 12
    assert list(bruto.columns) == list(CABECALHO)
    assert (bruto["V"] == "-").sum() == 3 and (bruto["V"] == "...").sum() == 3


def test_limpar_gera_o_esquema_e_tira_municipios_sem_area():
    limpo = cs.limpar(cs.registros_para_bruto(resposta_api()))
    assert list(limpo.columns) == cs.COLUNAS
    assert limpo["cod_municipio"].tolist() == ["5300108", "5105259"]  # DF e MT; RS e RN saem
    lucas = limpo.set_index("cod_municipio").loc["5105259"]
    assert (lucas["municipio"], lucas["uf"], lucas["ano"]) == ("Lucas do Rio Verde", "MT", 2025)
    assert lucas["rendimento_sc_ha"] == pytest.approx(3960 / 60)


def test_sinal_desconhecido_vira_erro_em_vez_de_nulo():
    registros = resposta_api()
    registros[1]["V"] = "abc"
    with pytest.raises(ValueError):
        cs.limpar(cs.registros_para_bruto(registros))


def test_csv_processado_volta_igual(tmp_path):
    limpo = cs.limpar(cs.registros_para_bruto(resposta_api()))
    caminho = tmp_path / "soja.csv"
    limpo.to_csv(caminho, index=False, float_format="%.10g")
    pd.testing.assert_frame_equal(cs.ler_processado(caminho), limpo, check_dtype=False)


def test_simulado_segue_o_esquema_e_se_identifica():
    df = simular.simular(semente=1)
    assert list(df.columns) == cs.COLUNAS
    assert df["uf"].str.startswith("SIM-").all()
    assert df["municipio"].str.startswith("Município simulado").all()
    assert (df["area_colhida_ha"] > 0).all()


def test_simulado_reproduz_os_tres_casos():
    tabela = metricas.resumo(simular.simular(semente=42))
    assert tabela.loc["SIM-A", "dif_media_mediana_pct"] < -2  # cauda inferior
    assert tabela.loc["SIM-B", "dif_media_mediana_pct"] > 2  # cauda superior
    assert abs(tabela.loc["SIM-C", "dif_media_mediana_pct"]) < 2  # quase simétrica
