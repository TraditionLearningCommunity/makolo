/* Display preference only. No owner selection, API or permissions are inferred. */
(function () {
  'use strict';

  function activate(root) {
    if (!root || root.dataset.usLayoutReady === 'true') return;
    const grid = root.querySelector('[data-us-territories]');
    if (!grid) return;
    const buttons = Array.from(root.querySelectorAll('[data-us-layout-choice]'));
    if (buttons.length !== 2) return;
    root.dataset.usLayoutReady = 'true';
    const space = grid.getAttribute('data-us-space-id') || '';
    const key = space ? 'makolo.us.layout.' + space : null;

    function setLayout(value) {
      const mode = value === 'grid' ? 'grid' : 'list';
      grid.setAttribute('data-us-layout', mode);
      buttons.forEach(function (button) {
        const selected = button.getAttribute('data-us-layout-choice') === mode;
        button.setAttribute('aria-pressed', String(selected));
      });
    }

    let saved = 'list';
    if (key) {
      try { saved = window.sessionStorage.getItem(key) || 'list'; }
      catch (_) { /* Storage availability never blocks navigation. */ }
    }
    setLayout(saved);

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        const value = button.getAttribute('data-us-layout-choice');
        setLayout(value);
        if (key) {
          try { window.sessionStorage.setItem(key, value); }
          catch (_) { /* Presentational preference only. */ }
        }
      });
    });
  }

  function initialize(event) {
    const target = event && event.target && event.target.querySelectorAll
      ? event.target : document;
    if (target.matches && target.matches('[data-space-us-root]')) activate(target);
    target.querySelectorAll('[data-space-us-root]').forEach(activate);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }
  document.addEventListener('htmx:afterSwap', initialize);
})();
