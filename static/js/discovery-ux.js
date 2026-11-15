(() => {
  // Native history keeps the exact scroll and selection on a true N2 return.
  // Deep links keep their safe server-generated href instead.
  const returnLink = document.querySelector('[data-discovery-return]');
  if (returnLink) {
    returnLink.addEventListener('click', (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey ||
          event.shiftKey || event.altKey || window.history.length < 2 ||
          !document.referrer) return;
      const destination = new URL(returnLink.href, window.location.href);
      const previous = new URL(document.referrer, window.location.href);
      if (destination.origin !== previous.origin ||
          destination.pathname !== previous.pathname ||
          destination.search !== previous.search) return;
      event.preventDefault();
      window.history.back();
    });
  }

  const form = document.getElementById('discovery-search-form');
  const latitude = document.getElementById('discover-lat');
  const longitude = document.getElementById('discover-lon');
  const query = document.getElementById('discover-query');

  const params = new URLSearchParams(window.location.search);
  const expandedFilters = form?.querySelector('.mk-discovery-filters');
  const searchContext = document.querySelector('.mk-discovery-workspace[data-discovery-context="search"]');
  if (expandedFilters && searchContext && window.matchMedia('(min-width: 1200px)').matches) expandedFilters.open = true;

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

  }

  // In-place previews reuse text and links already visible in the owner-backed card.
  // Never fetch a detail or introduce another authorization path.
  const previewPanel = document.getElementById('discover-preview-wrapper');
  const previewBody = document.getElementById('discover-preview-body');
  if (previewPanel && previewBody) {
    document.querySelectorAll('[data-discovery-preview-open]').forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('article[data-discovery-result]');
        const detailLink = card?.querySelector('h3 a[href]');
        if (!detailLink) return;
        const title = document.createElement('h3');
        title.className = 'break-words text-lg font-bold';
        title.textContent = detailLink.textContent.trim();
        const link = document.createElement('a');
        link.className = 'mk-action-button mt-3';
        link.dataset.variant = 'secondary';
        link.href = detailLink.href;
        link.textContent = 'Voir le détail';
        previewBody.replaceChildren(title, link);
        previewPanel.classList.remove('hidden');
        if (!window.matchMedia('(min-width: 1024px)').matches) {
          previewPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    });
  }

  // Only reflect which view is selected; the map controller keeps owning
  // list/map visibility, camera and selection.
  const listControl = document.getElementById('discovery-show-list');
  const mapControl = document.getElementById('discovery-show-map');
  if (listControl && mapControl) {
    const activeView = (view) => {
      listControl.dataset.variant = view === 'list' ? 'secondary' : 'ghost';
      mapControl.dataset.variant = view === 'map' ? 'secondary' : 'ghost';
    };
    listControl.addEventListener('click', () => activeView('list'));
    mapControl.addEventListener('click', () => activeView('map'));
  }

  const map = window.__makoloDiscoveryMap;
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

  if (!map || typeof map.on !== 'function') {
    // The deployed bundle may decline initialization: keep the list.
    if (document.getElementById('discovery-map')) failGracefully();
    return;
  }
  map.on('error', () => {
    // Raster tile errors after initialization may recover.
    if (typeof map.getSource === 'function' &&
        map.getSource('discovery-results')) return;
    failGracefully();
  });
})();
