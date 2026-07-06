"""
calcula_indicadores.py
======================
Calcula todos os indicadores estatísticos a partir do dataset_final.csv
e gera indicadores_sc.json e municipios_sc.json.

Separado do processa_dados.py para permitir recalcular indicadores
sem re-executar o pipeline de coleta.

Indicadores calculados:
  - Correlação de Pearson (temperatura × internações)
  - Information Value (IV) com bins por quartil
  - Média, mediana, desvio padrão das internações mensais
  - Tendência temporal (regressão linear simples)
  - Variação percentual anual
  - Sazonalidade mensal
  - Classificação de risco e vulnerabilidade
  - Insights automáticos
"""

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MUNICIPIOS_SEM_SERIE_LOCAL = {
    "4202057",
    "4212809",
    "4220000",
    "4203253",
    "4212239",
    "4212650",
}


def carregar_status_fontes() -> dict:
    path = DATA_DIR / "status_dados.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

# ============================================================
# Leitura
# ============================================================

def ler_dataset() -> list[dict]:
    path = DATA_DIR / "dataset_final.csv"
    if not path.exists():
        raise FileNotFoundError(f"dataset_final.csv não encontrado em {DATA_DIR}. Execute processa_dados.py primeiro.")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================================
# Estatísticas
# ============================================================

def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx, my = sum(x)/n, sum(y)/n
    num = sum((xi-mx)*(yi-my) for xi,yi in zip(x,y))
    dx  = math.sqrt(sum((xi-mx)**2 for xi in x))
    dy  = math.sqrt(sum((yi-my)**2 for yi in y))
    return round(num/(dx*dy), 4) if dx*dy else 0.0


