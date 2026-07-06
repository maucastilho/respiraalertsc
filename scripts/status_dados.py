"""
Registro simples de status das fontes de dados.

Este arquivo evita fallback silencioso: quando uma API falha, os scripts podem
usar o ultimo dataset valido, mas deixam isso explicito em data/status_dados.json.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STATUS_PATH = DATA_DIR / "status_dados.json"


def carregar_status() -> dict:
    if not STATUS_PATH.exists():
        return {"fontes": {}, "historico": []}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"fontes": {}, "historico": []}


def registrar_status(fonte: str, status: str, mensagem: str, registros: int = 0) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    dados = carregar_status()
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "fonte": fonte,
        "status": status,
        "mensagem": mensagem,
        "registros": registros,
    }
    dados.setdefault("fontes", {})[fonte] = entrada
    historico = dados.setdefault("historico", [])
    historico.append(entrada)
    dados["historico"] = historico[-500:]
    STATUS_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
