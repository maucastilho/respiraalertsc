/**
 * app.js — RespirAlert SC
 * Módulo principal: estado global, navegação, carregamento de dados,
 * filtros reativos, exportação PDF por gráfico.
 * Depende de: components/graficos.js, components/dashboard.js,
 *             components/mapa.js, components/simulador.js,
 *             components/ranking.js, components/insights.js
 */

// ================================================================
// ESTADO GLOBAL
// ================================================================
let DADOS = null;
let MUNICIPIOS = [];
window.DADOS_GLOBAIS = null;

// Filtros ativos
const FILTROS = {
  municipio: 'TODOS',
  ano: 'TODOS',
  temp_min: -5,
  temp_max: 35,
};

let chartInstances = {};
let rankingOrdem = { campo: 'total_internacoes', asc: false };

// ================================================================
// CARREGAMENTO DE DADOS
// ================================================================
async function carregarDados() {
  try {
    const resp = await fetch('../data/indicadores_sc.json');
    if (!resp.ok) throw new Error('JSON não encontrado');
    DADOS = await resp.json();
  } catch (e) {
    exibirErroDados(e);
    return;
  }
  MUNICIPIOS = DADOS.municipios || [];
  window.DADOS_GLOBAIS = DADOS;
  await Promise.all([carregarPrevisao(), carregarModelo()]);
  inicializarApp();
}

// ================================================================
// INICIALIZAÇÃO
// ================================================================
function inicializarApp() {
  // KPIs
  _set('kpi-municipios',  DADOS.total_municipios);
  _set('kpi-internacoes', Number(DADOS.total_internacoes).toLocaleString('pt-BR'));
  _set('kpi-temp',        DADOS.temp_media_estadual + '°C');
  _set('kpi-correlacao',  DADOS.correlacao_media_estadual);
  _set('kpi-maior',       DADOS.municipio_maior_incidencia);
  _set('kpi-menor',       DADOS.municipio_menor_incidencia);
  const statusFontes = DADOS.status_fontes?.fontes || {};
  const usandoUltimoValido = Object.values(statusFontes).some(f => f?.status === 'ultimo_valido');
  const statusTexto = usandoUltimoValido ? 'Último dataset válido' : 'Dados oficiais atualizados';
  _set('last-update-topbar', `✓ ${statusTexto}: ${DADOS.ultima_atualizacao}`);
  const corrEl = document.getElementById('kpi-correlacao');
  if (corrEl) corrEl.style.color = 'var(--cyan)';

  // Popular selects de municípios
  const opts = MUNICIPIOS.map(m =>
    `<option value="${m.municipio_ibge}">${m.municipio_nome}</option>`
  ).join('');
  ['filter-municipio','filter-municipio-insights'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML += opts;
  });
  ['comp-mun1','comp-mun2'].forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) { el.innerHTML = opts; el.selectedIndex = i === 1 ? 1 : 0; }
  });

  // Inicializar filtro de faixa de temperatura
  _initFaixaTemp();

  renderDashboard();
  renderRanking();
  renderInsights();
  renderImpacto();
  renderTabelaMapa();
  renderSimuladorHistograma();
  atualizarSimulador(18);
  atualizarComparativo();
  inicializarMapaCanvas();
}

function _set(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function exibirErroDados(erro) {
  _set('last-update-topbar', 'Erro ao carregar dados');
  _set('kpi-municipios', 'Erro');
  const detalhe = document.querySelector('#view-dashboard .page-subtitle');
  if (detalhe) {
    detalhe.textContent = 'Não foi possível carregar data/indicadores_sc.json. Abra o projeto via servidor HTTP para usar os dados reais.';
  }
  console.error('Falha ao carregar dados oficiais:', erro);
}

// ================================================================
// FILTROS REATIVOS
// ================================================================
function _initFaixaTemp() {
  // Criar slider duplo de temperatura nos filtros da análise temporal
  const row = document.getElementById('filtros-temporal');
  if (!row) return;

  // Inputs numéricos de temperatura mínima e máxima
  const minInput = document.getElementById('filter-temp-min');
  const maxInput = document.getElementById('filter-temp-max');
  if (minInput) {
    minInput.value = FILTROS.temp_min;
    minInput.addEventListener('change', e => {
      FILTROS.temp_min = parseFloat(e.target.value);
      aplicarFiltros();
    });
  }
  if (maxInput) {
    maxInput.value = FILTROS.temp_max;
    maxInput.addEventListener('change', e => {
      FILTROS.temp_max = parseFloat(e.target.value);
      aplicarFiltros();
    });
  }
}

function aplicarFiltros() {
  // Sincronizar estado
  FILTROS.municipio = document.getElementById('filter-municipio')?.value || 'TODOS';
  FILTROS.ano       = document.getElementById('filter-ano')?.value      || 'TODOS';
  FILTROS.temp_min  = parseFloat(document.getElementById('filter-temp-min')?.value ?? -5);
  FILTROS.temp_max  = parseFloat(document.getElementById('filter-temp-max')?.value ?? 35);

  // Atualizar label de temp
  const lbl = document.getElementById('filter-temp-label');
  if (lbl) lbl.textContent = `${FILTROS.temp_min}°C – ${FILTROS.temp_max}°C`;

  // Recalcular todos os gráficos que dependem dos filtros
  atualizarTemporal();
  renderInsights();
}

// Dados filtrados por município, ano e faixa de temperatura
function dadosFiltrados(municipios) {
  return municipios.filter(m => {
    if (FILTROS.municipio !== 'TODOS' && m.municipio_ibge !== FILTROS.municipio) return false;
    if (m.temp_media < FILTROS.temp_min || m.temp_media > FILTROS.temp_max) return false;
    return true;
  });
}

function anosDisponiveis(municipios = MUNICIPIOS) {
  const anos = new Set();
  municipios.forEach(m => {
    Object.keys(m.variacao_anual || {}).forEach(ano => {
      if (/^\d{4}$/.test(ano)) anos.add(Number(ano));
    });
    Object.keys(m.serie_anual || {}).forEach(ano => {
      if (/^\d{4}$/.test(ano)) anos.add(Number(ano));
    });
  });
  return [...anos].sort((a, b) => a - b);
}

function estimarTotalAno(m, ano) {
  const anual = m.serie_anual?.[ano];
  if (anual) return Object.values(anual).reduce((a, b) => a + b, 0);

  const variacao = m.variacao_anual || {};
  const anosSerie = Math.max(1, Object.keys(variacao).length + 1);
  const baseAnual = Number(m.total_internacoes || 0) / anosSerie;
  const vari = variacao[String(ano)];
  return vari !== undefined ? baseAnual * (1 + Number(vari) / 100) : baseAnual;
}

// Série mensal filtrada (respeita ano e faixa de temperatura)
function serieFiltradasMes(m) {
  const meses = [1,2,3,4,5,6,7,8,9,10,11,12];

  if (FILTROS.ano === 'TODOS') {
    // Média dos anos disponíveis
    return meses.map(mes => {
      const saz = m.sazonalidade_mensal || {};
      return parseFloat(saz[mes] || saz[String(mes)] || 0);
    });
  }

  // Ano específico via serie_anual
  const anual = m.serie_anual?.[parseInt(FILTROS.ano)];
  if (anual) return meses.map(mes => anual[mes] || 0);

  const vari = m.variacao_anual?.[FILTROS.ano];
  const fator = vari !== undefined ? 1 + Number(vari) / 100 : 1.0;
  return meses.map(mes => {
    const saz = m.sazonalidade_mensal || {};
    return Math.round((parseFloat(saz[mes] || 0)) * fator);
  });
}

// ================================================================
// DASHBOARD
// ================================================================
function renderDashboard() {
  const mesesLabels = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const sazonTempEstado = [21.0,21.2,20.4,18.5,16.0,13.5,12.8,13.2,15.0,17.5,19.5,20.8];

  // Agregar internações mensais de todos os municípios
  const internacoesMes = Array(12).fill(0);
  MUNICIPIOS.forEach(m => {
    const saz = m.sazonalidade_mensal || {};
    for (let i = 1; i <= 12; i++) internacoesMes[i-1] += parseFloat(saz[i] || saz[String(i)] || 0);
  });

  renderChart('chart-internacoes-mensal', {
    type: 'bar',
    data: {
      labels: mesesLabels,
      datasets: [{
        label: 'Internações (SC)',
        data: internacoesMes,
        backgroundColor: internacoesMes.map((_, i) => i >= 5 && i <= 7 ? 'rgba(239,68,68,0.75)' : 'rgba(0,194,255,0.5)'),
        borderRadius: 4,
      }]
    },
    options: chartOpts()
  });

  // Scatter correlação
  const scatter = MUNICIPIOS.map(m => ({ x: m.temp_media, y: m.total_internacoes, nome: m.municipio_nome }));
  renderChart('chart-correlacao', {
    type: 'scatter',
    data: { datasets: [{ label: 'Município', data: scatter.map(d => ({x:d.x,y:d.y})), backgroundColor:'rgba(0,194,255,0.65)', pointRadius:6, pointHoverRadius:9 }] },
    options: {
      ...chartOpts({ xLabel: 'Temperatura Média (°C)', yLabel: 'Total Internações' }),
      plugins: { legend:{display:false}, tooltip:{...chartOpts().plugins.tooltip, callbacks:{label:ctx=>{const d=scatter[ctx.dataIndex]; return d?`${d.nome}: ${d.x}°C / ${Number(d.y).toLocaleString('pt-BR')} intern.`:'';}}} }
    }
  });

  // Sazonalidade dual
  renderChart('chart-sazonalidade', {
    type: 'line',
    data: {
      labels: mesesLabels,
      datasets: [
        { label: 'Internações (índice)', data: internacoesMes.map(v=>(v/Math.max(...internacoesMes)*100).toFixed(1)), borderColor:'#ef4444', backgroundColor:'rgba(239,68,68,0.1)', tension:0.4, fill:true, yAxisID:'y' },
        { label: 'Temperatura (°C)', data: sazonTempEstado, borderColor:'#f59e0b', backgroundColor:'transparent', tension:0.4, borderDash:[5,3], yAxisID:'y2' },
      ]
    },
    options: { ...chartOpts({dual:true}), plugins:{legend:{display:true, labels:{color:'#8bacc8',font:{size:11}}}, tooltip:{...chartOpts().plugins.tooltip}} }
  });

  // Doughnut risco
  const riscos = {Baixo:0,Moderado:0,Alto:0,'Muito Alto':0};
  MUNICIPIOS.forEach(m => { riscos[m.classificacao_risco]=(riscos[m.classificacao_risco]||0)+1; });
  renderChart('chart-risco', {
    type: 'doughnut',
    data: { labels:Object.keys(riscos), datasets:[{data:Object.values(riscos), backgroundColor:['rgba(16,185,129,0.8)','rgba(245,158,11,0.8)','rgba(239,68,68,0.8)','rgba(139,92,246,0.8)'], borderColor:'rgba(0,0,0,0.3)', borderWidth:1}] },
    options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'right', labels:{color:'#8bacc8',font:{size:11},padding:8}}} }
  });
}

