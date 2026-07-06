/**
 * graficos.js
 * Wrapper centralizado para Chart.js com tema RespirAlert SC.
 * Exportação PNG e PDF via html2canvas / jsPDF.
 */

const Graficos = (() => {

  const _instancias = {};

  // ----------------------------------------------------------------
  // Tema base
  // ----------------------------------------------------------------
  const GRID_COLOR   = 'rgba(0,194,255,0.06)';
  const TICK_COLOR   = '#4a6080';
  const TOOLTIP_BG   = 'rgba(13,21,39,0.95)';
  const LEGEND_COLOR = '#8bacc8';

  function _baseOpts({ xLabel = '', yLabel = '', dual = false } = {}) {
    const axis = (label) => ({
      grid: { color: GRID_COLOR },
      ticks: { color: TICK_COLOR, font: { size: 11 } },
      title: label ? { display: true, text: label, color: TICK_COLOR, font: { size: 11 } } : { display: false },
    });

    const opts = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        zoom: {
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
          pan:  { enabled: true, mode: 'x' },
        },
        tooltip: {
          backgroundColor: TOOLTIP_BG,
          borderColor: 'rgba(0,194,255,0.3)',
          borderWidth: 1,
          titleColor: '#e8f4fd',
          bodyColor: '#8bacc8',
          padding: 10,
        },
      },
      scales: {
        x: axis(xLabel),
        y: axis(yLabel),
      },
    };

    if (dual) {
      opts.scales.y2 = {
        position: 'right',
        grid: { display: false },
        ticks: { color: TICK_COLOR, font: { size: 11 } },
        title: { display: true, text: 'Temperatura (°C)', color: TICK_COLOR, font: { size: 11 } },
      };
    }

    return opts;
  }

  function _render(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    if (_instancias[id]) { _instancias[id].destroy(); }
    _instancias[id] = new Chart(canvas, config);
    return _instancias[id];
  }

  // ----------------------------------------------------------------
  // Tipos de gráfico
  // ----------------------------------------------------------------

  function bar(id, data, opts = {}) {
    return _render(id, {
      type: 'bar',
      data,
      options: { ..._baseOpts(opts), ...opts.extra },
    });
  }

  function line(id, data, opts = {}) {
    return _render(id, {
      type: 'line',
      data,
      options: { ..._baseOpts(opts), ...opts.extra },
    });
  }

  function dual(id, { labels, series1, series2 }, opts = {}) {
    return _render(id, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: series1.label,
            data: series1.data,
            borderColor: series1.color,
            backgroundColor: series1.color.replace(')', ',0.1)').replace('rgb', 'rgba'),
            tension: 0.4,
            fill: true,
            yAxisID: 'y',
          },
          {
            label: series2.label,
            data: series2.data,
            borderColor: series2.color,
            backgroundColor: 'transparent',
            tension: 0.4,
            borderDash: [5, 3],
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        ..._baseOpts({ dual: true }),
        plugins: {
          legend: {
            display: true,
            labels: { color: LEGEND_COLOR, font: { size: 11 } },
          },
          tooltip: {
            backgroundColor: TOOLTIP_BG,
            borderColor: 'rgba(0,194,255,0.3)',
            borderWidth: 1,
            titleColor: '#e8f4fd',
            bodyColor: '#8bacc8',
            padding: 10,
          },
        },
      },
    });
  }

  function scatter(id, pontos) {
    return _render(id, {
      type: 'scatter',
      data: {
        datasets: [{
          label: 'Municípios',
          data: pontos.map(p => ({ x: p.x, y: p.y })),
          backgroundColor: 'rgba(0,194,255,0.65)',
          pointRadius: 6,
          pointHoverRadius: 9,
        }],
      },
      options: {
        ..._baseOpts({ xLabel: 'Temperatura Média (°C)', yLabel: 'Total Internações' }),
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: TOOLTIP_BG,
            borderColor: 'rgba(0,194,255,0.3)',
            borderWidth: 1,
            titleColor: '#e8f4fd',
            bodyColor: '#8bacc8',
            padding: 10,
            callbacks: {
              label: (ctx) => {
                const p = pontos[ctx.dataIndex];
                return p ? `${p.nome}: ${p.x}°C / ${Number(p.y).toLocaleString('pt-BR')} intern.` : '';
              },
            },
          },
        },
      },
    });
  }

  function doughnut(id, { labels, data, colors }) {
    return _render(id, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors,
          borderColor: 'rgba(0,0,0,0.3)',
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: LEGEND_COLOR, font: { size: 11 }, padding: 8 },
          },
        },
      },
    });
  }

  // ----------------------------------------------------------------
  // Exportação PNG
  // ----------------------------------------------------------------
  function exportarPNG(id, nomeArquivo) {
    const canvas = document.getElementById(id);
    if (!canvas) { alert('Gráfico não encontrado.'); return; }
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = (nomeArquivo || id) + '.png';
    a.click();
  }

  // ----------------------------------------------------------------
  // Exportação PDF (via html2canvas + jsPDF inline)
  // ----------------------------------------------------------------
  async function exportarPDF(containerIdOuIds, nomeArquivo = 'respiralert_sc') {
    // Carrega jsPDF dinamicamente se ainda não estiver disponível
    if (!window.jspdf) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    if (!window.html2canvas) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const ids = Array.isArray(containerIdOuIds) ? containerIdOuIds : [containerIdOuIds];
    const W = 297, H = 210; // A4 landscape mm

    for (let i = 0; i < ids.length; i++) {
      const el = document.getElementById(ids[i]);
      if (!el) continue;
      if (i > 0) pdf.addPage();
      const canvas = await html2canvas(el, { backgroundColor: '#080e1c', scale: 2 });
      const imgData = canvas.toDataURL('image/png');
      const ratio = canvas.width / canvas.height;
      let w = W - 20, h = w / ratio;
      if (h > H - 20) { h = H - 20; w = h * ratio; }
      pdf.addImage(imgData, 'PNG', (W - w) / 2, 10, w, h);
    }

    pdf.save(nomeArquivo + '.pdf');
  }

  // ----------------------------------------------------------------
  // Utilitários
  // ----------------------------------------------------------------
  function destruir(id) {
    if (_instancias[id]) { _instancias[id].destroy(); delete _instancias[id]; }
  }

  function destruirTodos() {
    Object.keys(_instancias).forEach(destruir);
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------
  return { bar, line, dual, scatter, doughnut, exportarPNG, exportarPDF, destruir, destruirTodos };

})();

window.Graficos = Graficos;
