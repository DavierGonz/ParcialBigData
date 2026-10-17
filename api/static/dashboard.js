/* Atlas vial: read-only, bounded visualization of the existing Flask contracts. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const format = new Intl.NumberFormat('es-CO');
  const number = value => Number.isFinite(Number(value)) ? format.format(Number(value)) : '—';
  const coord = value => Number(value).toFixed(5);
  const text = (tag, value, className) => {
    const element = document.createElement(tag);
    element.textContent = String(value ?? 'No disponible');
    if (className) element.className = className;
    return element;
  };
  const state = {results: [], queryMeta: null, markers: [], requestId: 0, controller: null};
  const severityColors = {1: '#688cbe', 2: '#2b9787', 3: '#e5a34a', 4: '#d36363'};
  const map = L.map('map', {zoomControl: false, worldCopyJump: true, minZoom: 2, maxZoom: 18}).setView([38.7, -97.5], 4);
  L.control.zoom({position: 'topright', zoomInTitle: 'Acercar', zoomOutTitle: 'Alejar'}).addTo(map);
  L.control.scale({position: 'bottomright', imperial: false}).addTo(map);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    updateWhenIdle: true, keepBuffer: 1,
  }).addTo(map);
  tiles.on('tileerror', () => { $('tile-message').hidden = false; });
  tiles.on('tileload', () => { $('tile-message').hidden = true; });
  const accidentGroup = L.featureGroup().addTo(map);
  const selectionGroup = L.featureGroup().addTo(map);
  let radiusLayer = null;

  function message(value, type = '') {
    $('query-message').textContent = value;
    $('query-message').className = `message ${type}`;
  }
  function emptyState(title, description) {
    const node = text('div', '', 'empty-state');
    node.append(text('span', '⌖'), text('h3', title), text('p', description));
    return node;
  }
  function errorMessage(error) {
    if (error.name === 'TimeoutError') return 'La consulta tardó demasiado. Intenta con un radio menor.';
    if (error.name === 'TypeError') return 'No fue posible conectar con la API. Verifica que Flask está disponible e inténtalo de nuevo.';
    return ({400: 'Revisa las coordenadas, el radio y el límite de resultados.',
      503: 'Los datos no están disponibles. Comprueba la conexión con MongoDB e inténtalo de nuevo.',
      504: 'La consulta superó el tiempo permitido. Reduce el radio e inténtalo de nuevo.'})[error.status] || error.message || 'No fue posible completar la consulta.';
  }
  async function api(path, options = {}, externalSignal) {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) controller.abort();
      externalSignal.addEventListener('abort', abort, {once: true});
    }
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 12000);
    try {
      const response = await fetch(path, {...options, signal: controller.signal, headers: {'Accept': 'application/json', ...options.headers}});
      if (!response.ok) {
        const error = new Error('No fue posible completar la consulta.');
        error.status = response.status;
        throw error;
      }
      return await response.json();
    } catch (error) {
      if (timedOut) throw Object.assign(new Error('Tiempo de espera agotado.'), {name: 'TimeoutError'});
      throw error;
    } finally {
      clearTimeout(timer);
      if (externalSignal) externalSignal.removeEventListener('abort', abort);
    }
  }
  function cancelQuery() {
    ++state.requestId;
    if (state.controller) state.controller.abort();
    state.controller = null;
    $('search-button').disabled = false;
    $('search-button').textContent = '⌕ Buscar accidentes';
    $('results-list').removeAttribute('aria-busy');
  }
  function clearResults() {
    cancelQuery(); state.results = []; state.queryMeta = null; state.markers = [];
    accidentGroup.clearLayers(); $('result-count').textContent = '—'; renderResults();
  }
  function coordinateValues() {
    const lat = Number($('latitude').value), lon = Number($('longitude').value);
    if (!$('latitude').value.trim() || !$('longitude').value.trim() || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      throw new Error('Ingresa una latitud entre -90 y 90 y una longitud entre -180 y 180.');
    }
    return [lat, lon];
  }
  function radiusValue() {
    const radius = Number($('radius').value);
    if (!$('radius').value.trim() || !Number.isFinite(radius) || radius < 1 || radius > 50000) throw new Error('El radio debe estar entre 1 y 50.000 metros.');
    return radius;
  }
  function showPoint(lat, lon) {
    const radius = radiusValue();
    selectionGroup.clearLayers();
    radiusLayer = L.circle([lat, lon], {radius, color: '#117b66', weight: 1.5, fillColor: '#65b596', fillOpacity: .09, interactive: false}).addTo(selectionGroup);
    L.circleMarker([lat, lon], {radius: 10, color: '#117b66', weight: 2, fill: false, interactive: false}).addTo(selectionGroup);
    $('map-subtitle').textContent = `Centro ${coord(lat)}, ${coord(lon)} · radio ${number(radius)} m`;
  }
  function fitSelection() {
    if (!radiusLayer) return;
    const bounds = radiusLayer.getBounds();
    if (bounds.isValid() && [bounds.getSouth(), bounds.getNorth(), bounds.getEast(), bounds.getWest()].every(Number.isFinite)) {
      map.fitBounds(bounds.pad(.16), {maxZoom: 15});
    }
  }
  function updateSelection(focus = false) {
    try {
      showPoint(...coordinateValues());
      if (focus) fitSelection();
      message('Punto y radio listos. Pulsa Buscar accidentes.');
      return true;
    } catch (_) {
      selectionGroup.clearLayers(); radiusLayer = null;
      $('map-subtitle').textContent = 'Estados Unidos · selecciona el centro de búsqueda';
      message('Completa coordenadas válidas y un radio entre 1 y 50.000 metros.');
      return false;
    }
  }
  map.on('click', event => {
    const lat = Math.max(-90, Math.min(90, event.latlng.lat));
    const lon = ((event.latlng.lng + 180) % 360 + 360) % 360 - 180;
    $('latitude').value = lat.toFixed(6); $('longitude').value = lon.toFixed(6);
    clearResults();
    if (updateSelection(true)) message(`Punto seleccionado: ${coord(lat)}, ${coord(lon)}. Ajusta el radio y pulsa Buscar accidentes.`);
  });
  for (const id of ['latitude', 'longitude', 'radius']) {
    $(id).addEventListener('input', () => {
      if (id === 'radius') $('radius-slider').value = $('radius').value;
      clearResults(); updateSelection();
    });
    $(id).addEventListener('change', () => { clearResults(); updateSelection(true); });
  }
  $('radius-slider').addEventListener('input', () => {
    $('radius').value = $('radius-slider').value;
    clearResults(); updateSelection();
  });
  $('radius-slider').addEventListener('change', () => updateSelection(true));
  $('limit').addEventListener('change', () => { clearResults(); message('Límite actualizado. Pulsa Buscar accidentes.'); });
  $('query-form').addEventListener('invalid', () => message('Revisa las coordenadas y el radio (de 1 a 50.000 metros).', 'error'), true);
  function popup(title, fields) {
    const node = text('div', '', 'popup-content');
    node.append(text('h3', title));
    const dl = document.createElement('dl');
    fields.forEach(([label, value]) => dl.append(text('dt', label), text('dd', value)));
    node.append(dl);
    return node;
  }
  function distance(row) {
    return Number.isFinite(row.distance_m) ? `${number(Math.round(row.distance_m))} m` : null;
  }
  function accidentPopup(row) {
    const fields = [['Ciudad', row.City || 'No disponible'], ['Estado', row.State || 'No disponible'], ['Severidad', row.Severity ?? 'No disponible'], ['Fecha civil', row.Start_Time || 'No disponible']];
    if (distance(row)) fields.push(['Distancia', distance(row)]);
    const [lon, lat] = row.location.coordinates;
    fields.push(['Latitud', coord(lat)], ['Longitud', coord(lon)]);
    return popup(row.ID || 'Accidente', fields);
  }
  function highlightResult(index, scroll = false) {
    [...$('results-list').children].forEach((node, i) => {
      node.classList.toggle('active', index === i);
      if (node.tagName === 'BUTTON') node.setAttribute('aria-pressed', String(index === i));
    });
    if (scroll) $('results-list').children[index]?.scrollIntoView({block: 'nearest', inline: 'nearest'});
  }
  function drawAccidents() {
    accidentGroup.clearLayers();
    state.markers = state.results.map((row, index) => {
      const point = row.location?.coordinates;
      if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)) return null;
      const marker = L.circleMarker([point[1], point[0]], {
        radius: 6, color: '#fff', weight: 1.5, fillColor: severityColors[row.Severity] || '#758d81',
        fillOpacity: .93, bubblingMouseEvents: false,
      }).bindPopup(accidentPopup(row)).addTo(accidentGroup);
      marker.on('click', () => highlightResult(index, true));
      return marker;
    });
    fitSelection();
  }
  function renderResults() {
    const list = $('results-list'); list.replaceChildren();
    $('results-note').textContent = state.queryMeta ? (state.queryMeta.has_more ? 'Hay más coincidencias que el límite elegido.' : 'Todos los resultados de esta consulta.') : 'Los resultados aparecerán aquí al consultar.';
    $('fit-results').disabled = state.results.length === 0;
    if (!state.results.length) {
      list.append(emptyState(state.queryMeta ? 'Sin accidentes en este radio' : 'Elige dónde explorar', state.queryMeta ? 'Prueba otra ubicación o amplía el radio.' : 'Selecciona un punto, ajusta el radio y pulsa Buscar accidentes.'));
      return;
    }
    state.results.forEach((row, index) => {
      const button = text('button', '', 'result-card'); button.type = 'button'; button.setAttribute('aria-pressed', 'false');
      const top = text('div', '', 'result-card-top');
      top.append(text('span', row.ID, 'result-id'), text('span', `Severidad ${row.Severity ?? '—'}`, 'severity-chip'));
      const bottom = text('div', '', 'result-card-bottom');
      bottom.append(text('span', row.Start_Time ? row.Start_Time.slice(0, 16) : 'Fecha no disponible'), text('span', distance(row) || 'Ver en mapa ↗', 'distance'));
      button.append(top, text('div', [row.City, row.State].filter(Boolean).join(', ') || 'Ubicación no disponible', 'result-place'), bottom);
      button.addEventListener('click', () => {
        const marker = state.markers[index];
        if (!marker) return;
        map.setView(marker.getLatLng(), Math.max(map.getZoom(), 14)); marker.openPopup(); highlightResult(index);
      });
      list.append(button);
    });
  }
  async function search(event) {
    event.preventDefault();
    let lat, lon, radius, limit;
    try {
      [lat, lon] = coordinateValues(); radius = radiusValue(); limit = Number($('limit').value);
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('El límite debe ser un entero entre 1 y 100.');
    } catch (error) { message(error.message, 'error'); return; }
    clearResults(); showPoint(lat, lon); fitSelection();
    const id = ++state.requestId; state.controller = new AbortController();
    $('search-button').disabled = true; $('search-button').textContent = 'Consultando…';
    $('results-list').setAttribute('aria-busy', 'true');
    message('Buscando accidentes en el radio seleccionado…', 'loading');
    try {
      const data = await api('/accidents/geo-near?' + new URLSearchParams({lat, lon, radius_m: radius, limit}), {}, state.controller.signal);
      if (id !== state.requestId) return;
      state.results = data.items; state.queryMeta = data;
      $('result-count').textContent = number(data.count);
      drawAccidents(); renderResults();
      message(data.count ? `${number(data.count)} accidentes encontrados. ${data.has_more ? 'Se alcanzó el límite: existen más coincidencias.' : 'Se muestran todas las coincidencias de esta consulta.'}` : 'No se encontraron accidentes. Prueba otro punto o amplía el radio.');
    } catch (error) {
      if (id !== state.requestId || error.name === 'AbortError') return;
      message(errorMessage(error), 'error');
      $('results-list').replaceChildren(emptyState('No pudimos completar la búsqueda', 'Revisa el mensaje de los filtros e inténtalo de nuevo.'));
    } finally {
      if (id === state.requestId) {
        $('search-button').disabled = false; $('search-button').textContent = '⌕ Buscar accidentes';
        $('results-list').removeAttribute('aria-busy');
      }
    }
  }
  $('query-form').addEventListener('submit', search);
  $('fit-results').addEventListener('click', fitSelection);
  $('overview-button').addEventListener('click', () => map.setView([38.7, -97.5], 4));
  map.on('popupopen', event => {
    const close = event.popup.getElement()?.querySelector('.leaflet-popup-close-button');
    if (close) { close.setAttribute('aria-label', 'Cerrar detalle'); close.title = 'Cerrar detalle'; }
  });
  fetch('/static/us-outline.geojson').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(data => {
    L.geoJSON(data, {style: {color: '#a5b59c', weight: 1, fillColor: '#dfe8d6', fillOpacity: .15}, interactive: false}).addTo(map).bringToBack();
  }).catch(() => { /* Tile map and queries remain usable if the optional outline fails. */ });
  api('/health').then(data => {
    if (data.status !== 'ok') throw new Error();
    $('service-status').textContent = 'API disponible';
  }).catch(() => { $('service-status').textContent = 'API no disponible'; $('service-dot').classList.add('error'); });
  new ResizeObserver(() => map.invalidateSize()).observe($('map'));
})();