// ================================================================
// ANÁLISE TEMPORAL (com filtros completos)
// ================================================================
function atualizarTemporal() {
  const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

  const munFiltrados = dadosFiltrados(MUNICIPIOS);
  const label = document.getElementById('stats-municipio-label');
  if (label) label.textContent = FILTROS.municipio === 'TODOS' ? `SC (${munFiltrados.length} mun.)` : (munFiltrados[0]?.municipio_nome || 'SC');

  // Agregar internações mensais dos municípios filtrados
  const internacoesMes = Array(12).fill(0);
  munFiltrados.forEach(m => {
    const serie = serieFiltradasMes(m);
    serie.forEach((v, i) => internacoesMes[i] += v);
  });

  // Temperatura média do grupo filtrado por mês
  const sazonT = [1.0,1.0,0.8,0.5,-0.2,-0.8,-1.0,-0.9,-0.4,0.2,0.7,0.9];
  let tempBase = munFiltrados.length
    ? munFiltrados.reduce((s,m)=>s+m.temp_media,0)/munFiltrados.length
    : 18;
  const tempMes = sazonT.map(d => parseFloat((tempBase + d*4.5).toFixed(1)));

  // Gráfico principal dual
  renderChart('chart-temporal-main', {
    type: 'line',
    data: {
      labels: meses,
      datasets: [
        { label:'Internações', data:internacoesMes, borderColor:'#ef4444', backgroundColor:'rgba(239,68,68,0.08)', tension:0.4, fill:true, yAxisID:'y' },
        { label:'Temperatura (°C)', data:tempMes, borderColor:'#f59e0b', backgroundColor:'transparent', tension:0.4, borderDash:[5,3], yAxisID:'y2' },
      ]
    },
    options: { ...chartOpts({dual:true}), plugins:{legend:{display:true,labels:{color:'#8bacc8',font:{size:11}}}, tooltip:{...chartOpts().plugins.tooltip}} }
  });

  // Distribuição mensal (barras com cor por faixa de temperatura)
  renderChart('chart-boxplot-mes', {
    type: 'bar',
    data: {
      labels: meses,
      datasets: [{
        label: 'Internações médias',
        data: internacoesMes.map(v => munFiltrados.length ? +(v/munFiltrados.length).toFixed(1) : v),
        backgroundColor: tempMes.map(t => {
          if (t < 12)  return 'rgba(139,92,246,0.75)';
          if (t < 15)  return 'rgba(239,68,68,0.75)';
          if (t < 18)  return 'rgba(245,158,11,0.70)';
          return 'rgba(16,185,129,0.60)';
        }),
        borderRadius: 4,
      }]
    },
    options: {
      ...chartOpts({yLabel:'Média Internações'}),
      plugins: { ...chartOpts().plugins,
        legend: { display: true, labels: { color:'#8bacc8', font:{size:10},
          generateLabels: () => [
            {text:'< 12°C (Muito Alto)', fillStyle:'rgba(139,92,246,0.75)', strokeStyle:'transparent', lineWidth:0},
            {text:'12–15°C (Alto)',       fillStyle:'rgba(239,68,68,0.75)',   strokeStyle:'transparent', lineWidth:0},
            {text:'15–18°C (Moderado)',   fillStyle:'rgba(245,158,11,0.70)',  strokeStyle:'transparent', lineWidth:0},
            {text:'> 18°C (Baixo)',       fillStyle:'rgba(16,185,129,0.60)',  strokeStyle:'transparent', lineWidth:0},
          ]
        }}
      }
    }
  });

  // Variação anual
  const anos = anosDisponiveis(munFiltrados);
  const totais = anos.map(ano => {
    return munFiltrados.reduce((s, m) => s + estimarTotalAno(m, ano), 0);
  });
  renderChart('chart-variacao-anual', {
    type: 'bar',
    data: {
      labels: anos.map(String),
      datasets: [{
        label:'Internações',
        data: totais.map(Math.round),
        backgroundColor: 'rgba(0,194,255,0.6)',
        borderRadius: 4,
      }]
    },
    options: chartOpts({yLabel:'Total Internações'})
  });

  // Estatísticas do grupo filtrado
  renderStatsGrid(munFiltrados);
}

