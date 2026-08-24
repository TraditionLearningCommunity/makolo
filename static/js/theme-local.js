(() => {
  const selector = document.getElementById('public-theme-preference');
  if (!selector) return;
  const valid = new Set(['system', 'light', 'dark']);

  let current = 'system';
  try {
    const stored = window.localStorage.getItem('theme');
    if (valid.has(stored)) current = stored;
  } catch (_error) {
    // Browser storage is optional.
  }
  selector.value = current;

  selector.addEventListener('change', () => {
    const value = valid.has(selector.value) ? selector.value : 'system';
    try {
      if (value === 'system') window.localStorage.removeItem('theme');
      else window.localStorage.setItem('theme', value);
    } catch (_error) {
      // Keep the UI usable even when storage is unavailable.
    }
    window.location.reload();
  });
})();
