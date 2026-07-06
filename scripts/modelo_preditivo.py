"""
modelo_preditivo.py
===================
Constrói um modelo de regressão linear múltipla por município para
estimar internações futuras combinando:
  - Temperatura média
  - Umidade relativa
  - Sazonalidade (mês como variável cíclica via seno/cosseno)
  - Tendência temporal (meses desde o início da série)

Gera: data/modelo_preditivo.json

Projeção: 12 meses à frente (com previsão climática Open-Meteo quando disponível,
ou extrapolação de sazonalidade histórica quando não disponível).

Uso:
    python modelo_preditivo.py
"""

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'


# ================================================================
# Regressão Linear Múltipla (implementada sem numpy/sklearn)
# ================================================================

def transpor(matriz):
    return [[matriz[j][i] for j in range(len(matriz))] for i in range(len(matriz[0]))]


def multiplicar_matrizes(A, B):
    linhas_A, cols_A = len(A), len(A[0])
    linhas_B, cols_B = len(B), len(B[0])
    C = [[0.0]*cols_B for _ in range(linhas_A)]
    for i in range(linhas_A):
        for j in range(cols_B):
            for k in range(cols_A):
                C[i][j] += A[i][k] * B[k][j]
    return C


def inverter_matriz(M):
    """Inversão por eliminação de Gauss-Jordan (para matrizes pequenas ≤ 6x6)."""
    n = len(M)
    aug = [M[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        # Pivô
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        piv = aug[col][col]
        if abs(piv) < 1e-12:
            return None  # singular
        aug[col] = [x / piv for x in aug[col]]
        for row in range(n):
            if row != col:
                f = aug[row][col]
                aug[row] = [aug[row][k] - f * aug[col][k] for k in range(2*n)]
    return [aug[i][n:] for i in range(n)]


def regressao_linear_multipla(X, y):
    """
    Calcula coeficientes β = (Xᵀ X)⁻¹ Xᵀ y via mínimos quadrados.
    X: matriz n×p (inclui coluna de 1s para intercepto)
    y: vetor n×1
    Retorna: coeficientes β (lista de p valores) ou None se singular.
    """
    n, p = len(X), len(X[0])
    if n < p + 2:
        return None

    Xt  = transpor(X)
    XtX = multiplicar_matrizes(Xt, X)
    Xty = multiplicar_matrizes(Xt, [[yi] for yi in y])
    inv = inverter_matriz(XtX)
    if inv is None:
        return None
    beta_mat = multiplicar_matrizes(inv, Xty)
    return [b[0] for b in beta_mat]


def r_quadrado(y_real, y_pred):
    media = statistics.mean(y_real)
    ss_tot = sum((y - media)**2 for y in y_real)
    ss_res = sum((y - yp)**2 for y, yp in zip(y_real, y_pred))
    return round(1 - ss_res/ss_tot, 4) if ss_tot > 0 else 0.0


# ================================================================
# Feature engineering
# ================================================================

def features_linha(temp, umidade, mes, indice_tempo):
    """
    Retorna vetor de features para uma observação.
    Features: [1, temp, umidade, sen(mês), cos(mês), tendência]
    As features cíclicas de mês capturam sazonalidade sem tratar
    o mês como variável linear (jan ≠ 12 em distância de dez).
    """
    rad = 2 * math.pi * (mes - 1) / 12
    return [
        1.0,                    # intercepto
        float(temp),            # temperatura média
        float(umidade),         # umidade relativa
        math.sin(rad),          # sazonalidade cíclica (seno)
        math.cos(rad),          # sazonalidade cíclica (cosseno)
        float(indice_tempo),    # tendência temporal linear
    ]


# ================================================================
# Leitura do dataset
# ================================================================

def ler_dataset():
    path = DATA_DIR / 'dataset_final.csv'
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ================================================================
# Treinar modelo por município
# ================================================================

def treinar_municipio(registros: list[dict]) -> dict | None:
    """
    Treina o modelo de regressão múltipla para um município.
    Retorna dicionário com coeficientes, R², métricas e projeção.
    """
    # Ordenar por ano/mês para índice temporal correto
    registros_ord = sorted(registros, key=lambda r: (int(r['ano']), int(r['mes'])))
    n = len(registros_ord)
    if n < 12:
        return None

    X, y = [], []
    for i, r in enumerate(registros_ord):
        try:
            temp  = float(r['temp_media'])
            umid  = float(r.get('umidade', 75))
            mes   = int(r['mes'])
            intern= int(r['internacoes'])
            if temp == 0:
                continue
            X.append(features_linha(temp, umid, mes, i))
            y.append(float(intern))
        except (ValueError, KeyError):
            continue

    if len(X) < 12:
        return None

    beta = regressao_linear_multipla(X, y)
    if beta is None:
        return None

    # Predições in-sample para R²
    y_pred = [sum(b*x for b, x in zip(beta, xi)) for xi in X]
    r2 = r_quadrado(y, y_pred)

    # Erro médio absoluto (MAE)
    mae = round(statistics.mean(abs(yp - yr) for yp, yr in zip(y_pred, y)), 2)

    # ── Projeção dos próximos 12 meses ──────────────────────────────
    # Extrapolação de sazonalidade: temperatura média de cada mês histórico
    temp_por_mes = defaultdict(list)
    umid_por_mes = defaultdict(list)
    for r in registros_ord:
        try:
            temp_por_mes[int(r['mes'])].append(float(r['temp_media']))
            umid_por_mes[int(r['mes'])].append(float(r.get('umidade', 75)))
        except (ValueError, KeyError):
            pass

    hoje = date.today()
    projecao = []
    for k in range(1, 13):
        # Mês futuro
        mes_fut = (hoje.month + k - 1) % 12 + 1
        ano_fut = hoje.year + (hoje.month + k - 1) // 12
        temp_fut = statistics.mean(temp_por_mes[mes_fut]) if temp_por_mes[mes_fut] else 18.0
        umid_fut = statistics.mean(umid_por_mes[mes_fut]) if umid_por_mes[mes_fut] else 75.0

        idx_fut = n + k  # índice temporal futuro
        x_fut = features_linha(temp_fut, umid_fut, mes_fut, idx_fut)
        intern_proj = max(0, round(sum(b*x for b, x in zip(beta, x_fut))))

        projecao.append({
            'mes':         mes_fut,
            'ano':         ano_fut,
            'label':       f"{['','Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][mes_fut]}/{str(ano_fut)[2:]}",
            'temp_prevista': round(temp_fut, 1),
            'internacoes_estimadas': intern_proj,
            'intervalo_inferior': max(0, round(intern_proj - mae)),
            'intervalo_superior': round(intern_proj + mae),
        })

    # Tendência da projeção
    projs = [p['internacoes_estimadas'] for p in projecao]
    tend_proj = 'crescente' if projs[-1] > projs[0]*1.05 else ('decrescente' if projs[-1] < projs[0]*0.95 else 'estável')

    return {
        'n_observacoes':    n,
        'r_quadrado':       r2,
        'mae':              mae,
        'coeficientes': {
            'intercepto':   round(beta[0], 4),
            'temperatura':  round(beta[1], 4),
            'umidade':      round(beta[2], 4),
            'sazon_seno':   round(beta[3], 4),
            'sazon_cosseno':round(beta[4], 4),
            'tendencia':    round(beta[5], 4),
        },
        'interpretacao': _interpretar_coeficientes(beta, r2),
        'projecao_12meses': projecao,
        'tendencia_projecao': tend_proj,
        'pico_projetado': max(projecao, key=lambda p: p['internacoes_estimadas']),
        'vale_projetado': min(projecao, key=lambda p: p['internacoes_estimadas']),
    }


def _interpretar_coeficientes(beta, r2):
    """Gera texto interpretativo dos coeficientes para o frontend."""
    linhas = []
    if beta[1] < -0.5:
        linhas.append(f"Cada 1°C de redução na temperatura está associado a um aumento médio de {abs(round(beta[1],1))} internações.")
    elif beta[1] > 0.5:
        linhas.append(f"A temperatura apresenta associação positiva com as internações (β={round(beta[1],2)}).")
    if beta[2] > 0.3:
        linhas.append(f"A umidade relativa contribui positivamente para o modelo (β={round(beta[2],2)}).")
    if r2 >= 0.7:
        linhas.append(f"O modelo explica {round(r2*100,1)}% da variação das internações — ajuste considerado bom.")
    elif r2 >= 0.4:
        linhas.append(f"O modelo explica {round(r2*100,1)}% da variação — ajuste moderado. Outros fatores também influenciam.")
    else:
        linhas.append(f"R²={r2} — variação das internações influenciada por múltiplos fatores além do clima.")
    return linhas


# ================================================================
# Entry point
# ================================================================

def main():
    print('=== modelo_preditivo.py ===')
    print('Lendo dataset...')
    dataset = ler_dataset()
    print(f'  {len(dataset)} registros carregados')

    # Agrupar por município
    por_mun = defaultdict(list)
    for r in dataset:
        por_mun[r['municipio_ibge']].append(r)

    print(f'  {len(por_mun)} municípios encontrados')
    print('Treinando modelos...')

    modelos = {}
    sucessos = falhas = 0
    for ibge, registros in por_mun.items():
        nome = registros[0]['municipio_nome']
        modelo = treinar_municipio(registros)
        if modelo:
            modelos[ibge] = {'municipio_ibge': ibge, 'municipio_nome': nome, **modelo}
            sucessos += 1
        else:
            falhas += 1

    print(f'  Modelos treinados: {sucessos} | Falhas: {falhas}')

    # Estatísticas gerais
    r2_vals = [m['r_quadrado'] for m in modelos.values()]
    r2_medio = round(statistics.mean(r2_vals), 4) if r2_vals else 0

    saida = {
        'gerado_em':      datetime.now().isoformat(),
        'total_municipios': len(modelos),
        'r2_medio':       r2_medio,
        'descricao':      'Regressão linear múltipla: variáveis temperatura, umidade, sazonalidade (sen/cos) e tendência temporal.',
        'nota_metodologica': (
            'As estimativas representam projeções estatísticas baseadas em padrões históricos. '
            'Não constituem previsão epidemiológica. Os intervalos de confiança aproximados '
            'são baseados no MAE (Mean Absolute Error) do modelo in-sample.'
        ),
        'modelos': list(modelos.values()),
    }

    out = DATA_DIR / 'modelo_preditivo.json'
    out.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'modelo_preditivo.json salvo: {len(modelos)} municípios, R² médio={r2_medio} ({out.stat().st_size//1024}KB)')

    # Log
    log_path = DATA_DIR / 'logs.json'
    entrada = {'timestamp': datetime.now().isoformat(), 'modulo': 'modelo_preditivo',
               'sucesso': True, 'mensagem': f'{len(modelos)} modelos treinados, R²={r2_medio}'}
    hist = []
    if log_path.exists():
        try: hist = json.loads(log_path.read_text(encoding='utf-8'))
        except: hist = []
    hist.append(entrada)
    log_path.write_text(json.dumps(hist[-500:], ensure_ascii=False, indent=2), encoding='utf-8')
    print('=== Concluído ===')


if __name__ == '__main__':
    main()