function renderStatsGrid(municipios) {
  if (!municipios.length) return;
  const totalInt = municipios.reduce((s,m)=>s+m.total_internacoes,0);
  const tempMedia = municipios.reduce((s,m)=>s+m.temp_media,0)/municipios.length;
  const corrMedia = municipios.reduce((s,m)=>s+m.correlacao_pearson,0)/municipios.length;
  const ivMedia   = municipios.reduce((s,m)=>s+m.information_value,0)/municipios.length;
  const mediaInt  = municipios.reduce((s,m)=>s+m.int_media_mensal,0)/municipios.length;
  const dpMedio   = municipios.reduce((s,m)=>s+m.int_desvio_padrao,0)/municipios.length;

  const stats = [
    {label:'Municípios na seleção', val:municipios.length,                        cor:'var(--cyan)'},
    {label:'Total Internações',      val:Number(totalInt).toLocaleString('pt-BR'), cor:'var(--text-primary)'},
    {label:'Média Mensal / Mun.',    val:Math.round(mediaInt)+' intern.',          cor:'var(--text-primary)'},
    {label:'Desvio Padrão Médio',    val:Math.round(dpMedio)+' intern.',           cor:'var(--text-muted)'},
    {label:'Temp. Média do Grupo',   val:tempMedia.toFixed(1)+'°C',               cor:'var(--amber)'},
    {label:'Correlação Média',       val:corrMedia.toFixed(4),                     cor:corrMedia<-0.5?'var(--red)':'var(--cyan)'},
    {label:'IV Médio',               val:ivMedia.toFixed(2),                       cor:'var(--purple)'},
    {label:'Faixa de Temperatura',   val:`${FILTROS.temp_min}°C – ${FILTROS.temp_max}°C`, cor:'var(--amber)'},
  ];

  document.getElementById('stats-grid').innerHTML = stats.map(s => `
    <div class="gauge-card">
      <div style="font-family:var(--font-display);font-size:22px;font-weight:700;color:${s.cor};margin-bottom:4px;line-height:1">${s.val}</div>
      <div class="gauge-label">${s.label}</div>
    </div>
  `).join('');
}

// ================================================================
// RANKING
// ================================================================
function renderRanking() {
  if (window.Ranking) {
    Ranking.inicializar(MUNICIPIOS, (ibge) => abrirPaginaMunicipio(ibge));
  } else {
    // Fallback inline
    renderTbodyRanking([...MUNICIPIOS].sort((a,b)=>b.total_internacoes-a.total_internacoes));
  }
}

function filtrarRanking() {
  if (window.Ranking) { Ranking.renderizar(); return; }
  const search = document.getElementById('search-ranking')?.value.toLowerCase();
  const risco  = document.getElementById('filter-risco-ranking')?.value;
  const vulner = document.getElementById('filter-vulner-ranking')?.value;
  let dados = [...MUNICIPIOS];
  if (search) dados = dados.filter(m => m.municipio_nome.toLowerCase().includes(search));
  if (risco !== 'TODOS') dados = dados.filter(m => m.classificacao_risco === risco);
  if (vulner !== 'TODOS') dados = dados.filter(m => m.vulnerabilidade === vulner);
  dados.sort((a,b) => rankingOrdem.asc ? (a[rankingOrdem.campo]>b[rankingOrdem.campo]?1:-1) : (a[rankingOrdem.campo]<b[rankingOrdem.campo]?1:-1));
  renderTbodyRanking(dados);
}

function ordenarRanking(campo) {
  if (window.Ranking) { Ranking.ordenarPor(campo); return; }
  if (rankingOrdem.campo===campo) rankingOrdem.asc=!rankingOrdem.asc;
  else { rankingOrdem.campo=campo; rankingOrdem.asc=false; }
  filtrarRanking();
}

function renderTbodyRanking(dados) {
  const tbody = document.getElementById('tbody-ranking');
  if (!tbody) return;
  tbody.innerHTML = dados.map((m,idx) => `
    <tr onclick="abrirPaginaMunicipio('${m.municipio_ibge}')" style="cursor:pointer">
      <td style="color:var(--text-muted);font-family:var(--font-mono)">${String(idx+1).padStart(2,'0')}</td>
      <td style="font-weight:500;color:var(--text-primary)">${m.municipio_nome}</td>
      <td style="font-family:var(--font-mono)">${Number(m.total_internacoes).toLocaleString('pt-BR')}</td>
      <td style="font-family:var(--font-mono)">${m.temp_media?.toFixed(1)}°C</td>
      <td style="font-family:var(--font-mono);color:${m.correlacao_pearson<-0.5?'var(--red)':'var(--cyan)'}">${m.correlacao_pearson}</td>
      <td style="font-family:var(--font-mono)">${m.information_value?.toFixed(2)} <span style="font-size:10px;color:var(--text-muted)">${m.iv_classificacao}</span></td>
      <td>${badgeRisco(m.classificacao_risco)}</td>
      <td>${badgeVulner(m.vulnerabilidade)}</td>
      <td style="font-size:12px;color:var(--text-muted)">${m.estacao_inmet}${m.distancia_estacao_km>0?` (${m.distancia_estacao_km}km)`:''}</td>
    </tr>`).join('');
  const c=document.getElementById('ranking-count');
  if(c) c.textContent=`Exibindo ${dados.length} de ${MUNICIPIOS.length} municípios`;
}

function exportarRankingCSV() {
  if (window.Ranking) { Ranking.exportarCSV(); return; }
  const linhas = [['Município','IBGE','Internações','Temp. Média','Correlação','IV','Risco','Vulnerabilidade','Estação']];
  MUNICIPIOS.forEach(m => linhas.push([m.municipio_nome,m.municipio_ibge,m.total_internacoes,m.temp_media,m.correlacao_pearson,m.information_value,m.classificacao_risco,m.vulnerabilidade,m.estacao_inmet]));
  const csv = linhas.map(l=>l.join(';')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}));
  a.download='respiralert_ranking.csv'; a.click();
}

