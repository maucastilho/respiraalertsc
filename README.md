# 🫁 RespirAlert SC

**Plataforma Inteligente de Monitoramento Climático e Hospitalar para Apoio à Prevenção de Doenças Respiratórias em Santa Catarina**

[![GitHub Pages](https://img.shields.io/badge/Deploy-GitHub%20Pages-blue?logo=github)](#publicação-no-github-pages)
[![Atualização Automática](https://img.shields.io/badge/Dados-Atualização%20Mensal-green?logo=github-actions)](/.github/workflows/atualizar-dados.yml)
[![Dados Públicos](https://img.shields.io/badge/Fonte-DATASUS%20%2B%20INMET-orange)](https://datasus.saude.gov.br)
[![Licença Acadêmica](https://img.shields.io/badge/Uso-Acadêmico%20e%20Informativo-lightgrey)](#licença)

---

## Visão Geral

> **295 municípios de Santa Catarina · 1990–2026 · Dados públicos DATASUS + INMET + Open-Meteo**


O RespirAlert SC é uma plataforma web que analisa a relação entre temperatura e internações por doenças respiratórias (CID-10 J00–J99) nos municípios de Santa Catarina, utilizando dados públicos de referência do DATASUS/SIH-SUS, INMET e Open-Meteo.

O sistema coleta, processa e visualiza dados automaticamente, sem depender de banco de dados, backend hospedado ou APIs pagas. É totalmente estático e publicado via GitHub Pages.

### Por que este projeto importa?

> *"Este projeto transforma dados públicos em conhecimento acessível para apoiar estudos acadêmicos, pesquisas e ações preventivas. A plataforma demonstra como a análise de dados pode auxiliar na compreensão de padrões relacionados à saúde pública e às condições climáticas, fortalecendo o uso de evidências na tomada de decisão."*

---

## Funcionalidades

| Módulo | Descrição |
|---|---|
| **Dashboard Executivo** | KPIs estaduais, gráficos de internações mensais, correlação e sazonalidade |
| **Mapa Interativo** | Visualização municipal com camadas de vulnerabilidade e risco |
| **Análise Temporal** | Gráficos interativos com zoom, filtros por município e ano |
| **Ranking Municipal** | Tabela dinâmica com busca, filtros e exportação CSV |
| **Insights Automáticos** | Interpretações geradas por análise estatística |
| **Simulador de Risco** | Estimativa de risco respiratório por temperatura |
| **Painel de Impacto Social** | Calendário sazonal, pressão no SUS, tendências |
| **Comparativo Municipal** | Comparação lado a lado de dois municípios |
| **Metodologia** | Transparência científica completa |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                         │
│  (cron mensal) → Python Scripts → CSV/JSON → Commit/Push   │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    GitHub Pages (CDN)   │
              │   index.html + assets   │
              └────────────┬────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │           Browser (JS)              │
         │  fetch(data/*.json) → Chart.js      │
         │  Análise estatística client-side    │
         └─────────────────────────────────────┘

Fontes de dados (Python):
  DATASUS TabNet  ──┐
  DATASUS DBC/pysus ├──→ internacoes_sc.csv
  Último CSV válido ─┘

  INMET API REST  ──┐
  INMET BDMEP     ├──→ clima_sc.csv
  Último CSV válido ─┘

  processa_dados.py → dataset_final.csv + indicadores_sc.json
```

### Fluxo de Coleta Resiliente

```
ETAPA 1: API oficial (TabNet / INMET REST)
    ↓ (se falhar)
ETAPA 2: Download de arquivos públicos (DBC via pysus / BDMEP)
    ↓ (se falhar)
ETAPA 3: Manter o último dataset local válido, sem sobrescrever coleta incompleta
    ↓
Registrar status da fonte + exibir se está usando dados atualizados ou último dataset válido
```

---

## Tecnologias

**Frontend:**
- HTML5 / CSS3 / JavaScript (ES2022) — sem frameworks
- Chart.js 4 — visualizações interativas
- Google Fonts (Barlow Condensed + Inter + JetBrains Mono)

**Backend/Processamento:**
- Python 3.12
- `requests` — coleta HTTP
- `pandas` — manipulação de dados
- `pysus` — acesso a dados DBC do DATASUS (opcional)
- `statistics` / `math` — cálculos estatísticos (stdlib)

**Infraestrutura:**
- GitHub Pages — hospedagem estática gratuita
- GitHub Actions — CI/CD e atualização automática mensal

**Dados:**
- DATASUS SIH-SUS — internações hospitalares
- INMET — dados meteorológicos
- GeoJSON IBGE — geometrias municipais de SC

---

## Estrutura do Projeto

```
respiralert-sc/
├── .github/
│   └── workflows/
│       └── atualizar-dados.yml    # GitHub Actions — cron mensal
├── data/
│   ├── internacoes_sc.csv         # Internações por município/mês (DATASUS)
│   ├── clima_sc.csv               # Dados climáticos por município/mês (INMET)
│   ├── dataset_final.csv          # Dataset unificado (internações + clima)
│   ├── indicadores_sc.json        # Indicadores estatísticos por município
│   ├── municipios_sc.json         # Mapa: dados resumidos para o frontend
│   ├── estacoes_sc.json           # Estações INMET de SC com coordenadas
│   └── logs.json                  # Log de execuções do pipeline
├── scripts/
│   ├── coleta_datasus.py          # Coleta SIH-SUS (TabNet + pysus + último válido)
│   ├── coleta_inmet.py            # Coleta INMET (API + BDMEP + último válido)
│   ├── processa_dados.py          # Processamento, joins e cálculo de indicadores
│   └── utils.py                   # Funções utilitárias compartilhadas
├── src/
│   └── index.html                 # Aplicação frontend completa (SPA)
└── README.md
```

---

## Instalação e Execução Local

### Pré-requisitos

```bash
python 3.12+
pip
```

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/respiralert-sc.git
cd respiralert-sc
```

### 2. Instalar dependências Python

```bash
pip install requests pandas pysus
```

> **Nota:** `pysus` é opcional. Se não instalado ou se a coleta vier incompleta, o sistema mantém o último dataset local válido e registra o status em `data/status_dados.json`.

### 3. Executar o pipeline de dados

```bash
# Coleta de internações (DATASUS)
cd scripts
python coleta_datasus.py

# Coleta de dados climáticos (INMET)
python coleta_inmet.py

# Processamento e geração de indicadores
python processa_dados.py
```

### 4. Servir o frontend localmente

```bash
# Python built-in server (a partir da raiz do projeto)
python -m http.server 8080

# Acessar em: http://localhost:8080/src/
```

> O `index.html` realiza `fetch('../data/indicadores_sc.json')` — por isso precisa ser servido via HTTP, não aberto diretamente como arquivo.

---

## Publicação no GitHub Pages

### 1. Criar o repositório no GitHub

```bash
git init
git remote add origin https://github.com/seu-usuario/respiralert-sc.git
```

### 2. Configurar GitHub Pages

No repositório GitHub:
- `Settings → Pages → Source → Deploy from branch`
- Branch: `main` / Folder: `/ (root)`

O `index.html` deve estar em `/src/index.html`. Crie um `index.html` na raiz com redirect:

```html
<!DOCTYPE html>
<html><head>
<meta http-equiv="refresh" content="0; url=src/index.html">
</head></html>
```

### 3. Ajustar paths para GitHub Pages

No `src/index.html`, a linha de fetch dos dados:
```javascript
const resp = await fetch('../data/indicadores_sc.json');
```
Já aponta para o caminho correto relativo à estrutura do projeto.

### 4. Push inicial

```bash
git add .
git commit -m "feat: deploy inicial RespirAlert SC"
git push -u origin main
```

---

## GitHub Actions — Atualização Automática

O workflow `.github/workflows/atualizar-dados.yml` é executado automaticamente no **primeiro dia de cada mês às 03:00 UTC**.

### Execução manual

No GitHub: `Actions → RespirAlert SC — Atualização Automática de Dados → Run workflow`

### Segredos necessários (opcionais)

| Secret | Descrição |
|---|---|
| `INMET_TOKEN` | Token da API INMET (rotas públicas funcionam sem token) |

Para configurar: `Settings → Secrets and variables → Actions → New repository secret`

### O que o workflow faz

1. Checkout do repositório
2. Instala Python 3.12 e dependências
3. Executa `coleta_datasus.py` e mantém o último CSV válido se a coleta vier incompleta
4. Executa `coleta_inmet.py` e mantém o último CSV válido se a coleta vier incompleta
5. Executa `processa_dados.py`
6. Verifica integridade dos arquivos gerados
7. Realiza commit automático dos dados atualizados
8. Publica via GitHub Pages

---

## Metodologia

### Fontes de Dados

**DATASUS / SIH-SUS** — dados desde 1990
- Sistema de Informações Hospitalares do SUS
- Filtro: Estado = SC, CID-10 J00–J99, período **1990–2026**
- Agrupamento: município de residência × mês × ano
- Acesso: `tabnet.datasus.gov.br` e arquivos DBC via `pysus`

**INMET**
- 20 estações automáticas em Santa Catarina identificadas
- Variáveis: temperatura média/mínima/máxima, umidade relativa, precipitação
- Acesso: `apitempo.inmet.gov.br`

### Associação Município–Estação

Cada município é associado à estação INMET mais próxima pela fórmula de **Haversine**:

```
d = 2R · arcsin(√[sin²(Δlat/2) + cos(lat₁)·cos(lat₂)·sin²(Δlon/2)])
```

Quando a estação mais próxima não está no próprio município, a distância é reportada.

### Indicadores Estatísticos

| Indicador | Descrição |
|---|---|
| **Correlação de Pearson (r)** | Associação linear entre temperatura e internações mensais |
| **Information Value (IV)** | Poder preditivo da temperatura; bins por quartil de temperatura |
| **Média / Mediana / DP** | Estatísticas descritivas das internações mensais |
| **Tendência temporal** | Regressão linear simples sobre a série histórica |
| **Variação anual (%)** | Variação percentual entre anos consecutivos |

### Classificação de Risco

| Temperatura Média | Risco |
|---|---|
| ≥ 18°C | Baixo |
| 15°C – 18°C | Moderado |
| 12°C – 15°C | Alto |
| < 12°C | Muito Alto |

### Classificação de Vulnerabilidade

Score composto (0–6 pontos):
- Correlação < −0,5: +2 pontos; < −0,3: +1 ponto
- IV > 0,30: +2 pontos; > 0,10: +1 ponto
- Temperatura média < 14°C: +2 pontos; < 18°C: +1 ponto

Resultado: ≥5 = Muito Alta; ≥3 = Alta; ≥1 = Moderada; 0 = Baixa

---

## Limitações

- Dados de internação por município de **residência** (não de ocorrência)
- Municípios sem estação INMET própria usam a mais próxima disponível
- Correlação não implica causalidade
- Dados históricos — não são previsões meteorológicas
- Municípios pequenos podem apresentar maior variância estatística
- A disponibilidade das APIs públicas pode variar; quando a atualização não é completa, o painel mantém o último dataset local válido e mostra esse status

---

## Aviso Metodológico e Jurídico

> Este sistema utiliza dados públicos oficiais para fins **acadêmicos, científicos e informativos**.
> Os resultados representam **associações estatísticas** e não estabelecem causalidade.
> Este sistema **não realiza diagnóstico médico**.
> Este sistema **não substitui** orientação médica, epidemiológica ou decisões governamentais.
> Eventuais inconsistências podem decorrer das limitações das bases públicas utilizadas.

---

## Roadmap Futuro

- [x] GeoJSON municipal completo de SC com renderização no canvas
- [x] Integração com API de previsão meteorológica (Open-Meteo — gratuita)
- [ ] Alertas automáticos via GitHub Issues quando risco aumenta
- [ ] Expansão para outros estados brasileiros
- [ ] Análise de correlação com outros CIDs (cardiovascular, pediátrico)
- [x] Modelo preditivo simples (regressão linear múltipla) no cliente
- [ ] PWA (Progressive Web App) para uso offline
- [ ] Exportação de relatórios em PDF diretamente do browser

---

## Contexto Acadêmico

**Curso:** Sistemas de Informação — UDESC  
**Objetivo:** Demonstração integrada de Sistemas de Informação, Engenharia de Software, Análise de Dados, Ciência de Dados, Estatística, Visualização de Dados, Saúde Pública e Automação.

---

## Licença

Projeto acadêmico de uso livre para fins educacionais, científicos e não-comerciais.  
Dados utilizados são de domínio público (DATASUS e INMET — órgãos públicos federais brasileiros).
