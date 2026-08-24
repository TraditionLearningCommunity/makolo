(() => {
  const form = document.getElementById('discovery-search-form');
  const latitude = document.getElementById('discover-lat');
  const longitude = document.getElementById('discover-lon');

  if (form) {
    form.addEventListener('submit', () => {
      [latitude, longitude].forEach((field) => {
        if (!field || !field.value) return;
        const value = Number(field.value);
        if (Number.isFinite(value)) field.value = value.toFixed(4);
      });
    });
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