// ================================================================
// INSIGHTS (reativo aos filtros)
// ================================================================
function renderInsights() {
  const ibge = document.getElementById('filter-municipio-insights')?.value || 'TODOS';
  const munFiltrados = dadosFiltrados(MUNICIPIOS);

  if (window.Insights) {
    Insights.renderizar(munFiltrados.map(m => ({...m, ibge: m.municipio_ibge, nome: m.municipio_nome})), ibge);
    return;
  }

  const icons = ['📉','❄️','📅','🔬','📊','📈','🌡️','⚠️'];
  let lista = munFiltrados;
  if (ibge !== 'TODOS') lista = lista.filter(m => m.municipio_ibge === ibge);
  const allInsights = [];
  lista.forEach(m => (m.insights||[]).forEach(txt => allInsights.push({mun:m.municipio_nome,txt})));
  const container = document.getElementById('insights-container');
  if (!container) return;
  container.innerHTML = allInsights.map((ins,i) => `
    <div class="insight-item">
      <div class="insight-icon">${icons[i%icons.length]}</div>
      <div>
        <div style="font-size:11px;font-weight:600;color:var(--cyan);margin-bottom:4px">${ins.mun.toUpperCase()}</div>
        <div class="insight-text">${ins.txt}</div>
      </div>
    </div>`).join('');
}

// ================================================================
// SIMULADOR
// ================================================================
function atualizarSimulador(temp) {
  if (window.Simulador) { Simulador.atualizar(temp); return; }
  temp = parseFloat(temp);
  document.getElementById('sim-temp-display').textContent = temp.toFixed(1)+'°C';
  document.getElementById('sim-slider').value = temp;
  let nivel,desc,bg,border,color;
  if (temp>=18)      {nivel='BAIXO';     desc='Temperaturas acima de 18°C associadas a menor incidência respiratória'; bg='var(--green-dim)'; border='rgba(16,185,129,0.3)'; color='var(--green)';}
  else if (temp>=15) {nivel='MODERADO';  desc='Faixa de transição — monitoramento preventivo recomendado'; bg='var(--amber-dim)'; border='rgba(245,158,11,0.3)'; color='var(--amber)';}
  else if (temp>=12) {nivel='ALTO';      desc='Temperaturas nesta faixa historicamente associadas a maior incidência'; bg='var(--red-dim)'; border='rgba(239,68,68,0.3)'; color='var(--red)';}
  else               {nivel='MUITO ALTO';desc='Abaixo de 12°C: período crítico histórico para internações respiratórias'; bg='rgba(139,92,246,0.1)'; border='rgba(139,92,246,0.3)'; color='var(--purple)';}
  const box=document.getElementById('sim-risco-box');
  box.style.background=bg; box.style.borderColor=border;
  document.getElementById('sim-risco-nivel').style.color=color;
  document.getElementById('sim-risco-nivel').textContent=nivel;
  document.getElementById('sim-risco-desc').textContent=desc;
  document.getElementById('sim-temp-display').style.color=color;
}

function renderSimuladorHistograma() {
  if (window.Simulador) { Simulador.renderHistograma(); return; }
  const labels=['≤5','5–8','8–11','11–14','14–17','17–20','20–23','23–26','26–29','≥29'];
  const internacoes=[95,88,82,74,58,38,25,18,14,12];
  const cores=['rgba(139,92,246,0.85)','rgba(139,92,246,0.75)','rgba(239,68,68,0.80)','rgba(239,68,68,0.70)','rgba(245,158,11,0.80)','rgba(245,158,11,0.65)','rgba(16,185,129,0.65)','rgba(16,185,129,0.75)','rgba(16,185,129,0.85)','rgba(16,185,129,0.90)'];
  renderChart('chart-sim-hist',{type:'bar',data:{labels,datasets:[{label:'Índice de Internações',data:internacoes,backgroundColor:cores,borderRadius:4}]},options:chartOpts({xLabel:'Faixa de Temperatura (°C)',yLabel:'Índice (base 100)'})});
}

