/**
 * dashboard.js
 * Componente do Dashboard Executivo — KPIs e gráficos principais.
 * Depende de: graficos.js, utils.js
 */

const Dashboard = (() => {

  // ----------------------------------------------------------------
  // KPIs
  // ----------------------------------------------------------------
  function renderKPIs(dados) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

    set('kpi-municipios',  dados.total_municipios);
    set('kpi-internacoes', Number(dados.total_internacoes).toLocaleString('pt-BR'));
    set('kpi-temp',        dados.temp_media_estadual + '°C');
    set('kpi-correlacao',  dados.correlacao_media_estadual);
    set('kpi-maior',       dados.municipio_maior_incidencia);
    set('kpi-menor',       dados.municipio_menor_incidencia);
    set('last-update-topbar', '✓ ' + dados.ultima_atualizacao);

    const corrEl = document.getElementById('kpi-correlacao');
    if (corrEl) corrEl.style.color = 'var(--cyan)';
  }

  // ----------------------------------------------------------------
  // Gráficos do dashboard
  // ----------------------------------------------------------------
  function renderGraficos(municipios) {
    const mesesLabels = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

    // Agregar internações mensais de todos os municípios
    const internacoesMes = Array(12).fill(0);
    municipios.forEach(m => {
      const saz = m.sazonalidade_mensal || m.sazonalidade || {};
      for (let i = 1; i <= 12; i++) {
        internacoesMes[i-1] += parseFloat(saz[i] || saz[String(i)] || 0);
      }
    });

    const sazonTempEstado = [21.0,21.2,20.4,18.5,16.0,13.5,12.8,13.2,15.0,17.5,19.5,20.8];

    // 1. Internações mensais (barras)
    Graficos.bar('chart-internacoes-mensal', {
      labels: mesesLabels,
      datasets: [{
        label: 'Internações (SC)',
        data: internacoesMes,
        backgroundColor: internacoesMes.map((_, i) =>
          i >= 5 && i <= 7 ? 'rgba(239,68,68,0.75)' : 'rgba(0,194,255,0.5)'
        ),
        borderRadius: 4,
      }]
    });

    // 2. Scatter correlação
    const scatterData = municipios.map(m => ({
      x: m.temp_media,
      y: m.total_internacoes,
      nome: m.municipio_nome || m.nome,
    }));
    Graficos.scatter('chart-correlacao', scatterData);

    // 3. Sazonalidade dual-axis
    Graficos.dual('chart-sazonalidade', {
      labels: mesesLabels,
      series1: { label: 'Internações (índice)', data: internacoesMes.map(v => (v / Math.max(...internacoesMes) * 100).toFixed(1)), color: '#ef4444' },
      series2: { label: 'Temperatura (°C)', data: sazonTempEstado, color: '#f59e0b' },
    });

    // 4. Distribuição de risco (doughnut)
    const riscos = { Baixo:0, Moderado:0, Alto:0, 'Muito Alto':0 };
    municipios.forEach(m => { riscos[m.classificacao_risco || m.risco] = (riscos[m.classificacao_risco || m.risco] || 0) + 1; });
    Graficos.doughnut('chart-risco', {
      labels: Object.keys(riscos),
      data: Object.values(riscos),
      colors: ['rgba(16,185,129,0.8)','rgba(245,158,11,0.8)','rgba(239,68,68,0.8)','rgba(139,92,246,0.8)'],
    });
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------
  return { renderKPIs, renderGraficos };

})();

window.Dashboard = Dashboard;
