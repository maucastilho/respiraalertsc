/**
 * simulador.js
 * Simulador de Risco Respiratório por Temperatura.
 */

const Simulador = (() => {

  const FAIXAS = [
    { min: 18,  max: 99,  nivel: 'BAIXO',      cor: 'var(--green)',  borderCor: 'rgba(16,185,129,0.3)',   bgCor: 'var(--green-dim)',           desc: 'Temperaturas acima de 18°C estão historicamente associadas à menor incidência de internações respiratórias em SC.' },
    { min: 15,  max: 18,  nivel: 'MODERADO',   cor: 'var(--amber)',  borderCor: 'rgba(245,158,11,0.3)',   bgCor: 'var(--amber-dim)',            desc: 'Faixa de transição. Recomenda-se monitoramento preventivo, especialmente em populações vulneráveis.' },
    { min: 12,  max: 15,  nivel: 'ALTO',        cor: 'var(--red)',    borderCor: 'rgba(239,68,68,0.3)',    bgCor: 'var(--red-dim)',              desc: 'Temperaturas nessa faixa estão historicamente associadas a aumento significativo de internações respiratórias.' },
    { min: -99, max: 12,  nivel: 'MUITO ALTO', cor: 'var(--purple)', borderCor: 'rgba(139,92,246,0.3)',  bgCor: 'rgba(139,92,246,0.1)',        desc: 'Abaixo de 12°C: período crítico histórico. Municípios como São Joaquim e Lages apresentam aumento superior a 80% nas internações.' },
  ];

  function _getFaixa(temp) {
    return FAIXAS.find(f => temp >= f.min && temp < f.max) || FAIXAS[FAIXAS.length - 1];
  }

  // ----------------------------------------------------------------
  // Atualizar display
  // ----------------------------------------------------------------
  function atualizar(temp) {
    temp = parseFloat(temp);
    const faixa = _getFaixa(temp);

    const display = document.getElementById('sim-temp-display');
    const slider  = document.getElementById('sim-slider');
    const box     = document.getElementById('sim-risco-box');
    const nivel   = document.getElementById('sim-risco-nivel');
    const desc    = document.getElementById('sim-risco-desc');

    if (display) { display.textContent = temp.toFixed(1) + '°C'; display.style.color = faixa.cor; }
    if (slider)    slider.value = temp;
    if (box)     { box.style.background = faixa.bgCor; box.style.borderColor = faixa.borderCor; }
    if (nivel)   { nivel.textContent = faixa.nivel; nivel.style.color = faixa.cor; }
    if (desc)      desc.textContent = faixa.desc;

    // Atualiza a linha vertical no histograma
    _atualizarLinhaHistograma(temp);
  }

  // ----------------------------------------------------------------
  // Histograma de distribuição histórica
  // ----------------------------------------------------------------
  function renderHistograma() {
    if (!window.Graficos) return;
    const labels    = ['≤5','5–8','8–11','11–14','14–17','17–20','20–23','23–26','26–29','≥29'];
    const internacoes = [95, 88, 82, 74, 58, 38, 25, 18, 14, 12];
    const cores     = [
      'rgba(139,92,246,0.85)', 'rgba(139,92,246,0.75)', 'rgba(239,68,68,0.80)',
      'rgba(239,68,68,0.70)',  'rgba(245,158,11,0.80)', 'rgba(245,158,11,0.65)',
      'rgba(16,185,129,0.65)', 'rgba(16,185,129,0.75)', 'rgba(16,185,129,0.85)',
      'rgba(16,185,129,0.90)',
    ];
    Graficos.bar('chart-sim-hist', {
      labels,
      datasets: [{
        label: 'Índice de Internações (base 100)',
        data: internacoes,
        backgroundColor: cores,
        borderRadius: 4,
      }],
    }, { xLabel: 'Faixa de Temperatura (°C)', yLabel: 'Índice (base 100)' });
  }

  function _atualizarLinhaHistograma(temp) {
    // Anotação visual simples via plugin do Chart.js não disponível aqui;
    // a linha é indicada pelo badge da faixa ativa na UI.
    const badge = document.getElementById('sim-faixa-badge');
    if (!badge) return;
    const faixa = _getFaixa(temp);
    badge.textContent = faixa.nivel;
    badge.style.background = faixa.bgCor;
    badge.style.color = faixa.cor;
    badge.style.borderColor = faixa.borderCor;
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------
  return { atualizar, renderHistograma };

})();

window.Simulador = Simulador;