// ================================================================
// IMPACTO SOCIAL
// ================================================================
function renderImpacto() {
  // Alerta preventivo
  const inverno=[6,7,8];
  const mesAtual=new Date().getMonth()+1;
  const alertEl=document.getElementById('impacto-alerta');
  const alertText=document.getElementById('impacto-alerta-texto');
  const mNome=['','Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][mesAtual];
  if (inverno.includes(mesAtual)){
    alertEl.className='alerta-box';
    alertText.innerHTML=`<strong>⚠️ Período de Maior Risco Identificado.</strong><br>
    ${mNome} é historicamente um dos meses de maior incidência respiratória em SC. Municípios como São Joaquim e Lages registraram aumento superior a 60% nas internações neste período.`;
  } else {
    alertEl.className='alerta-box verde';
    alertText.innerHTML=`<strong>✅ Período de Menor Risco Histórico.</strong><br>
    Com base em padrões históricos, o mês atual (${mNome}) apresenta temperaturas mais elevadas em SC, associadas à menor incidência respiratória. Recomenda-se manutenção do monitoramento nos municípios de maior altitude.`;
  }

  // Calendário sazonal
  const meses=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const niveis=[15,12,18,25,45,75,95,90,60,30,18,14];
  document.getElementById('calendario-sazonal').innerHTML=meses.map((m,i)=>{
    const n=niveis[i];
    let bg,cor,emoji;
    if(n<25){bg='rgba(59,130,246,0.2)';cor='var(--blue)';emoji='🔵';}
    else if(n<55){bg='rgba(245,158,11,0.2)';cor='var(--amber)';emoji='🟡';}
    else if(n<80){bg='rgba(239,68,68,0.2)';cor='var(--red)';emoji='🔴';}
    else{bg='rgba(139,92,246,0.2)';cor='var(--purple)';emoji='⬛';}
    return `<div class="cal-month" style="background:${bg};color:${cor}"><div>${emoji}</div><div style="font-size:16px;font-weight:700;margin:4px 0">${n}</div><div class="cal-month-label">${m}</div></div>`;
  }).join('');

  // Pressão SUS
  const ordem={Crítica:4,Alta:3,Moderada:2,Baixa:1};
  const pressoes=[...MUNICIPIOS].sort((a,b)=>(ordem[b.pressao_sus]||0)-(ordem[a.pressao_sus]||0)).slice(0,8);
  const cores={Crítica:'var(--purple)',Alta:'var(--red)',Moderada:'var(--amber)',Baixa:'var(--green)'};
  document.getElementById('pressao-grid').innerHTML=pressoes.map(m=>`
    <div class="gauge-card">
      <div style="font-family:var(--font-display);font-size:18px;font-weight:700;color:${cores[m.pressao_sus]||'var(--muted)'};margin-bottom:4px">${m.pressao_sus||'—'}</div>
      <div class="gauge-label">${m.municipio_nome}</div>
    </div>`).join('');

  // Tendências
  const anos=anosDisponiveis(MUNICIPIOS);
  const totais=anos.map(a=>{
    return Math.round(MUNICIPIOS.reduce((s,m)=>s + estimarTotalAno(m, a),0));
  });
  renderChart('chart-tendencias',{type:'line',data:{labels:anos,datasets:[{label:'Internações Anuais — SC',data:totais,borderColor:'#00c2ff',backgroundColor:'rgba(0,194,255,0.08)',tension:0.3,fill:true,pointRadius:6,pointBackgroundColor:'#00c2ff'}]},options:{...chartOpts({yLabel:'Internações'}),plugins:{legend:{display:true,labels:{color:'#8bacc8',font:{size:11}}},tooltip:{...chartOpts().plugins.tooltip}}}});

  // Tabela vulnerabilidade
  const sorted=[...MUNICIPIOS].sort((a,b)=>(ordem[b.vulnerabilidade]||0)-(ordem[a.vulnerabilidade]||0));
  document.getElementById('tbody-vulnerabilidade').innerHTML=sorted.map(m=>`
    <tr>
      <td style="font-weight:500;color:var(--text-primary)">${m.municipio_nome}</td>
      <td>${badgeVulner(m.vulnerabilidade)}</td>
      <td>${badgeRisco(m.classificacao_risco)}</td>
      <td style="font-family:var(--font-mono)">${m.temp_media?.toFixed(1)}°C</td>
      <td style="font-family:var(--font-mono)">${m.int_media_mensal?.toFixed(1)}</td>
      <td style="font-family:var(--font-mono)">${m.correlacao_pearson}</td>
      <td style="font-size:12px;color:var(--text-muted)">${m.estacao_inmet}</td>
    </tr>`).join('');
}

// ================================================================
// MAPA
// ================================================================
function renderTabelaMapa() {
  const sorted=[...MUNICIPIOS].sort((a,b)=>b.total_internacoes-a.total_internacoes);
  document.getElementById('tbody-mapa').innerHTML=sorted.map(m=>`
    <tr onclick="selecionarMunicipio('${m.municipio_ibge}')" style="cursor:pointer">
      <td style="font-weight:500;color:var(--text-primary)">${m.municipio_nome}</td>
      <td style="font-family:var(--font-mono)">${m.temp_media?.toFixed(1)}°C</td>
      <td style="font-family:var(--font-mono)">${Number(m.total_internacoes).toLocaleString('pt-BR')}</td>
      <td style="font-family:var(--font-mono)">${m.correlacao_pearson}</td>
      <td>${badgeVulner(m.vulnerabilidade)}</td>
      <td><button class="btn btn-outline" style="padding:4px 10px;font-size:11px" onclick="event.stopPropagation();selecionarMunicipio('${m.municipio_ibge}')">Ver</button></td>
    </tr>`).join('');
}

function selecionarMunicipio(ibge) {
  const m = MUNICIPIOS.find(x => x.municipio_ibge === ibge);
  if (!m) return;
  const painel = document.getElementById('painel-municipio');
  if (!painel) return;
  painel.innerHTML = `
    <div style="margin-bottom:16px">
      <div style="font-family:var(--font-display);font-size:22px;font-weight:700;color:var(--cyan)">${m.municipio_nome}</div>
      <div style="font-size:11px;color:var(--text-muted)">IBGE: ${m.municipio_ibge}</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;font-size:13px">
      ${_panelRow('🌡️ Temperatura Média', m.temp_media?.toFixed(1)+'°C')}
      ${_panelRow('🏥 Total Internações', Number(m.total_internacoes).toLocaleString('pt-BR'))}
      ${_panelRow('📊 Correlação (r)', m.correlacao_pearson)}
      ${_panelRow('📈 IV', m.information_value?.toFixed(4)+' — '+m.iv_classificacao)}
      ${_panelRow('⚠️ Risco', badgeRisco(m.classificacao_risco))}
      ${_panelRow('🎯 Vulnerabilidade', badgeVulner(m.vulnerabilidade))}
      ${_panelRow('📡 Estação INMET', m.estacao_inmet)}
      ${m.distancia_estacao_km>0?_panelRow('📍 Distância', m.distancia_estacao_km+' km'):''}
    </div>
    <div style="margin-top:14px;padding:12px;background:var(--bg-surface);border-radius:var(--radius);font-size:12px;color:var(--text-muted);line-height:1.5">${m.insights?.[0]||''}</div>
    <button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="abrirPaginaMunicipio('${ibge}')">Ver página completa →</button>`;
}

function _panelRow(label, value) {
  return `<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border)">
    <span style="color:var(--text-muted)">${label}</span>
    <span style="color:var(--text-primary);font-weight:500">${value}</span>
  </div>`;
}

function abrirPaginaMunicipio(ibge) {
  window.location.href = 'pages/municipio.html?ibge=' + encodeURIComponent(ibge);
}

async function inicializarMapaCanvas() {
  try {
    const resp = await fetch('../data/municipios_sc.geojson');
    if (!resp.ok) throw new Error('GeoJSON não encontrado');
    const geojson = await resp.json();
    const loading = document.getElementById('mapa-loading');
    if (loading) loading.style.display='none';
    if (window.Mapa) {
      Mapa.inicializar('mapa-canvas-real', geojson,
        MUNICIPIOS.map(m=>({...m, ibge:m.municipio_ibge, nome:m.municipio_nome})),
        (ibge) => { selecionarMunicipio(ibge); }
      );
    }
  } catch(e) {
    const loading=document.getElementById('mapa-loading');
    if(loading) loading.innerHTML='<div style="font-size:20px;margin-bottom:6px">🗺️</div><div style="font-size:11px;max-width:200px;text-align:center">Consulte o Ranking para dados municipais detalhados</div>';
  }
}

function atualizarMapa() {
  const v=document.getElementById('mapa-variavel')?.value;
  if(window.Mapa) Mapa.setVariavel(v);
}

// ================================================================
// COMPARATIVO
// ================================================================
function atualizarComparativo() {
  const ibge1=document.getElementById('comp-mun1')?.value;
  const ibge2=document.getElementById('comp-mun2')?.value;
  const m1=MUNICIPIOS.find(m=>m.municipio_ibge===ibge1)||MUNICIPIOS[0];
  const m2=MUNICIPIOS.find(m=>m.municipio_ibge===ibge2)||MUNICIPIOS[1];
  if(!m1||!m2) return;

  const metricas=[
    {label:'Total Internações',k:'total_internacoes',fmt:v=>Number(v).toLocaleString('pt-BR')},
    {label:'Temp. Média',k:'temp_media',fmt:v=>v?.toFixed(1)+'°C'},
    {label:'Correlação (r)',k:'correlacao_pearson',fmt:v=>v},
    {label:'IV',k:'information_value',fmt:v=>v?.toFixed(2)},
    {label:'Risco',k:'classificacao_risco',fmt:v=>badgeRisco(v)},
    {label:'Vulnerabilidade',k:'vulnerabilidade',fmt:v=>badgeVulner(v)},
  ];

  document.getElementById('compare-cards').innerHTML=[m1,m2].map(m=>`
    <div class="card">
      <div style="font-family:var(--font-display);font-size:20px;font-weight:700;color:var(--cyan);margin-bottom:16px">${m.municipio_nome}</div>
      ${metricas.map(mt=>`<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px">
        <span style="color:var(--text-muted)">${mt.label}</span>
        <span style="color:var(--text-primary);font-weight:500">${mt.fmt(m[mt.k])}</span>
      </div>`).join('')}
    </div>`).join('');

  const meses=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  renderChart('chart-comparativo',{type:'line',data:{labels:meses,datasets:[
    {label:m1.municipio_nome,data:serieFiltradasMes(m1),borderColor:'#00c2ff',backgroundColor:'rgba(0,194,255,0.1)',tension:0.4,fill:true},
    {label:m2.municipio_nome,data:serieFiltradasMes(m2),borderColor:'#f59e0b',backgroundColor:'rgba(245,158,11,0.1)',tension:0.4,fill:true},
  ]},options:{...chartOpts({yLabel:'Internações'}),plugins:{legend:{display:true,labels:{color:'#8bacc8',font:{size:11}}},tooltip:{...chartOpts().plugins.tooltip}}}});
}

// ================================================================
// EXPORTAÇÃO PNG POR GRÁFICO INDIVIDUAL
// ================================================================
function exportarGraficoPNG(canvasId, nome) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) { alert('Gráfico não encontrado.'); return; }
  // Fundo escuro para PNG
  const offscreen = document.createElement('canvas');
  offscreen.width  = canvas.width;
  offscreen.height = canvas.height;
  const ctx = offscreen.getContext('2d');
  ctx.fillStyle = '#0d1527';
  ctx.fillRect(0, 0, offscreen.width, offscreen.height);
  ctx.drawImage(canvas, 0, 0);
  const a = document.createElement('a');
  a.href = offscreen.toDataURL('image/png');
  a.download = (nome||canvasId) + '_respiralert.png';
  a.click();
}

