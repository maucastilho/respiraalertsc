"""
processa_dados.py
=================
Une internações (DATASUS) e clima (INMET), gera dataset_final.csv
e calcula estatísticas: correlação de Pearson, Information Value,
média, mediana, desvio padrão, tendência temporal, variação anual.

Saída:
  data/dataset_final.csv
  data/indicadores_sc.json
  data/municipios_sc.json
"""

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ---------------------------------------------------------------------------
# Leitura dos CSVs
# ---------------------------------------------------------------------------

def ler_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Correlação de Pearson
# ---------------------------------------------------------------------------

def pearson(x: list[float], y: list[float]) -> float:
    """Coeficiente de correlação de Pearson entre duas listas numéricas."""
    n = len(x)
    if n < 3:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return round(num / (den_x * den_y), 4)


# ---------------------------------------------------------------------------
# Information Value (IV) — baseado em WoE com binagem por quartil de temperatura
# ---------------------------------------------------------------------------

def information_value(temps: list[float], internacoes: list[float]) -> tuple[float, str]:
    """
    Calcula IV simples: divide temperatura em 4 bins (quartis),
    mede separação relativa de internações altas/baixas.
    Classificação:
      < 0.02  → Negligenciável
      0.02–0.10 → Fraco
      0.10–0.30 → Médio
      > 0.30  → Forte
    """
    if len(temps) < 8:
        return 0.0, "Insuficiente"

    mediana_int = statistics.median(internacoes)
    n = len(temps)

    # Bins por quartil de temperatura
    sorted_t = sorted(temps)
    q1 = sorted_t[n // 4]
    q2 = sorted_t[n // 2]
    q3 = sorted_t[3 * n // 4]
    bins = [(-999, q1), (q1, q2), (q2, q3), (q3, 9999)]

    total_evento = sum(1 for i in internacoes if i > mediana_int) or 1
    total_nao    = sum(1 for i in internacoes if i <= mediana_int) or 1
    iv = 0.0

    for lo, hi in bins:
        indices = [idx for idx, t in enumerate(temps) if lo <= t < hi]
        if not indices:
            continue
        evento = sum(1 for i in indices if internacoes[i] > mediana_int) or 0.5
        nao    = sum(1 for i in indices if internacoes[i] <= mediana_int) or 0.5
        dist_e = evento / total_evento
        dist_n = nao / total_nao
        if dist_e > 0 and dist_n > 0:
            woe = math.log(dist_e / dist_n)
            iv += (dist_e - dist_n) * woe

    if iv < 0.02:
        cls = "Negligenciável"
    elif iv < 0.10:
        cls = "Fraco"
    elif iv < 0.30:
        cls = "Médio"
    else:
        cls = "Forte"

    return round(abs(iv), 4), cls


# ---------------------------------------------------------------------------
# Tendência temporal (regressão linear simples)
# ---------------------------------------------------------------------------

def tendencia_linear(valores: list[float]) -> dict:
    """Retorna slope, intercepto e direção da tendência."""
    n = len(valores)
    if n < 2:
        return {"slope": 0, "direcao": "estável"}
    x = list(range(n))
    mean_x = sum(x) / n
    mean_y = sum(valores) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, valores))
    den = sum((xi - mean_x) ** 2 for xi in x)
    slope = num / den if den != 0 else 0
    direcao = "crescente" if slope > 0.1 else ("decrescente" if slope < -0.1 else "estável")
    return {"slope": round(slope, 4), "direcao": direcao}


# ---------------------------------------------------------------------------
# Classificação de risco por temperatura
# ---------------------------------------------------------------------------

def classificar_risco_temp(temp: float) -> str:
    if temp >= 18:
        return "Baixo"
    if temp >= 15:
        return "Moderado"
    if temp >= 12:
        return "Alto"
    return "Muito Alto"


def classificar_vulnerabilidade(correlacao: float, iv: float, temp_media: float) -> str:
    score = 0
    if correlacao < -0.5:
        score += 2
    elif correlacao < -0.3:
        score += 1
    if iv > 0.3:
        score += 2
    elif iv > 0.1:
        score += 1
    if temp_media < 14:
        score += 2
    elif temp_media < 18:
        score += 1

    if score >= 5:
        return "Muito Alta"
    if score >= 3:
        return "Alta"
    if score >= 1:
        return "Moderada"
    return "Baixa"


# ---------------------------------------------------------------------------
# Insights automáticos
# ---------------------------------------------------------------------------

def gerar_insights(nome: str, correlacao: float, iv: float, iv_cls: str,
                   temp_media: float, tendencia: dict, mes_pico: int) -> list[str]:
    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    insights = []

    if correlacao < -0.4:
        insights.append(
            f"{nome} apresenta associação negativa entre temperatura e internações "
            f"(r={correlacao}): queda de temperatura correlaciona-se com aumento de internações."
        )
    elif correlacao > 0.4:
        insights.append(
            f"{nome} apresenta associação positiva entre temperatura e internações "
            f"(r={correlacao}): ambas as variáveis tendem a variar no mesmo sentido."
        )
    else:
        insights.append(
            f"A associação entre temperatura e internações em {nome} é moderada "
            f"(r={correlacao}), sugerindo influência de outros fatores."
        )

    if temp_media < 12:
        insights.append(
            f"As temperaturas médias históricas em {nome} frequentemente ficam abaixo de 12°C, "
            f"período associado a maior risco respiratório."
        )

    if mes_pico in [6, 7, 8]:
        insights.append(
            f"Os meses de inverno (especialmente {meses[mes_pico]}) concentram os maiores "
            f"volumes de internações respiratórias observados."
        )

    if iv_cls in ["Médio", "Forte"]:
        insights.append(
            f"O Information Value ({iv}) indica poder preditivo {iv_cls.lower()} da temperatura "
            f"sobre as internações neste município."
        )

    if tendencia["direcao"] == "crescente":
        insights.append(
            f"As internações em {nome} apresentam tendência de crescimento ao longo do período analisado."
        )
    elif tendencia["direcao"] == "decrescente":
        insights.append(
            f"As internações em {nome} apresentam tendência de redução no período analisado."
        )

    return insights


# ---------------------------------------------------------------------------
# Processamento principal
# ---------------------------------------------------------------------------

def processar() -> None:
    print("Lendo internacoes_sc.csv...")
    internacoes_raw = ler_csv(DATA_DIR / "internacoes_sc.csv")
    print("Lendo clima_sc.csv...")
    clima_raw = ler_csv(DATA_DIR / "clima_sc.csv")

    # Indexar clima por (municipio_ibge, ano, mes)
    clima_idx: dict[tuple, dict] = {}
    for row in clima_raw:
        key = (row["municipio_ibge"], int(row["ano"]), int(row["mes"]))
        clima_idx[key] = row

    # Montar dataset final
    dataset: list[dict] = []
    for row in internacoes_raw:
        key = (row["municipio_ibge"], int(row["ano"]), int(row["mes"]))
        clima = clima_idx.get(key, {})
        dataset.append({
            "municipio_ibge":  row["municipio_ibge"],
            "municipio_nome":  row["municipio_nome"],
            "ano":             int(row["ano"]),
            "mes":             int(row["mes"]),
            "internacoes":     int(row["internacoes"]),
            "temp_media":      float(clima.get("temp_media", 0)),
            "temp_min":        float(clima.get("temp_min", 0)),
            "temp_max":        float(clima.get("temp_max", 0)),
            "umidade":         float(clima.get("umidade", 0)),
            "precipitacao":    float(clima.get("precipitacao", 0)),
            "estacao_codigo":  clima.get("estacao_codigo", ""),
            "estacao_nome":    clima.get("estacao_nome", ""),
            "distancia_km":    float(clima.get("distancia_km", 0)),
        })

    # Salvar dataset_final.csv
    if dataset:
        campos = list(dataset[0].keys())
        with open(DATA_DIR / "dataset_final.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(dataset)
        print(f"dataset_final.csv: {len(dataset)} linhas")

    # ---------------------------------------------------------------------------
    # Calcular indicadores por município
    # ---------------------------------------------------------------------------
    por_municipio: dict[str, list[dict]] = defaultdict(list)
    for row in dataset:
        por_municipio[row["municipio_ibge"]].append(row)

    municipios_indicadores: list[dict] = []
    todos_correlacoes: list[float] = []
    total_internacoes_geral = sum(r["internacoes"] for r in dataset)

    for cod_mun, registros in por_municipio.items():
        nome = registros[0]["municipio_nome"]
        internacoes_list = [r["internacoes"] for r in registros]
        temps_list       = [r["temp_media"] for r in registros]

        corr = pearson(temps_list, internacoes_list)
        iv, iv_cls = information_value(temps_list, internacoes_list)

        temp_media   = statistics.mean(temps_list) if temps_list else 0
        temp_min_abs = min(r["temp_min"] for r in registros) if registros else 0
        temp_max_abs = max(r["temp_max"] for r in registros) if registros else 0

        int_media    = statistics.mean(internacoes_list) if internacoes_list else 0
        int_mediana  = statistics.median(internacoes_list) if internacoes_list else 0
        int_dp       = statistics.stdev(internacoes_list) if len(internacoes_list) > 1 else 0
        total_int    = sum(internacoes_list)

        tendencia    = tendencia_linear(internacoes_list)

        # Variação anual
        por_ano = defaultdict(list)
        for r in registros:
            por_ano[r["ano"]].append(r["internacoes"])
        anos_sorted = sorted(por_ano.keys())
        variacao_anual = {}
        for i in range(1, len(anos_sorted)):
            a_ant = anos_sorted[i - 1]
            a_cur = anos_sorted[i]
            soma_ant = sum(por_ano[a_ant])
            soma_cur = sum(por_ano[a_cur])
            if soma_ant > 0:
                variacao_anual[str(a_cur)] = round(((soma_cur - soma_ant) / soma_ant) * 100, 2)

        # Mês de pico
        por_mes = defaultdict(list)
        for r in registros:
            por_mes[r["mes"]].append(r["internacoes"])
        mes_pico = max(por_mes, key=lambda m: sum(por_mes[m]), default=7)

        # Sazonalidade (médias mensais)
        sazonalidade = {
            str(m): round(statistics.mean(vals), 1)
            for m, vals in sorted(por_mes.items())
        }

        risco = classificar_risco_temp(temp_media)
        vulnerabilidade = classificar_vulnerabilidade(corr, iv, temp_media)

        insights = gerar_insights(nome, corr, iv, iv_cls, temp_media, tendencia, mes_pico)

        estacao = registros[0].get("estacao_nome", "")
        dist_est = registros[0].get("distancia_km", 0)

        indicador = {
            "municipio_ibge":   cod_mun,
            "municipio_nome":   nome,
            "total_internacoes": total_int,
            "int_media_mensal": round(int_media, 2),
            "int_mediana":      round(int_mediana, 2),
            "int_desvio_padrao": round(int_dp, 2),
            "temp_media":       round(temp_media, 2),
            "temp_min_historica": round(temp_min_abs, 2),
            "temp_max_historica": round(temp_max_abs, 2),
            "correlacao_pearson": corr,
            "information_value": iv,
            "iv_classificacao": iv_cls,
            "tendencia_internacoes": tendencia,
            "variacao_anual":   variacao_anual,
            "mes_pico":         mes_pico,
            "sazonalidade_mensal": sazonalidade,
            "classificacao_risco": risco,
            "vulnerabilidade":  vulnerabilidade,
            "estacao_inmet":    estacao,
            "distancia_estacao_km": dist_est,
            "insights":         insights,
        }

        municipios_indicadores.append(indicador)
        if corr != 0:
            todos_correlacoes.append(corr)

    # ---------------------------------------------------------------------------
    # Indicadores estaduais
    # ---------------------------------------------------------------------------
    total_municipios = len(municipios_indicadores)
    correlacao_media_sc = round(statistics.mean(todos_correlacoes), 4) if todos_correlacoes else 0
    mun_maior_incidencia = max(municipios_indicadores, key=lambda m: m["total_internacoes"], default={})
    mun_menor_incidencia = min(municipios_indicadores, key=lambda m: m["total_internacoes"], default={})

    # Temperatura média SC
    all_temps = [r["temp_media"] for r in dataset if r["temp_media"] > 0]
    temp_media_sc = round(statistics.mean(all_temps), 2) if all_temps else 0

    indicadores_sc = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_municipios":   total_municipios,
        "total_internacoes":  total_internacoes_geral,
        "temp_media_estadual": temp_media_sc,
        "correlacao_media_estadual": correlacao_media_sc,
        "municipio_maior_incidencia": mun_maior_incidencia.get("municipio_nome", ""),
        "municipio_menor_incidencia": mun_menor_incidencia.get("municipio_nome", ""),
        "municipios": municipios_indicadores,
    }

    with open(DATA_DIR / "indicadores_sc.json", "w", encoding="utf-8") as f:
        json.dump(indicadores_sc, f, ensure_ascii=False, indent=2)
    print(f"indicadores_sc.json gerado com {total_municipios} municípios")

    # municipios_sc.json (mapa)
    municipios_mapa = [
        {
            "ibge":          m["municipio_ibge"],
            "nome":          m["municipio_nome"],
            "correlacao":    m["correlacao_pearson"],
            "iv":            m["information_value"],
            "iv_cls":        m["iv_classificacao"],
            "risco":         m["classificacao_risco"],
            "vulnerabilidade": m["vulnerabilidade"],
            "total_internacoes": m["total_internacoes"],
            "temp_media":    m["temp_media"],
            "estacao":       m["estacao_inmet"],
        }
        for m in municipios_indicadores
    ]
    with open(DATA_DIR / "municipios_sc.json", "w", encoding="utf-8") as f:
        json.dump(municipios_mapa, f, ensure_ascii=False, indent=2)
    print("municipios_sc.json gerado")


if __name__ == "__main__":
    processar()