def information_value(temps: list[float], internacoes: list[float]) -> tuple[float, str]:
    if len(temps) < 8:
        return 0.0, "Insuficiente"
    n = len(temps)
    mediana_int = statistics.median(internacoes)
    s = sorted(temps)
    q1, q2, q3 = s[n//4], s[n//2], s[3*n//4]
    bins = [(-999,q1),(q1,q2),(q2,q3),(q3,9999)]
    total_e = sum(1 for v in internacoes if v > mediana_int) or 1
    total_n = sum(1 for v in internacoes if v <= mediana_int) or 1
    iv = 0.0
    for lo, hi in bins:
        idx = [i for i,t in enumerate(temps) if lo <= t < hi]
        if not idx:
            continue
        ev = sum(1 for i in idx if internacoes[i] > mediana_int) or 0.5
        nv = sum(1 for i in idx if internacoes[i] <= mediana_int) or 0.5
        de, dn = ev/total_e, nv/total_n
        if de > 0 and dn > 0:
            iv += (de - dn) * math.log(de/dn)
    iv = abs(iv)
    cls = "Negligenciável" if iv < 0.02 else "Fraco" if iv < 0.10 else "Médio" if iv < 0.30 else "Forte"
    return round(iv, 4), cls


def tendencia(valores: list[float]) -> dict:
    n = len(valores)
    if n < 2:
        return {"slope": 0.0, "direcao": "estável"}
    x = list(range(n))
    mx, my = sum(x)/n, sum(valores)/n
    num = sum((xi-mx)*(yi-my) for xi,yi in zip(x,valores))
    den = sum((xi-mx)**2 for xi in x) or 1
    slope = num/den
    dir_ = "crescente" if slope > 0.1 else ("decrescente" if slope < -0.1 else "estável")
    return {"slope": round(slope,4), "direcao": dir_}


def classificar_risco(temp: float) -> str:
    if temp >= 18: return "Baixo"
    if temp >= 15: return "Moderado"
    if temp >= 12: return "Alto"
    return "Muito Alto"


def classificar_vulnerabilidade(corr: float, iv: float, temp: float) -> str:
    score = 0
    if corr < -0.5: score += 2
    elif corr < -0.3: score += 1
    if iv > 0.30: score += 2
    elif iv > 0.10: score += 1
    if temp < 14: score += 2
    elif temp < 18: score += 1
    return "Muito Alta" if score >= 5 else "Alta" if score >= 3 else "Moderada" if score >= 1 else "Baixa"


def classificar_pressao(total_int: int, corr: float, temp: float) -> str:
    score = 0
    if corr < -0.5: score += 2
    if temp < 18: score += 1
    if total_int > 10000: score += 2
    elif total_int > 5000: score += 1
    return "Crítica" if score >= 4 else "Alta" if score >= 3 else "Moderada" if score >= 2 else "Baixa"


def gerar_insights(nome, corr, iv, iv_cls, temp, tend, mes_pico) -> list[str]:
    MESES = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    ins = []
    if corr < -0.4:
        ins.append(f"{nome} apresenta associação negativa entre temperatura e internações (r={corr}): "
                   f"queda de temperatura correlaciona-se com aumento de internações.")
    elif corr > 0.4:
        ins.append(f"{nome} apresenta associação positiva entre temperatura e internações (r={corr}).")
    else:
        ins.append(f"A associação entre temperatura e internações em {nome} é moderada (r={corr}), "
                   f"sugerindo influência de múltiplos fatores.")
    if temp < 12:
        ins.append(f"Temperaturas médias históricas em {nome} frequentemente ficam abaixo de 12°C, "
                   f"período classificado como risco Muito Alto.")
    if mes_pico in range(6, 9):
        ins.append(f"Os meses de inverno (especialmente {MESES[mes_pico]}) concentram os maiores "
                   f"volumes de internações respiratórias observados.")
    if iv_cls in ("Médio", "Forte"):
        ins.append(f"O Information Value ({iv}) indica poder preditivo {iv_cls.lower()} da temperatura "
                   f"sobre as internações neste município.")
    if tend["direcao"] == "crescente":
        ins.append(f"As internações em {nome} apresentam tendência de crescimento ao longo do período.")
    elif tend["direcao"] == "decrescente":
        ins.append(f"As internações em {nome} apresentam tendência de redução no período analisado.")
    if corr < -0.7:
        ins.append(f"A associação observada em {nome} (r={corr}) é superior à magnitude média estadual, "
                   f"indicando sensibilidade climática elevada.")
    return ins


# ============================================================
# Cálculo principal
# ============================================================

def calcular_indicadores(dataset: list[dict]) -> dict:
    por_mun: dict[str, list[dict]] = defaultdict(list)
    for row in dataset:
        por_mun[row["municipio_ibge"]].append(row)

    municipios_out = []
    all_corr = []
    total_geral = 0

    for cod, registros in por_mun.items():
        nome = registros[0]["municipio_nome"]
        ints  = [int(r["internacoes"]) for r in registros]
        temps = [float(r["temp_media"]) for r in registros]
        total_geral += sum(ints)

        corr       = pearson(temps, ints)
        iv, iv_cls = information_value(temps, ints)
        temp_media = statistics.mean(temps) if temps else 0
        temp_min   = min(float(r["temp_min"]) for r in registros)
        temp_max   = max(float(r["temp_max"]) for r in registros)
        int_media  = statistics.mean(ints) if ints else 0
        int_med    = statistics.median(ints) if ints else 0
        int_dp     = statistics.stdev(ints) if len(ints) > 1 else 0
        tend       = tendencia(ints)

        # Variação anual
        por_ano = defaultdict(list)
        for r in registros: por_ano[r["ano"]].append(int(r["internacoes"]))
        anos = sorted(por_ano.keys())
        variacao_anual = {}
        for i in range(1, len(anos)):
            sa = sum(por_ano[anos[i-1]]) or 1
            sc = sum(por_ano[anos[i]])
            variacao_anual[anos[i]] = round(((sc-sa)/sa)*100, 2)

        # Sazonalidade
        por_mes = defaultdict(list)
        for r in registros: por_mes[int(r["mes"])].append(int(r["internacoes"]))
        sazonalidade = {str(m): round(statistics.mean(v),1) for m,v in sorted(por_mes.items())}
        mes_pico = max(por_mes, key=lambda m: sum(por_mes[m]), default=7)

        risco  = classificar_risco(temp_media)
        vulner = classificar_vulnerabilidade(corr, iv, temp_media)
        pressao = classificar_pressao(sum(ints), corr, temp_media)
        insights = gerar_insights(nome, corr, iv, iv_cls, temp_media, tend, mes_pico)

        estacao = registros[0].get("estacao_nome","")
        dist    = float(registros[0].get("distancia_km", 0))

        indicador = {
            "municipio_ibge":    cod,
            "municipio_nome":    nome,
            "total_internacoes": sum(ints),
            "int_media_mensal":  round(int_media, 2),
            "int_mediana":       round(int_med, 2),
            "int_desvio_padrao": round(int_dp, 2),
            "temp_media":        round(temp_media, 2),
            "temp_min_historica":round(temp_min, 2),
            "temp_max_historica":round(temp_max, 2),
            "correlacao_pearson":corr,
            "information_value": iv,
            "iv_classificacao":  iv_cls,
            "tendencia_internacoes": tend,
            "variacao_anual":    variacao_anual,
            "mes_pico":          mes_pico,
            "sazonalidade_mensal": sazonalidade,
            "classificacao_risco": risco,
            "vulnerabilidade":   vulner,
            "pressao_sus":       pressao,
            "estacao_inmet":     estacao,
            "distancia_estacao_km": dist,
            "insights":          insights,
            # séries temporais para gráficos (12 meses, média dos anos)
            "serie_temp_mensal": [round(statistics.mean([float(r["temp_media"]) for r in registros if int(r["mes"])==m]),2) if any(int(r["mes"])==m for r in registros) else 0 for m in range(1,13)],
            "serie_int_mensal":  [round(statistics.mean([int(r["internacoes"]) for r in registros if int(r["mes"])==m]),1) if any(int(r["mes"])==m for r in registros) else 0 for m in range(1,13)],
        }
        if cod in MUNICIPIOS_SEM_SERIE_LOCAL:
            indicador["dados_historicos"] = False
            indicador["observacao_dados"] = "Sem serie historica propria no pacote local; aguardando coleta oficial completa."
        municipios_out.append(indicador)
        if corr: all_corr.append(corr)

    # Ordenar por total de internações
    municipios_out.sort(key=lambda m: m["total_internacoes"], reverse=True)

    corr_media = round(statistics.mean(all_corr), 4) if all_corr else 0
    all_temps = [m["temp_media"] for m in municipios_out]
    temp_media_sc = round(statistics.mean(all_temps), 2) if all_temps else 0
    maior = municipios_out[0]["municipio_nome"] if municipios_out else ""
    menor = municipios_out[-1]["municipio_nome"] if municipios_out else ""

    return {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_municipios":   len(municipios_out),
        "total_internacoes":  total_geral,
        "temp_media_estadual": temp_media_sc,
        "correlacao_media_estadual": corr_media,
        "municipio_maior_incidencia": maior,
        "municipio_menor_incidencia": menor,
        "status_fontes": carregar_status_fontes(),
        "municipios": municipios_out,
    }


# ============================================================
# Salvar saídas
# ============================================================

def salvar_indicadores(dados: dict) -> None:
    with open(DATA_DIR / "indicadores_sc.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"indicadores_sc.json: {dados['total_municipios']} municípios")

    # municipios_sc.json (versão resumida para mapa/frontend)
    mapa = []
    for m in dados["municipios"]:
        item = {
        "ibge":           m["municipio_ibge"],
        "nome":           m["municipio_nome"],
        "correlacao":     m["correlacao_pearson"],
        "iv":             m["information_value"],
        "iv_cls":         m["iv_classificacao"],
        "risco":          m["classificacao_risco"],
        "vulnerabilidade":m["vulnerabilidade"],
        "pressao_sus":    m["pressao_sus"],
        "total_internacoes": m["total_internacoes"],
        "int_media_mensal": m["int_media_mensal"],
        "temp_media":     m["temp_media"],
        "estacao":        m["estacao_inmet"],
        "distancia_km":   m["distancia_estacao_km"],
        "mes_pico":       m["mes_pico"],
        "sazonalidade":   m["sazonalidade_mensal"],
        "serie_temp":     m["serie_temp_mensal"],
        "serie_int":      m["serie_int_mensal"],
        }
        if m.get("dados_historicos") is False:
            item["dados_historicos"] = False
            item["observacao_dados"] = m.get("observacao_dados", "Sem serie historica propria no pacote local.")
        mapa.append(item)

    with open(DATA_DIR / "municipios_sc.json", "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
    print(f"municipios_sc.json: {len(mapa)} registros")

    # Atualizar log
    log_path = DATA_DIR / "logs.json"
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "modulo": "calcula_indicadores",
        "sucesso": True,
        "mensagem": f"{dados['total_municipios']} municípios processados, {dados['total_internacoes']} internações"
    }
    hist = []
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            try: hist = json.load(f)
            except: hist = []
    hist.append(entrada)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(hist[-500:], f, ensure_ascii=False, indent=2)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    print("=== calcula_indicadores.py ===")
    print("Lendo dataset_final.csv...")
    dataset = ler_dataset()
    print(f"  {len(dataset)} registros carregados")
    print("Calculando indicadores...")
    dados = calcular_indicadores(dataset)
    print("Salvando JSONs...")
    salvar_indicadores(dados)
    print(f"=== Concluído: {dados['total_municipios']} municípios, correlação média SC = {dados['correlacao_media_estadual']} ===")