// ================================================================
// EXPORTAÇÃO PDF (dashboard ou view ativa)
// ================================================================
async function exportarPDF() {
  // Carregar jsPDF e html2canvas sob demanda
  const carregarScript = (src) => new Promise((res,rej)=>{
    if(document.querySelector(`script[src="${src}"]`)){res();return;}
    const s=document.createElement('script'); s.src=src; s.onload=res; s.onerror=rej;
    document.head.appendChild(s);
  });

  try {
    await carregarScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
    await carregarScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js');
  } catch(e) {
    alert('Erro ao carregar bibliotecas de PDF. Verifique sua conexão.'); return;
  }

  const {jsPDF} = window.jspdf;
  const pdf = new jsPDF({orientation:'landscape',unit:'mm',format:'a4'});
  const W=297, H=210;

  // Captura a view ativa
  const viewAtiva = document.querySelector('.view.active');
  if (!viewAtiva) { alert('Nenhuma view ativa encontrada.'); return; }

  // Adicionar cabeçalho
  pdf.setFillColor(8,14,28);
  pdf.rect(0,0,W,H,'F');
  pdf.setTextColor(0,194,255);
  pdf.setFont('helvetica','bold');
  pdf.setFontSize(16);
  pdf.text('RespirAlert SC — Monitoramento Climático e Respiratório', W/2, 14, {align:'center'});
  pdf.setFontSize(9);
  pdf.setTextColor(74,96,128);
  pdf.text(`Gerado em ${new Date().toLocaleString('pt-BR')} · Dados públicos DATASUS + INMET · Uso acadêmico`, W/2, 20, {align:'center'});

  // Capturar canvas dos gráficos visíveis
  const canvases = viewAtiva.querySelectorAll('canvas');
  const positions = [[10,25],[155,25],[10,115],[155,115]];
  let idx=0;

  for (const canvas of canvases) {
    if (idx >= positions.length) { pdf.addPage(); pdf.setFillColor(8,14,28); pdf.rect(0,0,W,H,'F'); idx=0; }
    const [px,py] = positions[idx];
    const imgData = canvas.toDataURL('image/png');
    const ratio = canvas.width/canvas.height;
    const w=130, h=w/ratio;
    pdf.addImage(imgData,'PNG',px,py,w,Math.min(h,80));
    idx++;
  }

  // Rodapé disclaimer
  pdf.setFontSize(7);
  pdf.setTextColor(74,96,128);
  pdf.text('Este documento é de uso acadêmico e informativo. Os resultados representam associações estatísticas e não estabelecem causalidade. Não constitui diagnóstico médico.', W/2, H-6, {align:'center'});

  pdf.save('respiralert_sc_relatorio.pdf');
}

// ================================================================
// NAVEGAÇÃO
// ================================================================
function navegarPara(id) {
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  const view=document.getElementById('view-'+id);
  if(view){view.classList.add('active');}
  const nav=document.getElementById('nav-'+id);
  if(nav) nav.classList.add('active');
  if(id==='temporal') setTimeout(atualizarTemporal,50);
  if(id==='mapa')     setTimeout(inicializarMapaCanvas,100);
  if(id==='insights') renderInsights();
  if(id==='impacto')   setTimeout(renderImpacto,50);
  if(id==='comparativo') setTimeout(atualizarComparativo,50);
  if(id==='previsao')  renderPrevisao();
  if(id==='modelo')    renderModelo();
}

// ================================================================
// UTILITÁRIOS
// ================================================================
function badgeRisco(r){
  const cls={Baixo:'badge-baixo',Moderado:'badge-moderado',Alto:'badge-alto','Muito Alto':'badge-muito-alto'};
  return `<span class="badge ${cls[r]||''}">${r||'—'}</span>`;
}
function badgeVulner(v){
  const cls={Baixa:'badge-baixo',Moderada:'badge-moderado',Alta:'badge-alto','Muito Alta':'badge-muito-alto'};
  return `<span class="badge ${cls[v]||''}">${v||'—'}</span>`;
}

function chartOpts({title='',xLabel='',yLabel='',dual=false}={}) {
  const grid={color:'rgba(0,194,255,0.06)'};
  const ticks={color:'#4a6080',font:{size:11}};
  const opts={
    responsive:true, maintainAspectRatio:false,
    interaction:{mode:'index',intersect:false},
    plugins:{
      legend:{display:false},
      tooltip:{backgroundColor:'rgba(13,21,39,0.95)',borderColor:'rgba(0,194,255,0.3)',borderWidth:1,titleColor:'#e8f4fd',bodyColor:'#8bacc8',padding:10}
    },
    scales:{
      x:{grid,ticks,title:xLabel?{display:true,text:xLabel,color:'#4a6080',font:{size:11}}:{display:false}},
      y:{grid,ticks,title:yLabel?{display:true,text:yLabel,color:'#4a6080',font:{size:11}}:{display:false}},
    }
  };
  if(dual) opts.scales.y2={position:'right',grid:{display:false},ticks,title:{display:true,text:'Temperatura (°C)',color:'#4a6080',font:{size:11}}};
  return opts;
}

function renderChart(id, config) {
  const canvas=document.getElementById(id);
  if(!canvas) return;
  if(chartInstances[id]) chartInstances[id].destroy();
  chartInstances[id]=new Chart(canvas,config);
}

function toggleTema() {
  const html=document.documentElement;
  html.dataset.theme=html.dataset.theme==='dark'?'light':'dark';
}

function exportarDados() {
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([JSON.stringify(DADOS,null,2)],{type:'application/json'}));
  a.download='respiralert_sc_dados.json'; a.click();
}

// ================================================================
// BOOT
// ================================================================
window.addEventListener('DOMContentLoaded', carregarDados);

// ================================================================
// EVOLUÇÃO 1 — PREVISÃO METEOROLÓGICA 7 DIAS (Open-Meteo)
// ================================================================
let PREVISAO = null;

async function carregarPrevisao() {
  try {
    const resp = await fetch('../data/previsao_sc.json');
    if (!resp.ok) throw new Error('previsao_sc.json não encontrado');
    PREVISAO = await resp.json();
    console.log(`Previsão carregada: ${PREVISAO.total} municípios`);
  } catch(e) {
    console.warn('Previsão não disponível:', e.message);
    PREVISAO = null;
  }
}

