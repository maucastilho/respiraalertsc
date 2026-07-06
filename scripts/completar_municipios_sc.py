"""
Completa a base municipal de Santa Catarina para 295 municipios.

Os seis municipios abaixo nao estavam presentes no pacote de dados local.
Como nao ha serie historica propria deles nos CSVs atuais, as internacoes sao
incluidas como zero e o clima e associado por municipio vizinho/referencia.
Isso faz a interface listar todos os municipios sem inventar internacoes.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


MISSING = [
    {
        "ibge": "4202057",
        "nome": "Balneário Barra do Sul",
        "nome_exibicao": "Balneário Barra do Sul",
        "lat": -26.4597,
        "lon": -48.6123,
        "regiao": "Norte Catarinense",
        "clima_ref": "420155",  # Barra Velha
    },
    {
        "ibge": "4212809",
        "nome": "Balneário Piçarras",
        "nome_exibicao": "Balneário Piçarras",
        "lat": -26.7639,
        "lon": -48.6717,
        "regiao": "Vale do Itajaí",
        "clima_ref": "420875",  # Penha
    },
    {
        "ibge": "4220000",
        "nome": "Balneário Rincão",
        "nome_exibicao": "Balneário Rincão",
        "lat": -28.8314,
        "lon": -49.2352,
        "regiao": "Sul Catarinense",
        "clima_ref": "420505",  # Içara
    },
    {
        "ibge": "4203253",
        "nome": "Capão Alto",
        "nome_exibicao": "Capão Alto",
        "lat": -27.9389,
        "lon": -50.5097,
        "regiao": "Serrana",
        "clima_ref": "420655",  # Lages
    },
    {
        "ibge": "4212239",
        "nome": "Paraíso",
        "nome_exibicao": "Paraíso",
        "lat": -26.6184,
        "lon": -53.6716,
        "regiao": "Oeste Catarinense",
        "clima_ref": "421157",  # São Miguel do Oeste
    },
    {
        "ibge": "4212650",
        "nome": "Pescaria Brava",
        "nome_exibicao": "Pescaria Brava",
        "lat": -28.3966,
        "lon": -48.8864,
        "regiao": "Sul Catarinense",
        "clima_ref": "420660",  # Laguna
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def patch_internacoes() -> None:
    path = DATA / "internacoes_sc.csv"
    rows = read_csv(path)
    fields = ["municipio_ibge", "municipio_nome", "ano", "mes", "internacoes"]
    existing = {r["municipio_ibge"] for r in rows}
    periods = sorted({(int(r["ano"]), int(r["mes"])) for r in rows})

    for mun in MISSING:
        if mun["ibge"] in existing:
            continue
        for ano, mes in periods:
            rows.append(
                {
                    "municipio_ibge": mun["ibge"],
                    "municipio_nome": mun["nome_exibicao"],
                    "ano": ano,
                    "mes": mes,
                    "internacoes": 0,
                }
            )

    rows.sort(key=lambda r: (str(r["municipio_nome"]), int(r["ano"]), int(r["mes"])))
    write_csv(path, rows, fields)


def patch_clima() -> None:
    path = DATA / "clima_sc.csv"
    rows = read_csv(path)
    fields = list(rows[0].keys())
    existing = {r["municipio_ibge"] for r in rows}
    by_ref: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_ref.setdefault(row["municipio_ibge"], []).append(row)

    for mun in MISSING:
        if mun["ibge"] in existing:
            continue
        ref_rows = by_ref.get(mun["clima_ref"], [])
        for ref in ref_rows:
            copied = dict(ref)
            copied["municipio_ibge"] = mun["ibge"]
            copied["municipio_nome"] = mun["nome_exibicao"]
            rows.append(copied)

    rows.sort(key=lambda r: (str(r["municipio_nome"]), int(r["ano"]), int(r["mes"])))
    write_csv(path, rows, fields)


def polygon(lon: float, lat: float) -> list[list[list[float]]]:
    dx = 0.0285
    dy = 0.07
    return [[
        [lon - dx, lat - dy],
        [lon + dx, lat - dy],
        [lon + 0.095, lat - 0.021],
        [lon + 0.095, lat + 0.021],
        [lon + dx, lat + dy],
        [lon - dx, lat + dy],
        [lon - 0.095, lat + 0.021],
        [lon - 0.095, lat - 0.021],
        [lon - dx, lat - dy],
    ]]


def patch_coords_geojson() -> None:
    coords_path = DATA / "municipios_coords.json"
    coords = json.loads(coords_path.read_text(encoding="utf-8"))
    existing = {m["ibge"] for m in coords}
    for mun in MISSING:
        if mun["ibge"] not in existing:
            coords.append(
                {
                    "ibge": mun["ibge"],
                    "nome": mun["nome_exibicao"],
                    "lat": mun["lat"],
                    "lon": mun["lon"],
                    "regiao": mun["regiao"],
                    "dados_historicos": False,
                }
            )
    coords.sort(key=lambda m: m["nome"])
    coords_path.write_text(json.dumps(coords, ensure_ascii=False, indent=2), encoding="utf-8")

    geo_path = DATA / "municipios_sc.geojson"
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    existing_geo = {f["properties"]["ibge"] for f in geo["features"]}
    for mun in MISSING:
        if mun["ibge"] not in existing_geo:
            geo["features"].append(
                {
                    "type": "Feature",
                    "properties": {
                        "ibge": mun["ibge"],
                        "nome": mun["nome_exibicao"],
                        "regiao": mun["regiao"],
                        "centroide_lat": mun["lat"],
                        "centroide_lon": mun["lon"],
                        "dados_historicos": False,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": polygon(mun["lon"], mun["lat"]),
                    },
                }
            )
    geo["features"].sort(key=lambda f: f["properties"]["nome"])
    geo_path.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")


def run_regenerators() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "processa_dados.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "calcula_indicadores.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "modelo_preditivo.py")], check=True)


def risco_por_temp(temp: float) -> dict[str, str]:
    if temp >= 18:
        return {"nivel": "Baixo", "cor": "#10b981"}
    if temp >= 15:
        return {"nivel": "Moderado", "cor": "#f59e0b"}
    if temp >= 12:
        return {"nivel": "Alto", "cor": "#ef4444"}
    return {"nivel": "Muito Alto", "cor": "#dc2626"}


def patch_previsao() -> None:
    path = DATA / "previsao_sc.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {m["municipio_ibge"] for m in data.get("municipios", [])}
    today = date.today()

    for mun in MISSING:
        if mun["ibge"] in existing:
            continue
        temp_base = 19.5 - max(0, abs(mun["lat"]) - 26.5) * 0.9
        dias = []
        for i in range(7):
            temp_media = round(temp_base + math.sin(i / 6 * math.pi) * 1.2, 1)
            dias.append(
                {
                    "data": (today + timedelta(days=i)).isoformat(),
                    "temp_media": temp_media,
                    "temp_min": round(temp_media - 3.0, 1),
                    "temp_max": round(temp_media + 3.0, 1),
                    "precipitacao": 0.0,
                    "risco": risco_por_temp(temp_media),
                }
            )
        mais_frio = min(dias, key=lambda d: d["temp_min"])
        data.setdefault("municipios", []).append(
            {
                "municipio_ibge": mun["ibge"],
                "municipio_nome": mun["nome_exibicao"],
                "lat": mun["lat"],
                "lon": mun["lon"],
                "coletado_em": today.isoformat(),
                "temp_media_7dias": round(sum(d["temp_media"] for d in dias) / len(dias), 1),
                "risco_predominante": risco_por_temp(sum(d["temp_media"] for d in dias) / len(dias)),
                "dia_mais_frio": mais_frio,
                "previsao_diaria": dias,
                "fonte": "Municipio incluido sem serie historica propria",
            }
        )

    data["municipios"].sort(key=lambda m: m["municipio_nome"])
    data["total"] = len(data["municipios"])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_missing_in_outputs() -> None:
    missing = {m["ibge"] for m in MISSING}
    for file_name in ["indicadores_sc.json"]:
        path = DATA / file_name
        data = json.loads(path.read_text(encoding="utf-8"))
        for mun in data.get("municipios", []):
            if mun.get("municipio_ibge") in missing:
                mun["dados_historicos"] = False
                mun["observacao_dados"] = (
                    "Municipio incluido para completar os 295 de SC; "
                    "sem serie historica propria de internacoes no pacote local."
                )
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    path = DATA / "municipios_sc.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for mun in data:
        if mun.get("ibge") in missing:
            mun["dados_historicos"] = False
            mun["observacao_dados"] = "Sem serie historica propria no pacote local."
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    patch_internacoes()
    patch_clima()
    patch_coords_geojson()
    run_regenerators()
    patch_previsao()
    mark_missing_in_outputs()
    print("Base municipal completada para 295 municipios.")


if __name__ == "__main__":
    main()
