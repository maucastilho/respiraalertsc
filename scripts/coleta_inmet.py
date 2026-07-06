"""
coleta_inmet.py
===============
Coleta dados meteorolÃ³gicos do INMET (Instituto Nacional de Meteorologia)
para as estaÃ§Ãµes de Santa Catarina e associa cada municÃ­pio Ã  estaÃ§Ã£o mais prÃ³xima
usando distÃ¢ncia euclidiana entre coordenadas geogrÃ¡ficas.

Fontes:
  API INMET: https://apitempo.inmet.gov.br/
  Dados histÃ³ricos: https://bdmep.inmet.gov.br/

Fluxo resiliente:
  ETAPA 1 â†’ API INMET (dados recentes)
  ETAPA 2 â†’ BDMEP download de arquivos CSV histÃ³ricos
  ETAPA 3 â†’ Fallback do repositÃ³rio
"""

import csv
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from status_dados import registrar_status

# ---------------------------------------------------------------------------
# ConfiguraÃ§Ã£o
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DATA_DIR / "coleta_inmet.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

CLIMA_CSV = DATA_DIR / "clima_sc.csv"
ESTACOES_JSON = DATA_DIR / "estacoes_sc.json"

INMET_API_BASE = "https://apitempo.inmet.gov.br"
TOKEN_INMET = os.getenv("INMET_TOKEN", "")  # opcional; muitas rotas sÃ£o abertas

# ---------------------------------------------------------------------------
# EstaÃ§Ãµes INMET em Santa Catarina (prÃ©-mapeadas)
# Fonte: https://portal.inmet.gov.br/paginas/catalogoDE
# ---------------------------------------------------------------------------
ESTACOES_SC = [
    {"codigo": "A806", "nome": "FlorianÃ³polis",   "lat": -27.5954, "lon": -48.5480, "altitude": 11.13},
    {"codigo": "A826", "nome": "Joinville",        "lat": -26.2306, "lon": -48.8447, "altitude": 4.0},
    {"codigo": "A822", "nome": "Blumenau",         "lat": -26.9060, "lon": -49.0790, "altitude": 14.0},
    {"codigo": "A853", "nome": "ChapecÃ³",          "lat": -27.1001, "lon": -52.6143, "altitude": 679.0},
    {"codigo": "A849", "nome": "Lages",            "lat": -27.8011, "lon": -50.3291, "altitude": 937.0},
    {"codigo": "A856", "nome": "CriciÃºma",         "lat": -28.6749, "lon": -49.3688, "altitude": 46.0},
    {"codigo": "A852", "nome": "CaÃ§ador",          "lat": -26.7703, "lon": -51.0183, "altitude": 960.0},
    {"codigo": "A809", "nome": "ItajaÃ­",           "lat": -26.9052, "lon": -48.6546, "altitude": 4.0},
    {"codigo": "A823", "nome": "Campos Novos",     "lat": -27.4020, "lon": -51.2127, "altitude": 940.0},
    {"codigo": "A832", "nome": "SÃ£o Joaquim",      "lat": -28.2957, "lon": -49.9316, "altitude": 1415.0},
    {"codigo": "A858", "nome": "AraranguÃ¡",        "lat": -28.9330, "lon": -49.4875, "altitude": 16.0},
    {"codigo": "A848", "nome": "Curitibanos",      "lat": -27.2847, "lon": -50.5949, "altitude": 987.0},
    {"codigo": "A862", "nome": "XanxerÃª",          "lat": -26.8759, "lon": -52.4002, "altitude": 793.0},
    {"codigo": "A827", "nome": "Mafra",            "lat": -26.1144, "lon": -49.8027, "altitude": 795.0},
    {"codigo": "A807", "nome": "Laguna",           "lat": -28.4805, "lon": -48.7806, "altitude": 6.0},
    {"codigo": "A801", "nome": "Urussanga",        "lat": -28.5220, "lon": -49.3167, "altitude": 48.0},
    {"codigo": "A861", "nome": "ConcÃ³rdia",        "lat": -27.2333, "lon": -52.0167, "altitude": 569.0},
    {"codigo": "A863", "nome": "SÃ£o Miguel do Oeste","lat": -26.7260, "lon": -53.5046, "altitude": 653.0},
    {"codigo": "A876", "nome": "DionÃ­sio Cerqueira","lat": -26.2616, "lon": -53.6365, "altitude": 757.0},
    {"codigo": "A812", "nome": "Porto UniÃ£o",      "lat": -26.2277, "lon": -51.0801, "altitude": 763.0},
]

