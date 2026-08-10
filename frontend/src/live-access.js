(() => {
  const root = document.querySelector('[data-auto-reload-ms]');
  if (!root) return;
  const delay = Number(root.dataset.autoReloadMs);
  if (Number.isFinite(delay) && delay > 0) {
    window.setTimeout(() => window.location.reload(), delay);
  }
})();
