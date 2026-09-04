(() => {
  const form = document.getElementById('discovery-search-form');
  const latitude = document.getElementById('discover-lat');
  const longitude = document.getElementById('discover-lon');
  const query = document.getElementById('discover-query');

  const params = new URLSearchParams(window.location.search);
  if (query && params.get('focus') === 'search') {
    window.requestAnimationFrame(() => query.focus({ preventScroll: false }));
  }

  if (form) {
    form.addEventListener('submit', () => {
      [latitude, longitude].forEach((field) => {
        if (!field || !field.value) return;
        const value = Number(field.value);
        if (Number.isFinite(value)) field.value = value.toFixed(4);
      });
    });

    const meaningfulKeys = ['q', 'place', 'city', 'when', 'period', 'vertical', 'price', 'lat', 'lon', 'date', 'date_from', 'date_to'];
    const hasCriteria = meaningfulKeys.some((key) => (params.get(key) || '').trim());
    const filterGrid = form.querySelector('details > div');
    if (hasCriteria && filterGrid) {
      const link = document.createElement('a');
      link.className = 'mk-btn mk-btn-secondary';
      link.href = `/discover/watches/new/?${params.toString()}`;
      link.textContent = 'Enregistrer comme veille';
      filterGrid.appendChild(link);
    }
  }

  const map = window.__makoloDiscoveryMap;
  if (!map || typeof map.on !== 'function') return;

  let failed = false;
  const failGracefully = () => {
    if (failed) return;
    failed = true;
    const container = document.getElementById('discovery-map');
    const fallback = document.getElementById('discovery-map-fallback');
    const mapButton = document.getElementById('discovery-show-map');
    const listButton = document.getElementById('discovery-show-list');

    if (container) container.classList.add('hidden');
    if (fallback) fallback.classList.remove('hidden');
    if (mapButton) {
      mapButton.disabled = true;
      mapButton.setAttribute('aria-disabled', 'true');
    }
    if (listButton && window.matchMedia('(max-width: 1023px)').matches) {
      listButton.click();
    }
  };

  map.on('error', failGracefully);
})();
