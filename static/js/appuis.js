/* Local-only filtering and progressive disclosure; no business state. */
(() => {
  const root = document.querySelector('[data-mk-surface="appuis"]');
  if (!root) return;
  const filters = [...root.querySelectorAll('[data-appuis-filter]')];
  const families = [...root.querySelectorAll('[data-appuis-family]')];
  for (const filter of filters) {
    filter.addEventListener('click', () => {
      const selected = filter.dataset.appuisFilter;
      for (const candidate of filters) {
        candidate.setAttribute('aria-pressed',
          String(candidate.dataset.appuisFilter === selected));
      }
      for (const section of families) {
        section.hidden = selected !== 'all' &&
          section.dataset.appuisFamily !== selected;
      }
    });
  }
  for (const button of root.querySelectorAll('[data-appuis-expand]')) {
    button.addEventListener('click', () => {
      const key = button.dataset.appuisExpand;
      const items = [...root.querySelectorAll('[data-appuis-more="' + key + '"]')];
      const expanded = button.getAttribute('aria-expanded') === 'true';
      for (const item of items) item.hidden = expanded;
      button.setAttribute('aria-expanded', String(!expanded));
      button.textContent = expanded ? 'Tout voir' : 'Voir moins';
    });
  }
})();