function renderPrevisao() {
  if (!PREVISAO) {
    document.getElementById('previsao-fonte').textContent = 'Dados não disponíveis';
    return;
  }

  // Preencher select de municípios
  const sel = document.getElementById('filter-previsao-mun');
  if (sel && sel.options.length <= 1) {
    PREVISAO.municipios.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.municipio_ibge;
      opt.textContent = m.municipio_nome;
      sel.appendChild(opt);
    });
  }

  // Fonte dos dados
  const fonte = PREVISAO.municipios[0]?.fonte || 'Open-Meteo';
  document.getElementById('previsao-fonte').textContent =
    fonte.includes('Fallback') ? '📦 Sazonalidade histórica' : '🌐 Open-Meteo (tempo real)';

  // Alerta geral: municípios com risco Alto ou Muito Alto esta semana
  const emAlerta = PREVISAO.municipios.filter(m =>
    ['Alto','Muito Alto'].includes(m.risco_predominante?.nivel)
  );
  const alertaBox   = document.getElementById('previsao-alerta-box');
  const alertaTitle = document.getElementById('previsao-alerta-title');
  const alertaTexto = document.getElementById('previsao-alerta-texto');

  if (emAlerta.length > 0) {
    alertaBox.style.borderColor  = 'rgba(239,68,68,0.4)';
    alertaBox.style.background   = 'rgba(239,68,68,0.05)';
    alertaTitle.style.color      = 'var(--red)';
    alertaTitle.textContent      = `⚠️ ${emAlerta.length} município(s) com risco elevado esta semana`;
    alertaTexto.innerHTML = `Com base na previsão climática dos próximos 7 dias, os municípios 
      <strong style="color:var(--text-primary)">${emAlerta.slice(0,5).map(m=>m.municipio_nome).join(', ')}${emAlerta.length>5?` e mais ${emAlerta.length-5}`:''}</strong> 
      apresentam temperatura prevista abaixo de 15°C, período historicamente associado a maior incidência de internações respiratórias em SC.`;
  } else {
    alertaBox.style.borderColor  = 'rgba(16,185,129,0.4)';
    alertaBox.style.background   = 'rgba(16,185,129,0.05)';
    alertaTitle.style.color      = 'var(--green)';
    alertaTitle.textContent      = '✅ Nenhum município em alerta esta semana';
    alertaTexto.textContent      = 'As temperaturas previstas para os próximos 7 dias estão dentro da faixa de menor risco respiratório histórico para SC.';
  }

  // Tabela de municípios em alerta
  const tbody = document.getElementById('tbody-previsao-alerta');
  const maisGraves = [...PREVISAO.municipios]
    .sort((a,b) => (a.temp_media_7dias||99) - (b.temp_media_7dias||99))
    .slice(0, 15);

  tbody.innerHTML = maisGraves.map(m => {
    const r = m.risco_predominante || {};
    const badgeCls = {Baixo:'badge-baixo',Moderado:'badge-moderado',Alto:'badge-alto','Muito Alto':'badge-muito-alto'}[r.nivel] || '';
    const mun_ind = MUNICIPIOS.find(x => x.municipio_ibge === m.municipio_ibge);
    return `<tr>
      <td style="font-weight:500;color:var(--text-primary)">${m.municipio_nome}</td>
      <td style="font-family:var(--font-mono)">${m.temp_media_7dias}°C</td>
      <td style="font-family:var(--font-mono)">${m.dia_mais_frio?.temp_min ?? '—'}°C</td>
      <td><span class="badge ${badgeCls}">${r.nivel || '—'}</span></td>
      <td style="font-size:12px;color:var(--text-muted)">${mun_ind?.regiao || (m.municipio_nome.includes('Joaquim')||m.municipio_nome.includes('Lages')?'Serrana':'SC')}</td>
    </tr>`;
  }).join('');

  renderPrevisaoMunicipio();
}

function renderPrevisaoMunicipio() {
  if (!PREVISAO) return;
  const ibge = document.getElementById('filter-previsao-mun')?.value || 'TODOS';
  const lbl  = document.getElementById('previsao-mun-label');

  let mun = ibge === 'TODOS'
    ? PREVISAO.municipios.find(m => m.municipio_nome === 'Florianópolis') || PREVISAO.municipios[0]
    : PREVISAO.municipios.find(m => m.municipio_ibge === ibge) || PREVISAO.municipios[0];

  if (!mun) return;
  if (lbl) lbl.textContent = mun.municipio_nome;

  const dias = mun.previsao_diaria || [];
  const labels    = dias.map(d => d.data?.slice(5) || '');
  const tempMedia = dias.map(d => d.temp_media);
  const tempMax   = dias.map(d => d.temp_max);
  const tempMin   = dias.map(d => d.temp_min);

  // Cards dos 7 dias
  const cardsEl = document.getElementById('previsao-cards-7dias');
  if (cardsEl) {
    cardsEl.innerHTML = dias.map(d => {
      const r = d.risco || {};
      const cls = {Baixo:'badge-baixo',Moderado:'badge-moderado',Alto:'badge-alto','Muito Alto':'badge-muito-alto'}[r.nivel]||'';
      return `<div class="card" style="padding:14px;text-align:center">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">${d.data?.slice(5)||''}</div>
        <div style="font-family:var(--font-display);font-size:24px;font-weight:700;color:${r.cor||'var(--text-primary)'}">${d.temp_media}°C</div>
        <div style="font-size:10px;color:var(--text-muted);margin:2px 0">${d.temp_min}° / ${d.temp_max}°</div>
        <span class="badge ${cls}" style="font-size:10px;margin-top:4px">${r.nivel||'—'}</span>
        <div style="font-size:10px;color:var(--text-muted);margin-top:4px">🌧 ${d.precipitacao}mm</div>
      </div>`;
    }).join('');
  }

  // Gráfico
  renderChart('chart-previsao-temp', {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label:'Temp. Média', data:tempMedia, borderColor:'#f59e0b', backgroundColor:'rgba(245,158,11,0.1)', tension:0.4, fill:false, pointRadius:6, pointBackgroundColor:'#f59e0b' },
        { label:'Máxima',      data:tempMax,   borderColor:'rgba(239,68,68,0.6)', borderDash:[4,3], tension:0.3, pointRadius:3 },
        { label:'Mínima',      data:tempMin,   borderColor:'rgba(59,130,246,0.6)', borderDash:[4,3], tension:0.3, pointRadius:3 },
      ]
    },
    options: {
      ...chartOpts({ yLabel:'Temperatura (°C)' }),
      plugins: {
        legend: { display:true, labels:{color:'#8bacc8',font:{size:11}} },
        tooltip: { ...chartOpts().plugins.tooltip,
          callbacks: { afterLabel: ctx => {
            const d = dias[ctx.dataIndex];
            return d ? `Risco: ${d.risco?.nivel}` : '';
          }}
        },
        annotation: {
          annotations: {
            linhaBaixo: { type:'line', yMin:18, yMax:18, borderColor:'rgba(16,185,129,0.4)', borderWidth:1, borderDash:[4,4], label:{display:true, content:'Risco Baixo (18°C)', color:'rgba(16,185,129,0.7)', font:{size:10}} },
            linhaAlto:  { type:'line', yMin:12, yMax:12, borderColor:'rgba(239,68,68,0.4)',  borderWidth:1, borderDash:[4,4], label:{display:true, content:'Risco Alto (12°C)', color:'rgba(239,68,68,0.7)',  font:{size:10}} },
          }
        }
      }
    }
  });
}

