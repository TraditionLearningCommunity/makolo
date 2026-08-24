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

  function clearStoredPreference() {
    try {
      window.localStorage.removeItem('theme');
    } catch (_error) {
      // Browser storage is optional and must never override account preferences.
    }
  }

  const storedPreference = readStoredPreference();
  const preference = hasServerPreference
    ? (valid.has(serverPreference) ? serverPreference : 'system')
    : (storedPreference || 'system');

  // Authenticated preferences belong to the account and must not leak into
  // the anonymous session after logout or into the next account.
  if (hasServerPreference) clearStoredPreference();

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
