"""
utils.py
========
Funções utilitárias compartilhadas entre os scripts do RespirAlert SC.
"""

import json
import csv
import math
import logging
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def ler_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def salvar_json(dados: dict | list, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    log.info(f"JSON salvo: {path}")


def ler_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def salvar_csv(registros: list[dict], path: Path) -> None:
    if not registros:
        return
    campos = list(registros[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)
    log.info(f"CSV salvo: {path} ({len(registros)} linhas)")


# ---------------------------------------------------------------------------
# Matemática
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em km entre dois pontos geográficos."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0, min(1, a))))


def safe_mean(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def safe_median(valores: list[float]) -> float:
    if not valores:
        return 0.0
    s = sorted(valores)
    n = len(s)
    mid = n // 2
    return (s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2)


def safe_stdev(valores: list[float]) -> float:
    if len(valores) < 2:
        return 0.0
    m = safe_mean(valores)
    variance = sum((x - m) ** 2 for x in valores) / (len(valores) - 1)
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# Classificações
# ---------------------------------------------------------------------------

MESES_PTBR = [
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
]

MESES_COMPLETOS = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]


def classificar_risco(temp: float) -> str:
    if temp >= 18:
        return "Baixo"
    if temp >= 15:
        return "Moderado"
    if temp >= 12:
        return "Alto"
    return "Muito Alto"


def cor_risco(risco: str) -> str:
    mapa = {
        "Baixo":      "#10b981",
        "Moderado":   "#f59e0b",
        "Alto":       "#ef4444",
        "Muito Alto": "#7c3aed",
    }
    return mapa.get(risco, "#6b7280")


# ---------------------------------------------------------------------------
# Logs de execução
# ---------------------------------------------------------------------------

def registrar_execucao(modulo: str, sucesso: bool, mensagem: str = "") -> None:
    log_path = DATA_DIR / "logs.json"
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "modulo":    modulo,
        "sucesso":   sucesso,
        "mensagem":  mensagem,
    }
    historico = []
    if log_path.exists():
        try:
            with open(log_path, encoding="utf-8") as f:
                historico = json.load(f)
        except Exception:
            historico = []
    historico.append(entrada)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(historico[-500:], f, ensure_ascii=False, indent=2)
