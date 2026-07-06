/**
 * insights.js
 * Módulo de geração e renderização de Insights Automáticos.
 */

const Insights = (() => {

  const ICONES = ['📉','❄️','📅','🔬','📊','📈','🌡️','⚠️','🏔️','📌'];

  // ----------------------------------------------------------------
  // Gerar insights adicionais client-side (complementam os do JSON)
  // ----------------------------------------------------------------
  function _gerarInsightsExtras(m) {
    const extras = [];
    const nome = m.municipio_nome || m.nome;
    const corr = parseFloat(m.correlacao_pearson || m.correlacao || 0);
    const temp = parseFloat(m.temp_media || 0);
    const iv   = parseFloat(m.information_value || m.iv || 0);
    const tend = m.tendencia_internacoes;
    const vulner = m.vulnerabilidade;

    // Comparação com média estadual
    if (window.DADOS_GLOBAIS) {
      const corrMedia = DADOS_GLOBAIS.correlacao_media_estadual;
      if (Math.abs(corr) > Math.abs(corrMedia) + 0.05) {
        extras.push(`A associação observada em ${nome} (r=${corr}) é superior à média estadual (r=${corrMedia}), indicando sensibilidade climática acima da média de SC.`);
      }
    }

    // Alerta por altitude climática
    if (temp < 14) {
      extras.push(`${nome} apresenta temperatura média histórica de ${temp}°C, classificando-se como município de clima frio/temperado frio, com maior risco respiratório durante todo o inverno austral.`);
    }

    // Tendência
    if (tend && tend.direcao === 'crescente' && vulner === 'Muito Alta') {
      extras.push(`Combinação crítica: ${nome} apresenta tendência crescente de internações E vulnerabilidade Muito Alta. Requer atenção especial no planejamento de saúde pública local.`);
    }

    // IV muito forte
    if (iv > 1.0) {
      extras.push(`O Information Value de ${iv.toFixed(2)} em ${nome} indica que a temperatura possui altíssimo poder explicativo sobre a variação das internações respiratórias neste município.`);
    }

    return extras;
  }

  // ----------------------------------------------------------------
  // Renderização
  // ----------------------------------------------------------------
  function renderizar(municipios, ibgeFiltro = 'TODOS') {
    const container = document.getElementById('insights-container');
    if (!container) return;

    let lista = municipios;
    if (ibgeFiltro !== 'TODOS') {
      lista = municipios.filter(m => (m.ibge || m.municipio_ibge) === ibgeFiltro);
    }

    const todos = [];
    lista.forEach(m => {
      const base   = m.insights || [];
      const extras = _gerarInsightsExtras(m);
      const nome   = m.municipio_nome || m.nome;
      [...base, ...extras].forEach(txt => todos.push({ nome, ibge: m.ibge || m.municipio_ibge, txt }));
    });

    if (!todos.length) {
      container.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center">Nenhum insight disponível para a seleção atual.</div>';
      return;
    }

    container.innerHTML = todos.map((ins, i) => `
      <div class="insight-item" style="animation-delay:${i * 0.04}s">
        <div class="insight-icon">${ICONES[i % ICONES.length]}</div>
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--cyan);margin-bottom:4px;letter-spacing:0.6px">
            ${ins.nome.toUpperCase()}
          </div>
          <div class="insight-text">${ins.txt}</div>
        </div>
      </div>
    `).join('');
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------
  return { renderizar };

})();

window.Insights = Insights;
