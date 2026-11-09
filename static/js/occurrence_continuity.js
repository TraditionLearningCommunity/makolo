/* Jour J / Live / owner depths: visible browser content is not an authority.
 * No client-side snapshot is persisted; private pages are no-store.
 * A tab restored from bfcache or a long background interval revalidates
 * through the canonical server, without inventing changes or Live facts.
 */
(() => {
  'use strict';
  const root = document.querySelector('[data-occurrence-revalidate]');
  if (!root) return;

  const note = root.querySelector('[data-occurrence-state]');
  const refresh = root.querySelector('[data-occurrence-refresh]');
  const openedAt = performance.now();
  const expires = root.dataset.liveEndsAt
    ? Date.parse(root.dataset.liveEndsAt)
    : NaN;
  let hiddenAt = null;
  let marked = false;

  function blockStaleOperations(message) {
    if (marked) return;
    marked = true;
    note.textContent = message;
    note.hidden = false;
    refresh.hidden = false;
    root.closest('main')?.querySelectorAll(
      'form[method="post"] button[type="submit"], ' +
      'form[method="post"] button:not([type])'
    ).forEach(button => {
      button.disabled = true;
      button.setAttribute('aria-disabled', 'true');
    });
  }

  function checkAge() {
    if (document.hidden) return;
    if (!Number.isNaN(expires) && Date.now() >= expires) {
      blockStaleOperations(
        'La fenêtre Live prévue est terminée. Les informations affichées ' +
        'ne sont plus du direct. Actualisez pour vérifier la suite.'
      );
      return;
    }
    if (performance.now() - openedAt >= 120000) {
      blockStaleOperations(
        'Dernière lecture connue : les faits et autorisations peuvent avoir ' +
        'changé. Actualisez avant toute opération.'
      );
    }
  }

  refresh?.addEventListener('click', () => window.location.reload());
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      hiddenAt = performance.now();
      // The scanner never holds an unsubmitted secret through tab suspension.
      const manualCode = document.getElementById('manual-token');
      if (manualCode) manualCode.value = '';
      return;
    }
    if (hiddenAt !== null &&
        performance.now() - hiddenAt >= 15000) {
      window.location.reload();
      return;
    }
    hiddenAt = null;
    checkAge();
  });
  window.setInterval(checkAge, 15000);
  checkAge();
})();
