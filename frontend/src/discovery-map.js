import * as maplibregl from 'maplibre-gl';

function parseJson(id, fallback) {
  const node = document.getElementById(id);
  if (!node) return fallback;
  try { return JSON.parse(node.textContent || ''); } catch (_error) { return fallback; }
}

function setupGeolocation() {
  const button = document.getElementById('discover-near-me');
  if (!button) return;
  const status = document.getElementById('discover-geolocation-status');
  button.addEventListener('click', () => {
    if (!navigator.geolocation) {
      if (status) status.textContent = 'Localisation indisponible. Recherchez un lieu manuellement.';
      return;
    }
    button.disabled = true;
    if (status) status.textContent = 'Localisation en cours…';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        document.getElementById('discover-lat').value = position.coords.latitude.toFixed(6);
        document.getElementById('discover-lon').value = position.coords.longitude.toFixed(6);
        if (status) status.textContent = 'Position utilisée uniquement pour cette recherche.';
        document.getElementById('discovery-search-form').requestSubmit();
      },
      () => {
        button.disabled = false;
        if (status) status.textContent = 'Localisation refusée. Vous pouvez saisir un lieu.';
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 },
    );
  });
}

function setupMobileToggle() {
  const listButton = document.getElementById('discovery-show-list');
  const mapButton = document.getElementById('discovery-show-map');
  const listPanel = document.getElementById('discovery-list-panel');
  const mapPanel = document.getElementById('discovery-map-panel');
  if (!listButton || !mapButton || !listPanel || !mapPanel) return;
  const show = (mode) => {
    const mapMode = mode === 'map';
    listPanel.classList.toggle('hidden', mapMode);
    mapPanel.classList.toggle('hidden', !mapMode);
    mapPanel.classList.toggle('block', mapMode);
    listButton.setAttribute('aria-pressed', String(!mapMode));
    mapButton.setAttribute('aria-pressed', String(mapMode));
    if (mapMode && window.__makoloDiscoveryMap) window.__makoloDiscoveryMap.resize();
  };
  listButton.addEventListener('click', () => show('list'));
  mapButton.addEventListener('click', () => show('map'));
}

function selectResult(id, map, coordinates) {
  document.querySelectorAll('[data-discovery-result]').forEach((node) => {
    const selected = node.dataset.discoveryResult === id;
    node.classList.toggle('ring-2', selected);
    node.classList.toggle('ring-indigo-500', selected);
  });
  const target = document.querySelector(`[data-discovery-result="${CSS.escape(id)}"]`);
  if (target && window.matchMedia('(min-width: 1024px)').matches) {
    target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
  if (coordinates) map.easeTo({ center: coordinates, zoom: Math.max(map.getZoom(), 12), duration: 500 });
}

function showMapFallback() {
  const fallback = document.getElementById('discovery-map-fallback');
  if (fallback) fallback.classList.remove('hidden');
}

function supportsWebGL2() {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2'));
  } catch (_error) {
    return false;
  }
}

function showFeaturePopup(map, feature, coordinates) {
  const content = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = feature.properties.title;
  const link = document.createElement('a');
  link.href = feature.properties.url;
  link.textContent = feature.properties.cta_label;
  link.className = 'block mt-2 font-semibold';
  content.append(title, link);
  new maplibregl.Popup({ closeButton: true }).setLngLat(coordinates).setDOMContent(content).addTo(map);
}

function addSingleResultMarker(map, feature) {
  const coordinates = feature.geometry.coordinates.slice();
  const marker = document.createElement('button');
  marker.type = 'button';
  marker.className = 'discovery-map-marker';
  marker.setAttribute('aria-label', feature.properties.title);
  marker.style.width = '20px';
  marker.style.height = '20px';
  marker.style.borderRadius = '9999px';
  marker.style.border = '3px solid #FAF7F5';
  marker.style.background = '#FF704D';
  marker.style.boxShadow = '0 2px 10px rgba(15, 23, 42, 0.25)';
  marker.style.cursor = 'pointer';
  marker.addEventListener('click', () => {
    selectResult(feature.properties.occurrence_id, map, coordinates);
    showFeaturePopup(map, feature, coordinates);
  });
  new maplibregl.Marker({ element: marker, anchor: 'center' }).setLngLat(coordinates).addTo(map);
}