# ---------------------------------------------------------------------------
# MunicÃ­pios SC com coordenadas (amostra representativa)
# ---------------------------------------------------------------------------
MUNICIPIOS_COORDS = {
    "420005": (-27.4883, -51.0222),  # Abdon Batista
    "420010": (-26.5570, -52.3220),  # Abelardo Luz
    "420135": (-26.9904, -48.6345),  # BalneÃ¡rio CamboriÃº
    "420180": (-26.9195, -49.0658),  # Blumenau
    "420235": (-26.7742, -51.0147),  # CaÃ§ador
    "420315": (-27.1013, -52.6189),  # ChapecÃ³
    "420355": (-28.6783, -49.3695),  # CriciÃºma
    "420410": (-27.5954, -48.5480),  # FlorianÃ³polis
    "420580": (-26.9010, -48.6634),  # ItajaÃ­
    "420585": (-27.0864, -48.6213),  # Itapema
    "420620": (-26.4853, -49.0710),  # JaraguÃ¡ do Sul
    "420635": (-26.3044, -48.8457),  # Joinville
    "420655": (-27.8167, -50.3291),  # Lages
    "420660": (-28.4839, -48.7836),  # Laguna
    "420705": (-26.1137, -49.8055),  # Mafra
    "420780": (-26.8953, -48.6534),  # Navegantes
    "420825": (-27.6368, -48.6696),  # PalhoÃ§a
    "420830": (-26.6210, -53.3032),  # Palma Sola
    "420935": (-26.2277, -51.0789),  # Porto UniÃ£o
    "421005": (-26.3332, -49.5106),  # Rio Negrinho
    "421070": (-26.2527, -49.3902),  # SÃ£o Bento do Sul
    "421100": (-26.2463, -48.6420),  # SÃ£o Francisco do Sul
    "421120": (-28.2958, -49.9330),  # SÃ£o Joaquim
    "421125": (-27.6055, -48.6342),  # SÃ£o JosÃ©
    "421245": (-28.4670, -49.0130),  # TubarÃ£o
    "421290": (-27.0062, -51.1565),  # Videira
    "421305": (-26.8759, -52.4002),  # XanxerÃª
}
MUNICIPIOS_COORDS.update({
    "4202057": (-26.4597, -48.6123),  # Balneário Barra do Sul
    "4212809": (-26.7639, -48.6717),  # Balneário Piçarras
    "4220000": (-28.8314, -49.2352),  # Balneário Rincão
    "4203253": (-27.9389, -50.5097),  # Capão Alto
    "4212239": (-26.6184, -53.6716),  # Paraíso
    "4212650": (-28.3966, -48.8864),  # Pescaria Brava
})

