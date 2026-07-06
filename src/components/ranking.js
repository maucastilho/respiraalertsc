/**
 * ranking.js
 * Tabela dinâmica de ranking municipal com busca, filtros, ordenação e exportação CSV.
 */

const Ranking = (() => {

  let _municipios = [];
  let _ordem = { campo: 'total_internacoes', asc: false };
  let _onSelect = null;

  // ----------------------------------------------------------------
  // Inicialização
  // ----------------------------------------------------------------
  function inicializar(municipios, onSelect) {
    _municipios = municipios;
    _onSelect   = onSelect;
    renderizar();
  }

  // ----------------------------------------------------------------
  // Renderização
  // ----------------------------------------------------------------
  function renderizar() {
    const search = document.getElementById('search-ranking')?.value.toLowerCase() || '';
    const risco  = document.getElementById('filter-risco-ranking')?.value || 'TODOS';
    const vulner = document.getElementById('filter-vulner-ranking')?.value || 'TODOS';

    let dados = [..._municipios];
    if (search) dados = dados.filter(m => _nome(m).toLowerCase().includes(search));
    if (risco  !== 'TODOS') dados = dados.filter(m => (m.classificacao_risco || m.risco) === risco);
    if (vulner !== 'TODOS') dados = dados.filter(m => m.vulnerabilidade === vulner);

    dados.sort((a, b) => {
      const va = a[_ordem.campo] ?? 0;
      const vb = b[_ordem.campo] ?? 0;
      return _ordem.asc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });

    const tbody = document.getElementById('tbody-ranking');
    if (!tbody) return;

    tbody.innerHTML = dados.map((m, idx) => {
      const risco = m.classificacao_risco || m.risco || '';
      const vulner = m.vulnerabilidade || '';
      return `
      <tr onclick="Ranking.selecionarMunicipio('${m.ibge || m.municipio_ibge}')" style="cursor:pointer">
        <td style="color:var(--text-muted);font-family:var(--font-mono)">${String(idx+1).padStart(2,'0')}</td>
        <td style="font-weight:500;color:var(--text-primary)">${_nome(m)}</td>
        <td style="font-family:var(--font-mono)">${Number(m.total_internacoes).toLocaleString('pt-BR')}</td>
        <td style="font-family:var(--font-mono)">${parseFloat(m.temp_media).toFixed(1)}°C</td>
        <td style="font-family:var(--font-mono);color:${parseFloat(m.correlacao||m.correlacao_pearson) < -0.5 ? 'var(--red)' : 'var(--cyan)'}">${m.correlacao || m.correlacao_pearson}</td>
        <td style="font-family:var(--font-mono)">${parseFloat(m.iv||m.information_value).toFixed(2)}
          <span style="font-size:10px;color:var(--text-muted)">${m.iv_cls||m.iv_classificacao}</span></td>
        <td>${_badgeRisco(risco)}</td>
        <td>${_badgeVulner(vulner)}</td>
        <td style="font-size:12px;color:var(--text-muted)">
          ${m.estacao||m.estacao_inmet}${parseFloat(m.distancia_km||m.distancia_estacao_km||0) > 0 ? ` (${m.distancia_km||m.distancia_estacao_km}km)` : ''}
        </td>
      </tr>`;
    }).join('');

    const count = document.getElementById('ranking-count');
    if (count) count.textContent = `Exibindo ${dados.length} de ${_municipios.length} municípios`;
  }

  function ordenarPor(campo) {
    if (_ordem.campo === campo) _ordem.asc = !_ordem.asc;
    else { _ordem.campo = campo; _ordem.asc = false; }
    renderizar();
  }

  function selecionarMunicipio(ibge) {
    if (_onSelect) _onSelect(ibge);
  }

  // ----------------------------------------------------------------
  // Exportação CSV
  // ----------------------------------------------------------------
  function exportarCSV() {
    const cabecalho = ['Município','IBGE','Internações','Temp. Média','Correlação','IV','IV Classe','Risco','Vulnerabilidade','Estação INMET','Distância (km)'];
    const linhas = [cabecalho, ..._municipios.map(m => [
      _nome(m),
      m.ibge || m.municipio_ibge,
      m.total_internacoes,
      m.temp_media,
      m.correlacao || m.correlacao_pearson,
      m.iv || m.information_value,
      m.iv_cls || m.iv_classificacao,
      m.classificacao_risco || m.risco,
      m.vulnerabilidade,
      m.estacao || m.estacao_inmet,
      m.distancia_km || m.distancia_estacao_km || 0,
    ])];
    const csv = linhas.map(l => l.join(';')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
    a.download = 'respiralert_ranking_sc.csv';
    a.click();
  }

  // ----------------------------------------------------------------
  // Utilitários internos
  // ----------------------------------------------------------------
  function _nome(m) { return m.municipio_nome || m.nome || ''; }

  function _badgeRisco(r) {
    const cls = { 'Baixo':'badge-baixo','Moderado':'badge-moderado','Alto':'badge-alto','Muito Alto':'badge-muito-alto' };
    return `<span class="badge ${cls[r]||''}">${r}</span>`;
  }

  function _badgeVulner(v) {
    const cls = { 'Baixa':'badge-baixo','Moderada':'badge-moderado','Alta':'badge-alto','Muito Alta':'badge-muito-alto' };
    return `<span class="badge ${cls[v]||''}">${v}</span>`;
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------
  return { inicializar, renderizar, ordenarPor, selecionarMunicipio, exportarCSV };

})();

window.Ranking = Ranking;