function buildMap() {
  const container = document.getElementById('discovery-map');
  if (!container) return;
  const items = parseJson('discovery-map-data', []);
  const config = parseJson('discovery-map-config', {});
  if (!items.length || !config.tile_url) return;
  if (!supportsWebGL2()) {
    showMapFallback();
    return;
  }
  const features = items.map((item) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [item.place.longitude, item.place.latitude] },
    properties: {
      occurrence_id: item.occurrence_id,
      title: item.title,
      vertical: item.vertical,
      url: item.url,
      cta_label: item.cta_label,
    },
  }));
  try {
    const map = new maplibregl.Map({
      container,
      style: {
        version: 8,
        sources: {
          makoloTiles: {
            type: 'raster',
            tiles: [config.tile_url],
            tileSize: 256,
            maxzoom: config.max_zoom || 19,
            attribution: config.attribution || '',
          },
        },
        layers: [{ id: 'makolo-basemap', type: 'raster', source: 'makoloTiles' }],
      },
      center: features[0].geometry.coordinates,
      zoom: 11,
      attributionControl: true,
    });
    window.__makoloDiscoveryMap = map;
    map.on('error', showMapFallback);
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      const shouldCluster = features.length > 1;
      map.addSource('discovery-results', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features },
        cluster: shouldCluster,
        clusterRadius: 44,
        clusterMaxZoom: 13,
      });
      if (shouldCluster) {
        map.addLayer({ id: 'discovery-clusters', type: 'circle', source: 'discovery-results', filter: ['has', 'point_count'], paint: { 'circle-radius': ['step', ['get', 'point_count'], 18, 10, 24, 30, 30], 'circle-color': '#5232DB', 'circle-stroke-color': '#FAF7F5', 'circle-stroke-width': 2 } });
        map.addLayer({ id: 'discovery-cluster-count', type: 'symbol', source: 'discovery-results', filter: ['has', 'point_count'], layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 }, paint: { 'text-color': '#FAF7F5' } });
      }
      map.addLayer({ id: 'discovery-points', type: 'circle', source: 'discovery-results', filter: shouldCluster ? ['!', ['has', 'point_count']] : undefined, paint: { 'circle-radius': 8, 'circle-color': '#FF704D', 'circle-stroke-color': '#FAF7F5', 'circle-stroke-width': 2 } });
      if (features.length === 1) {
        addSingleResultMarker(map, features[0]);
      } else {
        const bounds = new maplibregl.LngLatBounds();
        features.forEach((feature) => bounds.extend(feature.geometry.coordinates));
        map.fitBounds(bounds, { padding: 55, maxZoom: 13, duration: 0 });
      }
    });
    map.on('click', 'discovery-points', (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const coords = feature.geometry.coordinates.slice();
      selectResult(feature.properties.occurrence_id, map, coords);
      showFeaturePopup(map, feature, coords);
    });
    map.on('click', 'discovery-clusters', async (event) => {
      const feature = event.features && event.features[0];
      if (!feature) return;
      const source = map.getSource('discovery-results');
      const zoom = await source.getClusterExpansionZoom(feature.properties.cluster_id);
      map.easeTo({ center: feature.geometry.coordinates, zoom });
    });
    ['discovery-points', 'discovery-clusters'].forEach((layer) => {
      map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
    });
    document.querySelectorAll('[data-discovery-result]').forEach((node) => {
      node.addEventListener('click', (event) => {
        if (event.target.closest('a,button')) return;
        const item = items.find((row) => row.occurrence_id === node.dataset.discoveryResult);
        if (item) selectResult(item.occurrence_id, map, [item.place.longitude, item.place.latitude]);
      });
    });
  } catch (_error) {
    showMapFallback();
  }
}

setupGeolocation();
setupMobileToggle();
buildMap();
