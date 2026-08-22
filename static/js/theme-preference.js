(() => {
  const root = document.documentElement;
  const valid = new Set(['system', 'light', 'dark']);
  const hasServerPreference = root.hasAttribute('data-theme-preference');
  const serverPreference = root.dataset.themePreference;

  function readStoredPreference() {
    try {
      const value = window.localStorage.getItem('theme');
      return valid.has(value) ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function cachePreference(value) {
    try {
      if (value === 'system') {
        window.localStorage.removeItem('theme');
      } else {
        window.localStorage.setItem('theme', value);
      }
    } catch (_error) {
      // Browser storage is an optional cache, never the account source of truth.
    }
  }

  const storedPreference = readStoredPreference();
  const preference = hasServerPreference
    ? (valid.has(serverPreference) ? serverPreference : 'system')
    : (storedPreference || 'system');

  if (hasServerPreference) cachePreference(preference);

  const media = window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;

  function applyTheme(systemDark = Boolean(media && media.matches)) {
    const dark = preference === 'dark' || (preference === 'system' && systemDark);
    root.classList.toggle('dark', dark);
    root.style.colorScheme = dark ? 'dark' : 'light';
    root.dataset.themePreference = preference;
  }

  applyTheme();

  if (preference === 'system' && media && media.addEventListener) {
    media.addEventListener('change', (event) => applyTheme(event.matches));
  }
})();