# ---------------------------------------------------------------------------
# FunÃ§Ãµes auxiliares
# ---------------------------------------------------------------------------
def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine simplificado para distÃ¢ncias em SC (escala <500km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def estacao_proxima(lat: float, lon: float) -> dict:
    """Alias para estacao_mais_proxima."""
    return estacao_mais_proxima(lat, lon)


def estacao_mais_proxima(lat: float, lon: float) -> dict:
    """Retorna a estaÃ§Ã£o INMET mais prÃ³xima de uma coordenada."""
    return min(ESTACOES_SC, key=lambda e: distancia_km(lat, lon, e["lat"], e["lon"]))


# ---------------------------------------------------------------------------
# ETAPA 1 â€” API INMET
# ---------------------------------------------------------------------------
def coletar_via_api_inmet(codigo_estacao: str, data_ini: str, data_fim: str) -> list[dict] | None:
    """
    Consulta dados horÃ¡rios da estaÃ§Ã£o automÃ¡tica via API INMET.
    data_ini / data_fim: "YYYY-MM-DD"
    """
    url = f"{INMET_API_BASE}/estacao/{data_ini}/{data_fim}/{codigo_estacao}"
    headers = {}
    if TOKEN_INMET:
        headers["Authorization"] = f"Bearer {TOKEN_INMET}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            log.warning(f"API INMET HTTP {resp.status_code} para estaÃ§Ã£o {codigo_estacao}")
            return None

        dados = resp.json()
        if not dados:
            return None

        # Agrupa por mÃªs
        mensais: dict[str, dict] = {}
        for obs in dados:
            try:
                mes_key = obs["DT_MEDICAO"][:7]  # "YYYY-MM"
                t_med = float(obs.get("TEM_MED") or obs.get("TEMP_MED") or 0)
                t_min = float(obs.get("TEM_MIN") or obs.get("TEMP_MIN") or 0)
                t_max = float(obs.get("TEM_MAX") or obs.get("TEMP_MAX") or 0)
                umid  = float(obs.get("UMD_MED") or obs.get("UMED_INS") or 0)
                prec  = float(obs.get("CHUVA") or 0)

                if mes_key not in mensais:
                    mensais[mes_key] = {"t_med": [], "t_min": [], "t_max": [], "umid": [], "prec": 0.0}
                mensais[mes_key]["t_med"].append(t_med)
                mensais[mes_key]["t_min"].append(t_min)
                mensais[mes_key]["t_max"].append(t_max)
                mensais[mes_key]["umid"].append(umid)
                mensais[mes_key]["prec"] += prec
            except (KeyError, ValueError):
                continue

        resultado = []
        for mes_key, vals in mensais.items():
            ano, mes = map(int, mes_key.split("-"))
            n = len(vals["t_med"]) or 1
            resultado.append({
                "estacao_codigo": codigo_estacao,
                "ano": ano,
                "mes": mes,
                "temp_media": round(sum(vals["t_med"]) / n, 2),
                "temp_min":   round(min(vals["t_min"]), 2),
                "temp_max":   round(max(vals["t_max"]), 2),
                "umidade":    round(sum(vals["umid"]) / n, 2),
                "precipitacao": round(vals["prec"], 2),
            })

        log.info(f"API INMET: {len(resultado)} meses para estaÃ§Ã£o {codigo_estacao}")
        return resultado

    except Exception as exc:
        log.warning(f"API INMET falhou para {codigo_estacao}: {exc}")
        return None


# ---------------------------------------------------------------------------
# ETAPA 2 â€” BDMEP (download CSV histÃ³rico)
# ---------------------------------------------------------------------------
def coletar_via_bdmep(codigo_estacao: str, ano: int) -> list[dict] | None:
    """
    Tenta baixar CSV histÃ³rico do BDMEP para uma estaÃ§Ã£o e ano.
    URL pÃºblica: https://bdmep.inmet.gov.br/...
    """
    # O BDMEP nÃ£o tem API REST aberta para download automatizado;
    # registramos a limitaÃ§Ã£o e retornamos None para acionar o fallback.
    log.info(f"BDMEP: download automatizado nÃ£o disponÃ­vel para {codigo_estacao}/{ano}")
    return None


# ---------------------------------------------------------------------------
# ETAPA 3 â€” Fallback
# ---------------------------------------------------------------------------
def carregar_fallback_clima() -> list[dict]:
    if not CLIMA_CSV.exists():
        log.error("Arquivo fallback clima_sc.csv nÃ£o encontrado!")
        return []
    registros = []
    with open(CLIMA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                registros.append({
                    "municipio_ibge": row["municipio_ibge"],
                    "municipio_nome": row["municipio_nome"],
                    "estacao_codigo": row.get("estacao_codigo", ""),
                    "estacao_nome":   row.get("estacao_nome", ""),
                    "distancia_km":   float(row.get("distancia_km", 0)),
                    "ano":            int(row["ano"]),
                    "mes":            int(row["mes"]),
                    "temp_media":     float(row.get("temp_media", 0)),
                    "temp_min":       float(row.get("temp_min", 0)),
                    "temp_max":       float(row.get("temp_max", 0)),
                    "umidade":        float(row.get("umidade", 0)),
                    "precipitacao":   float(row.get("precipitacao", 0)),
                })
            except (KeyError, ValueError):
                continue
    log.info(f"Ultimo dataset local de clima: {len(registros)} registros")
    return registros


# ---------------------------------------------------------------------------
# Coleta consolidada
# ---------------------------------------------------------------------------
def contar_municipios(registros: list[dict]) -> int:
    return len({r.get("municipio_ibge") for r in registros if r.get("municipio_ibge")})


def coletar_clima() -> tuple[list[dict], str]:
    """
    Coleta dados climaticos oficiais. Se a coleta vier incompleta,
    mantem o ultimo CSV valido local sem sobrescrever.
    """
    anos = list(range(1990, datetime.now().year + 1))
    dados_por_estacao: dict[str, list[dict]] = {}

    for estacao in ESTACOES_SC:
        cod = estacao["codigo"]
        dados_estacao = []

        for ano in anos:
            data_ini = f"{ano}-01-01"
            data_fim = f"{ano}-12-31"
            resultado = coletar_via_api_inmet(cod, data_ini, data_fim)
            if resultado:
                dados_estacao.extend(resultado)
            else:
                resultado = coletar_via_bdmep(cod, ano)
                if resultado:
                    dados_estacao.extend(resultado)
            time.sleep(0.3)

        if dados_estacao:
            dados_por_estacao[cod] = dados_estacao
            log.info(f"Estacao {cod} ({estacao['nome']}): {len(dados_estacao)} registros")

    if not dados_por_estacao:
        motivo = "Nenhuma estacao INMET retornou dados. Mantendo ultimo dataset valido local."
        log.warning(motivo)
        registrar_status("INMET", "ultimo_valido", motivo, 0)
        return carregar_fallback_clima(), "ultimo_valido"

    registros_finais = []
    for cod_mun, (lat, lon) in MUNICIPIOS_COORDS.items():
        est = estacao_mais_proxima(lat, lon)
        dist = distancia_km(lat, lon, est["lat"], est["lon"])
        dados_est = dados_por_estacao.get(est["codigo"], [])
        from coleta_datasus import MUNICIPIOS_SC
        nome_mun = MUNICIPIOS_SC.get(cod_mun, "Desconhecido")
        for obs in dados_est:
            registros_finais.append({
                "municipio_ibge":  cod_mun,
                "municipio_nome":  nome_mun,
                "estacao_codigo":  est["codigo"],
                "estacao_nome":    est["nome"],
                "distancia_km":    round(dist, 1),
                "ano":             obs["ano"],
                "mes":             obs["mes"],
                "temp_media":      obs["temp_media"],
                "temp_min":        obs["temp_min"],
                "temp_max":        obs["temp_max"],
                "umidade":         obs["umidade"],
                "precipitacao":    obs["precipitacao"],
            })

    total_municipios = contar_municipios(registros_finais)
    if total_municipios < 295:
        motivo = (
            f"Coleta INMET incompleta ({total_municipios} municipios). "
            "Mantendo ultimo dataset valido local."
        )
        log.warning(motivo)
        registrar_status("INMET", "ultimo_valido", motivo, len(registros_finais))
        return carregar_fallback_clima(), "ultimo_valido"

    registrar_status(
        "INMET",
        "oficial_atualizado",
        "Clima atualizado a partir de fonte oficial INMET.",
        len(registros_finais),
    )
    return registros_finais, "oficial"

# ---------------------------------------------------------------------------
# Salvar
# ---------------------------------------------------------------------------
def salvar_csv_clima(registros: list[dict]) -> None:
    if not registros:
        return
    campos = list(registros[0].keys())
    with open(CLIMA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)
    log.info(f"clima_sc.csv salvo: {len(registros)} linhas")


def salvar_estacoes_json() -> None:
    with open(ESTACOES_JSON, "w", encoding="utf-8") as f:
        json.dump(ESTACOES_SC, f, ensure_ascii=False, indent=2)
    log.info(f"estacoes_sc.json salvo")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log.info("=== InÃ­cio da coleta INMET ===")
    salvar_estacoes_json()
    registros, fonte = coletar_clima()
    if fonte == "oficial":
        salvar_csv_clima(registros)
    else:
        log.warning("CSV de clima mantido sem sobrescrever: usando ultimo dataset valido.")
    log.info(f"=== Coleta climÃ¡tica concluÃ­da: {len(registros)} registros ===")