// ================================================================
// EVOLUÇÃO 3 — MODELO PREDITIVO
// ================================================================
let MODELO = null;

async function carregarModelo() {
  try {
    const resp = await fetch('../data/modelo_preditivo.json');
    if (!resp.ok) throw new Error('modelo_preditivo.json não encontrado');
    MODELO = await resp.json();
    console.log(`Modelo carregado: ${MODELO.total_municipios} municípios, R²=${MODELO.r2_medio}`);
  } catch(e) {
    console.warn('Modelo não disponível:', e.message);
    MODELO = null;
  }
}

function renderModelo() {
  if (!MODELO) {
    document.getElementById('modelo-kpis').innerHTML =
      '<div style="color:var(--text-muted);padding:20px">Modelo preditivo não disponível.</div>';
    return;
  }

  // Popular select
  const sel = document.getElementById('filter-modelo-mun');
  if (sel && sel.options.length === 0) {
    MODELO.modelos.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.municipio_ibge;
      opt.textContent = `${m.municipio_nome} (R²=${m.r_quadrado})`;
      sel.appendChild(opt);
    });
  }

  renderModeloMunicipio();
  renderModeloRankingR2();
}

function renderModeloMunicipio() {
  if (!MODELO) return;
  const ibge = document.getElementById('filter-modelo-mun')?.value;
  const mod  = ibge
    ? MODELO.modelos.find(m => m.municipio_ibge === ibge) || MODELO.modelos[0]
    : MODELO.modelos[0];
  if (!mod) return;

  // KPIs
  const kpis = [
    { label:'R² do Modelo',       val: mod.r_quadrado,        cor:'var(--purple)', detail:'Variação explicada' },
    { label:'Erro Médio (MAE)',    val: mod.mae+' intern.',    cor:'var(--amber)',  detail:'Mean Absolute Error' },
    { label:'Observações',         val: mod.n_observacoes,     cor:'var(--cyan)',   detail:'Registros de treino' },
    { label:'Pico Projetado',      val: (mod.pico_projetado?.internacoes_estimadas||0)+' intern.', cor:'var(--red)',    detail: mod.pico_projetado?.label||'' },
    { label:'Vale Projetado',      val: (mod.vale_projetado?.internacoes_estimadas||0)+' intern.', cor:'var(--green)',  detail: mod.vale_projetado?.label||'' },
    { label:'Tendência Projeção',  val: mod.tendencia_projecao, cor:'var(--text-primary)', detail:'Próximos 12 meses' },
  ];
  document.getElementById('modelo-kpis').innerHTML = kpis.map(k => `
    <div class="kpi-card">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value" style="color:${k.cor};font-size:22px">${k.val}</div>
      <div class="kpi-detail">${k.detail}</div>
    </div>`).join('');

  const badge = document.getElementById('modelo-r2-badge');
  if (badge) badge.textContent = `R²=${mod.r_quadrado}`;

  // Gráfico de projeção
  const proj  = mod.projecao_12meses || [];
  const labels = proj.map(p => p.label);
  const vals   = proj.map(p => p.internacoes_estimadas);
  const inf    = proj.map(p => p.intervalo_inferior);
  const sup    = proj.map(p => p.intervalo_superior);

  renderChart('chart-modelo-proj', {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label:'Estimativa',          data:vals, borderColor:'#8b5cf6', backgroundColor:'rgba(139,92,246,0.15)', tension:0.4, fill:false, pointRadius:5, pointBackgroundColor:'#8b5cf6', borderWidth:2 },
        { label:'Intervalo Superior',  data:sup,  borderColor:'rgba(139,92,246,0.3)', borderDash:[4,4], tension:0.4, pointRadius:0, fill:false },
        { label:'Intervalo Inferior',  data:inf,  borderColor:'rgba(139,92,246,0.3)', borderDash:[4,4], tension:0.4, pointRadius:0, fill:'1', backgroundColor:'rgba(139,92,246,0.07)' },
      ]
    },
    options: {
      ...chartOpts({yLabel:'Internações Estimadas'}),
      plugins: {
        legend: { display:true, labels:{color:'#8bacc8',font:{size:11}} },
        tooltip: { ...chartOpts().plugins.tooltip,
          callbacks: { afterLabel: ctx => {
            const p = proj[ctx.dataIndex];
            return p && ctx.datasetIndex===0 ? `Temp. prevista: ${p.temp_prevista}°C\nIntervalo: ${p.intervalo_inferior}–${p.intervalo_superior}` : null;
          }}
        }
      }
    }
  });

  // Coeficientes
  const coefs = mod.coeficientes || {};
  const coefLabels = {
    intercepto:'Intercepto (β₀)', temperatura:'Temperatura (β₁)',
    umidade:'Umidade (β₂)', sazon_seno:'Sazonalidade sin (β₃)',
    sazon_cosseno:'Sazonalidade cos (β₄)', tendencia:'Tendência Temporal (β₅)'
  };
  document.getElementById('modelo-coefs').innerHTML = Object.entries(coefs).map(([k,v]) => `
    <div class="gauge-card" style="text-align:left">
      <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">${coefLabels[k]||k}</div>
      <div style="font-family:var(--font-mono);font-size:18px;font-weight:600;color:${v<0?'var(--red)':v>0?'var(--green)':'var(--text-muted)'}">${v>0?'+':''}${v}</div>
    </div>`).join('');

  // Interpretação
  document.getElementById('modelo-interpretacao').innerHTML =
    (mod.interpretacao||[]).map(txt => `
      <div class="insight-item">
        <div class="insight-icon">🔬</div>
        <div class="insight-text">${txt}</div>
      </div>`).join('') || '<div style="color:var(--text-muted)">Interpretação não disponível.</div>';
}

function renderModeloRankingR2() {
  if (!MODELO) return;
  const sorted = [...MODELO.modelos].sort((a,b)=>b.r_quadrado-a.r_quadrado).slice(0,15);
  renderChart('chart-modelo-r2', {
    type: 'bar',
    data: {
      labels: sorted.map(m=>m.municipio_nome),
      datasets: [{
        label:'R²',
        data: sorted.map(m=>m.r_quadrado),
        backgroundColor: sorted.map(m=>m.r_quadrado>=0.7?'rgba(16,185,129,0.7)':m.r_quadrado>=0.4?'rgba(245,158,11,0.7)':'rgba(239,68,68,0.6)'),
        borderRadius:4,
      }]
    },
    options: {
      ...chartOpts({yLabel:'R²'}),
      indexAxis:'y',
      plugins:{
        legend:{display:false},
        tooltip:{...chartOpts().plugins.tooltip}
      },
      scales:{
        x:{...chartOpts().scales?.x, min:0, max:1},
        y:{grid:{color:'rgba(0,194,255,0.04)'}, ticks:{color:'#4a6080',font:{size:10}}}
      }
    }
  });
}
