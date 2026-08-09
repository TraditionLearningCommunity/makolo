(() => {
  const root = document.documentElement;

  function preferredDark() {
    const stored = localStorage.getItem('theme');
    if (stored === 'dark') return true;
    if (stored === 'light') return false;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  window.themeManager = function themeManager() {
    return {
      dark: preferredDark(),
      init() { this.applyTheme(); },
      toggleTheme() {
        this.dark = !this.dark;
        localStorage.setItem('theme', this.dark ? 'dark' : 'light');
        this.applyTheme();
      },
      applyTheme() {
        root.classList.toggle('dark', this.dark);
        root.style.colorScheme = this.dark ? 'dark' : 'light';
      },
    };
  };

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons();
  }

  document.addEventListener('DOMContentLoaded', refreshIcons);
  document.addEventListener('htmx:afterSwap', refreshIcons);
  document.addEventListener('htmx:afterSettle', refreshIcons);
})();
