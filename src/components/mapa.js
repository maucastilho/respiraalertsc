/**
 * mapa.js
 * Renderização do mapa de Santa Catarina via Canvas 2D + GeoJSON.
 * Suporta camadas: vulnerabilidade, risco, correlação, internações.
 * Clique no município abre painel lateral de detalhes.
 */

const Mapa = (() => {

  let _geojson = null;
  let _indicadores = {};     // ibge → dados do município
  let _variavel = 'vulnerabilidade';
  let _onSelect = null;      // callback(municipio_ibge)
  let _canvas = null;
  let _ctx = null;
  let _projecao = null;      // { minLon, maxLon, minLat, maxLat, scaleX, scaleY, offsetX, offsetY }
  let _features = [];        // cache de features com pixels pré-calculados
  let _hoverIbge = null;

  // ----------------------------------------------------------------
  // Cores por variável
  // ----------------------------------------------------------------
  const CORES_VULNER = {
    'Baixa':     '#10b981',
    'Moderada':  '#f59e0b',
    'Alta':      '#ef4444',
    'Muito Alta':'#8b5cf6',
  };
  const CORES_RISCO = {
    'Baixo':     '#10b981',
    'Moderado':  '#f59e0b',
    'Alto':      '#ef4444',
    'Muito Alto':'#8b5cf6',
  };

  function _corMunicipio(ibge) {
    const m = _indicadores[ibge];
    if (!m) return 'rgba(30,50,80,0.6)';

    switch (_variavel) {
      case 'vulnerabilidade': return CORES_VULNER[m.vulnerabilidade] || '#4a6080';
      case 'risco':           return CORES_RISCO[m.risco || m.classificacao_risco] || '#4a6080';
      case 'correlacao': {
        const c = parseFloat(m.correlacao);
        // de azul (correlação próxima de 0) a vermelho (−1)
        const t = Math.min(1, Math.abs(c));
        return `rgba(${Math.round(239*t)},${Math.round(68*t + 130*(1-t))},${Math.round(68*t + 246*(1-t))},0.8)`;
      }
      case 'internacoes': {
        const vals = Object.values(_indicadores).map(x => x.total_internacoes || 0);
        const max  = Math.max(...vals) || 1;
        const t    = Math.min(1, (m.total_internacoes || 0) / max);
        return `rgba(${Math.round(239*t + 0*(1-t))},${Math.round(68*t + 194*(1-t))},${Math.round(68*t + 255*(1-t))},0.8)`;
      }
      default: return '#4a6080';
    }
  }

  // ----------------------------------------------------------------
  // Projeção lon/lat → pixels
  // ----------------------------------------------------------------
  function _calcularProjecao(features, W, H) {
    let minLon=999, maxLon=-999, minLat=999, maxLat=-999;
    features.forEach(f => {
      const coords = f.geometry.type === 'Polygon'
        ? f.geometry.coordinates[0]
        : f.geometry.coordinates.flat(2);
      coords.forEach(([lon, lat]) => {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      });
    });

    const pad = 24;
    const scaleX = (W - pad*2) / (maxLon - minLon);
    const scaleY = (H - pad*2) / (maxLat - minLat);
    const scale  = Math.min(scaleX, scaleY);

    return {
      minLon, maxLon, minLat, maxLat,
      scale,
      offsetX: pad + (W - pad*2 - (maxLon - minLon) * scale) / 2,
      offsetY: pad + (H - pad*2 - (maxLat - minLat) * scale) / 2,
    };
  }

  function _lonLatParaPx(lon, lat, proj) {
    return [
      proj.offsetX + (lon - proj.minLon) * proj.scale,
      proj.offsetY + (proj.maxLat - lat) * proj.scale,  // invertido Y
    ];
  }

  // ----------------------------------------------------------------
  // Pré-calcular pixels de cada feature
  // ----------------------------------------------------------------
  function _processarFeatures(geojson, proj) {
    return geojson.features.map(f => {
      const rings = f.geometry.type === 'Polygon'
        ? f.geometry.coordinates
        : f.geometry.coordinates[0]; // MultiPolygon simples

      const pixelRings = rings.map(ring =>
        ring.map(([lon, lat]) => _lonLatParaPx(lon, lat, proj))
      );

      // Centróide para tooltip
      const all = rings[0];
      const cx = all.reduce((s,[lon])=>s+lon,0)/all.length;
      const cy = all.reduce((s,[,lat])=>s+lat,0)/all.length;
      const [px, py] = _lonLatParaPx(cx, cy, proj);

      return {
        ibge:       f.properties.ibge,
        nome:       f.properties.nome,
        pixelRings,
        centroide:  [px, py],
      };
    });
  }

  // ----------------------------------------------------------------
  // Desenho principal
  // ----------------------------------------------------------------
  function _desenhar() {
    if (!_ctx || !_features.length) return;
    const W = _canvas.width, H = _canvas.height;
    _ctx.clearRect(0, 0, W, H);

    _features.forEach(f => {
      const cor = _corMunicipio(f.ibge);
      const hover = f.ibge === _hoverIbge;

      f.pixelRings.forEach(ring => {
        _ctx.beginPath();
        ring.forEach(([x, y], i) => i === 0 ? _ctx.moveTo(x, y) : _ctx.lineTo(x, y));
        _ctx.closePath();
        _ctx.fillStyle = hover ? cor.replace(',0.8)', ',1)').replace(')',',' + '1)') : cor;
        _ctx.fill();
        _ctx.strokeStyle = hover ? 'rgba(0,194,255,0.9)' : 'rgba(0,194,255,0.2)';
        _ctx.lineWidth   = hover ? 1.5 : 0.5;
        _ctx.stroke();
      });

      // Nome do município (apenas em hover ou municípios maiores)
      if (hover) {
        const [cx, cy] = f.centroide;
        _ctx.font = 'bold 11px Inter, sans-serif';
        _ctx.fillStyle = '#ffffff';
        _ctx.textAlign = 'center';
        _ctx.fillText(f.nome, cx, cy);
      }
    });
  }

  // ----------------------------------------------------------------
  // Hit-test (ponto dentro de polígono)
  // ----------------------------------------------------------------
  function _pointInPolygon(px, py, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
    }
    return inside;
  }

  function _featureNoPonto(px, py) {
    for (let i = _features.length - 1; i >= 0; i--) {
      const f = _features[i];
      if (f.pixelRings.some(ring => _pointInPolygon(px, py, ring))) return f;
    }
    return null;
  }

  // ----------------------------------------------------------------
  // Eventos do canvas
  // ----------------------------------------------------------------
  function _bindEventos() {
    _canvas.addEventListener('mousemove', e => {
      const rect = _canvas.getBoundingClientRect();
      const scaleX = _canvas.width / rect.width;
      const scaleY = _canvas.height / rect.height;
      const px = (e.clientX - rect.left) * scaleX;
      const py = (e.clientY - rect.top)  * scaleY;
      const f = _featureNoPonto(px, py);
      const novoHover = f ? f.ibge : null;
      if (novoHover !== _hoverIbge) {
        _hoverIbge = novoHover;
        _canvas.style.cursor = novoHover ? 'pointer' : 'default';
        _desenhar();
        _mostrarTooltip(e, f);
      }
    });

    _canvas.addEventListener('mouseleave', () => {
      _hoverIbge = null;
      _canvas.style.cursor = 'default';
      _desenhar();
      _esconderTooltip();
    });

    _canvas.addEventListener('click', e => {
      const rect = _canvas.getBoundingClientRect();
      const scaleX = _canvas.width / rect.width;
      const scaleY = _canvas.height / rect.height;
      const px = (e.clientX - rect.left) * scaleX;
      const py = (e.clientY - rect.top)  * scaleY;
      const f = _featureNoPonto(px, py);
      if (f && _onSelect) _onSelect(f.ibge, f.nome);
    });
  }

  // ----------------------------------------------------------------
  // Tooltip flutuante
  // ----------------------------------------------------------------
  function _mostrarTooltip(e, feature) {
    let tip = document.getElementById('mapa-tooltip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'mapa-tooltip';
      tip.className = 'map-tooltip';
      document.body.appendChild(tip);
    }
    if (!feature) { tip.style.display = 'none'; return; }

    const m = _indicadores[feature.ibge];
    tip.innerHTML = `
      <div style="font-weight:700;color:var(--text-primary);margin-bottom:6px">${feature.nome}</div>
      ${m ? `
        <div class="mtt">Internações</div><div class="mtv">${Number(m.total_internacoes).toLocaleString('pt-BR')}</div>
        <div class="mtt">Temp. média</div><div class="mtv">${m.temp_media}°C</div>
        <div class="mtt">Correlação</div><div class="mtv">${m.correlacao}</div>
        <div class="mtt">Vulnerabilidade</div><div class="mtv">${m.vulnerabilidade}</div>
      ` : '<div style="color:var(--text-muted)">Sem dados</div>'}
    `;
    tip.style.display = 'block';
    tip.style.left = (e.pageX + 14) + 'px';
    tip.style.top  = (e.pageY - 10) + 'px';
  }

  function _esconderTooltip() {
    const tip = document.getElementById('mapa-tooltip');
    if (tip) tip.style.display = 'none';
  }

  // ----------------------------------------------------------------
  // API pública
  // ----------------------------------------------------------------

  /**
   * Inicializa o mapa.
   * @param {string} canvasId - ID do elemento <canvas>
   * @param {object} geojson  - GeoJSON FeatureCollection dos municípios
   * @param {Array}  municipios - Array de indicadores municipais
   * @param {Function} onSelect - callback(ibge, nome) ao clicar num município
   */
  function inicializar(canvasId, geojson, municipios, onSelect) {
    _canvas = document.getElementById(canvasId);
    if (!_canvas) { console.warn('Canvas do mapa não encontrado:', canvasId); return; }
    _ctx = _canvas.getContext('2d');
    _geojson = geojson;
    _onSelect = onSelect;

    // Indexar indicadores por IBGE
    _indicadores = {};
    municipios.forEach(m => { _indicadores[m.ibge || m.municipio_ibge] = m; });

    // Ajustar resolução do canvas ao container
    const container = _canvas.parentElement;
    _canvas.width  = container.clientWidth  || 700;
    _canvas.height = container.clientHeight || 480;

    _projecao  = _calcularProjecao(geojson.features, _canvas.width, _canvas.height);
    _features  = _processarFeatures(geojson, _projecao);

    _bindEventos();
    _desenhar();
  }

  function setVariavel(variavel) {
    _variavel = variavel;
    _desenhar();
  }

  function exportarPNG() {
    if (!_canvas) return;
    const a = document.createElement('a');
    a.href = _canvas.toDataURL('image/png');
    a.download = 'respiralert_mapa_sc.png';
    a.click();
  }

  return { inicializar, setVariavel, exportarPNG };

})();

window.Mapa = Mapa;
