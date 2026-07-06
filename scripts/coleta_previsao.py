"""
coleta_previsao.py
==================
Coleta previsÃ£o meteorolÃ³gica dos prÃ³ximos 7 dias via API Open-Meteo
(gratuita, sem token, sem cadastro) para os municÃ­pios de SC.

Gera: data/previsao_sc.json

Executado pelo GitHub Actions junto com a coleta mensal.
TambÃ©m pode ser chamado a qualquer momento:
    python coleta_previsao.py

API Open-Meteo: https://open-meteo.com/
DocumentaÃ§Ã£o:   https://open-meteo.com/en/docs
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from status_dados import registrar_status

try:
    import requests
    HTTP_LIB = 'requests'
except ImportError:
    import urllib.request
    HTTP_LIB = 'urllib'

# â”€â”€ ConfiguraÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DATA_DIR = Path(__file__).parent.parent / 'data'
LOG_PATH = DATA_DIR / 'logs.json'
OUT_PATH = DATA_DIR / 'previsao_sc.json'

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# URL base Open-Meteo (sem API key, CORS-friendly)
OPENMETEO_URL = 'https://api.open-meteo.com/v1/forecast'

# VariÃ¡veis a coletar
DAILY_VARS = [
    'temperature_2m_max',
    'temperature_2m_min',
    'temperature_2m_mean',
    'precipitation_sum',
    'windspeed_10m_max',
]

HOURLY_VARS = []  # nÃ£o usamos horÃ¡rio para simplicidade

# â”€â”€ ClassificaÃ§Ã£o de risco por temperatura â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def classificar_risco(temp: float) -> dict:
    if temp >= 18:
        nivel = 'Baixo'
        cor   = '#10b981'
        desc  = 'Temperatura acima de 18Â°C. Menor risco respiratÃ³rio histÃ³rico.'
    elif temp >= 15:
        nivel = 'Moderado'
        cor   = '#f59e0b'
        desc  = 'Temperatura entre 15Â°C e 18Â°C. Monitoramento preventivo recomendado.'
    elif temp >= 12:
        nivel = 'Alto'
        cor   = '#ef4444'
        desc  = 'Temperatura entre 12Â°C e 15Â°C. Faixa de maior incidÃªncia respiratÃ³ria histÃ³rica.'
    else:
        nivel = 'Muito Alto'
        cor   = '#8b5cf6'
        desc  = f'Temperatura abaixo de 12Â°C. PerÃ­odo crÃ­tico histÃ³rico em SC. PopulaÃ§Ãµes vulnerÃ¡veis requerem atenÃ§Ã£o especial.'
    return {'nivel': nivel, 'cor': cor, 'descricao': desc}


# â”€â”€ Coleta para um municÃ­pio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def coletar_previsao_municipio(ibge: str, nome: str, lat: float, lon: float) -> dict | None:
    params = {
        'latitude':  lat,
        'longitude': lon,
        'daily':     ','.join(DAILY_VARS),
        'timezone':  'America/Sao_Paulo',
        'forecast_days': 7,
    }

    try:
        if HTTP_LIB == 'requests':
            resp = requests.get(OPENMETEO_URL, params=params, timeout=15,
                                headers={'User-Agent': 'RespirAlertSC/2.0'})
            resp.raise_for_status()
            data = resp.json()
        else:
            from urllib.parse import urlencode
            url = f"{OPENMETEO_URL}?{urlencode(params)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'RespirAlertSC/2.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())

        daily = data.get('daily', {})
        datas  = daily.get('time', [])
        t_mean = daily.get('temperature_2m_mean', [])
        t_max  = daily.get('temperature_2m_max', [])
        t_min  = daily.get('temperature_2m_min', [])
        prec   = daily.get('precipitation_sum', [])

        if not datas:
            return None

        dias = []
        for i, dt in enumerate(datas):
            tm = t_mean[i] if i < len(t_mean) and t_mean[i] is not None else 0
            dias.append({
                'data':      dt,
                'temp_media': round(tm, 1),
                'temp_max':   round(t_max[i], 1) if i < len(t_max) and t_max[i] is not None else 0,
                'temp_min':   round(t_min[i], 1) if i < len(t_min) and t_min[i] is not None else 0,
                'precipitacao': round(prec[i], 1) if i < len(prec) and prec[i] is not None else 0,
                'risco':     classificar_risco(tm),
            })

        # Resumo dos 7 dias
        temps_validas = [d['temp_media'] for d in dias if d['temp_media'] != 0]
        temp_media_7d = round(sum(temps_validas)/len(temps_validas), 1) if temps_validas else 0
        risco_predominante = classificar_risco(temp_media_7d)

        # Dia mais frio (maior risco)
        dia_mais_frio = min(dias, key=lambda d: d['temp_min']) if dias else {}

        return {
            'municipio_ibge':     ibge,
            'municipio_nome':     nome,
            'lat':                lat,
            'lon':                lon,
            'coletado_em':        datetime.now().isoformat(),
            'temp_media_7dias':   temp_media_7d,
            'risco_predominante': risco_predominante,
            'dia_mais_frio':      dia_mais_frio,
            'previsao_diaria':    dias,
            'fonte':              'Open-Meteo (api.open-meteo.com)',
        }

    except Exception as exc:
        log.warning(f'Open-Meteo falhou para {nome}: {exc}')
        return None


# â”€â”€ Coleta para todos os municÃ­pios â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def montar_previsao_api(data: dict, ibge: str, nome: str, lat: float, lon: float) -> dict | None:
    daily = data.get('daily', {})
    datas  = daily.get('time', [])
    t_mean = daily.get('temperature_2m_mean', [])
    t_max  = daily.get('temperature_2m_max', [])
    t_min  = daily.get('temperature_2m_min', [])
    prec   = daily.get('precipitation_sum', [])

    if not datas:
        return None

    dias = []
    for i, dt in enumerate(datas):
        tm = t_mean[i] if i < len(t_mean) and t_mean[i] is not None else 0
        dias.append({
            'data':      dt,
            'temp_media': round(tm, 1),
            'temp_max':   round(t_max[i], 1) if i < len(t_max) and t_max[i] is not None else 0,
            'temp_min':   round(t_min[i], 1) if i < len(t_min) and t_min[i] is not None else 0,
            'precipitacao': round(prec[i], 1) if i < len(prec) and prec[i] is not None else 0,
            'risco':     classificar_risco(tm),
        })

    temps_validas = [d['temp_media'] for d in dias if d['temp_media'] != 0]
    temp_media_7d = round(sum(temps_validas)/len(temps_validas), 1) if temps_validas else 0

    return {
        'municipio_ibge':     ibge,
        'municipio_nome':     nome,
        'lat':                lat,
        'lon':                lon,
        'coletado_em':        datetime.now().isoformat(),
        'temp_media_7dias':   temp_media_7d,
        'risco_predominante': classificar_risco(temp_media_7d),
        'dia_mais_frio':      min(dias, key=lambda d: d['temp_min']) if dias else {},
        'previsao_diaria':    dias,
        'fonte':              'Open-Meteo (api.open-meteo.com)',
    }


def coletar_previsao_lote(municipios_lote: list[dict]) -> list[dict | None]:
    params = {
        'latitude':  ','.join(str(m['lat']) for m in municipios_lote),
        'longitude': ','.join(str(m['lon']) for m in municipios_lote),
        'daily':     ','.join(DAILY_VARS),
        'timezone':  'America/Sao_Paulo',
        'forecast_days': 7,
    }

    try:
        if HTTP_LIB == 'requests':
            resp = requests.get(OPENMETEO_URL, params=params, timeout=45,
                                headers={'User-Agent': 'RespirAlertSC/2.0'})
            resp.raise_for_status()
            data = resp.json()
        else:
            from urllib.parse import urlencode
            url = f"{OPENMETEO_URL}?{urlencode(params)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'RespirAlertSC/2.0'})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read())

        respostas = data if isinstance(data, list) else [data]
        saida = []
        for mun, item in zip(municipios_lote, respostas):
            saida.append(montar_previsao_api(item, mun['ibge'], mun['nome'], mun['lat'], mun['lon']))
        return saida
    except Exception as exc:
        nomes = ', '.join(m['nome'] for m in municipios_lote[:3])
        log.warning(f'Open-Meteo falhou para lote iniciado em {nomes}: {exc}')
        return [None] * len(municipios_lote)
def coletar_todos() -> list:
    coords_path = DATA_DIR / 'municipios_coords.json'
    if not coords_path.exists():
        log.error('municipios_coords.json nao encontrado')
        return []

    municipios = json.loads(coords_path.read_text(encoding='utf-8'))
    log.info(f'Coletando previsao para {len(municipios)} municipios em lotes...')

    resultados = []
    falhas = 0
    tamanho_lote = 50

    for inicio in range(0, len(municipios), tamanho_lote):
        lote = municipios[inicio:inicio + tamanho_lote]
        dados_lote = coletar_previsao_lote(lote)
        for resultado in dados_lote:
            if resultado:
                resultados.append(resultado)
            else:
                falhas += 1

    log.info(f'Previsao coletada: {len(resultados)} municipios, {falhas} falhas')
    return resultados

# Salvar resultado
def salvar(dados: list) -> None:
    saida = {
        'gerado_em':    datetime.now().isoformat(),
        'total':        len(dados),
        'municipios':   dados,
    }
    OUT_PATH.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f'previsao_sc.json salvo: {len(dados)} municipios ({OUT_PATH.stat().st_size//1024}KB)')

    entrada = {
        'timestamp': datetime.now().isoformat(),
        'modulo':    'coleta_previsao',
        'sucesso':   True,
        'mensagem':  f'{len(dados)} municipios com previsao de 7 dias',
    }
    hist = []
    if LOG_PATH.exists():
        try: hist = json.loads(LOG_PATH.read_text(encoding='utf-8'))
        except: hist = []
    hist.append(entrada)
    LOG_PATH.write_text(json.dumps(hist[-500:], ensure_ascii=False, indent=2), encoding='utf-8')

# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == '__main__':
    log.info('=== Inicio coleta previsao Open-Meteo ===')

    dados = coletar_todos()
    deve_salvar = True

    if not dados:
        mensagem = 'Open-Meteo indisponivel. Mantendo ultima previsao valida local.'
        log.warning(mensagem)
        registrar_status('Open-Meteo', 'ultimo_valido', mensagem, 0)
        deve_salvar = False
        if OUT_PATH.exists():
            atual = json.loads(OUT_PATH.read_text(encoding='utf-8'))
            dados = atual.get('municipios', [])

    if dados and len(dados) < 295:
        mensagem = f'Previsao incompleta ({len(dados)} municipios). Mantendo ultimo arquivo valido.'
        log.warning(mensagem)
        registrar_status('Open-Meteo', 'ultimo_valido', mensagem, len(dados))
        deve_salvar = False

    if dados and deve_salvar:
        registrar_status('Open-Meteo', 'oficial_atualizado', 'Previsao atualizada a partir da API Open-Meteo.', len(dados))
        salvar(dados)
    elif not dados:
        log.error('Nao foi possivel gerar previsao — nenhum dado disponivel')

    log.info(f'=== Previsao concluida: {len(dados)} municipios ===')
