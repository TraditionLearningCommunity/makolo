/* Conversation folds remain an entirely local presentation of authorized
 * chronological entries. They never change owner ordering, read state or data. */
(() => {
  'use strict';
  function boot() {
    const root = document.querySelector('[data-conversation-thread]');
    const engine = window.MakoloConversationCompression;
    if (!root || !engine) return;
    const state = new engine.CompressionState();
    const olderButton = document.querySelector('[data-conversation-older-button]');
    let cursor = olderButton?.dataset.cursor || '';
    let loading = false;

    function visible(item) {
      const article = item.querySelector('[data-thread-point]');
      if (!article) return true;
      if (article.dataset.actionPending === 'true') return true;
      if (article.dataset.important === 'true') return true;
      const resultAt = article.dataset.resultAt;
      if (resultAt) {
        const age = Date.now() - new Date(resultAt).getTime();
        if (Number.isFinite(age) && age >= 0 && age <= 7 * 86400000) {
          return true;
        }
      }
      return false;
    }

    function fold(segment) {
      const details = document.createElement('details');
      details.className = 'mk-conversation-fold';
      details.dataset.foldId = segment.id;
      const summary = document.createElement('summary');
      summary.className = 'mk-conversation-fold-summary';
      const title = document.createElement('span');
      title.textContent = segment.items.length + ' échanges';
      summary.append(title);
      const first = segment.items[0].element.dataset.day;
      const last = segment.items[segment.items.length - 1].element.dataset.day;
      if (first) {
        const period = document.createElement('small');
        period.textContent = last && first !== last ? first + ' – ' + last : first;
        summary.append(period);
      }
      const chevron = document.createElement('span');
      chevron.className = 'mk-conversation-fold-chevron';
      chevron.setAttribute('aria-hidden', 'true');
      chevron.textContent = '⌄';
      summary.append(chevron);
      const body = document.createElement('div');
      body.className = 'mk-conversation-fold-body';
      for (const item of segment.items) body.append(item.element);
      details.append(summary, body);
      details.open = segment.expanded;
      details.addEventListener('toggle', () => {
        if (details.open) state.expand(segment);
        else state.collapse(segment);
      });
      return details;
    }

    function render() {
      const nodes = [...root.querySelectorAll('[data-thread-entry]')];
      const segments = state.project(nodes.map((element) => ({
        id: element.dataset.entryId || '',
        keepVisible: visible(element),
        element
      })));
      const result = document.createDocumentFragment();
      for (const segment of segments) {
        if (segment.foldable) result.append(fold(segment));
        else result.append(segment.items[0].element);
      }
      root.replaceChildren(result);
    }

    function scrollAnchor() {
      const nodes = [...root.querySelectorAll('[data-thread-entry]')];
      const anchor = nodes.find((node) => {
        const rect = node.getBoundingClientRect();
        return rect.height > 0 && rect.top > -120;
      }) || root.querySelector('summary');
      return anchor ? {node: anchor, top: anchor.getBoundingClientRect().top} : null;
    }

    if (olderButton) {
      olderButton.hidden = !cursor;
      olderButton.addEventListener('click', async () => {
        if (loading || !cursor) return;
        loading = true;
        olderButton.disabled = true;
        const priorLabel = olderButton.textContent;
        olderButton.textContent = 'Chargement…';
        try {
          const url = new URL(olderButton.dataset.olderUrl, location.href);
          url.searchParams.set('cursor', cursor);
          const response = await fetch(url, {credentials: 'same-origin'});
          if (!response.ok) throw new Error('Continuation indisponible');
          const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
          const page = doc.querySelector('[data-older-page]');
          if (!page) throw new Error('Page de continuation invalide');
          const rows = [...page.querySelectorAll('[data-thread-entry]')];
          const known = new Set(
            [...root.querySelectorAll('[data-thread-entry]')].map(
              (entry) => entry.dataset.entryId
            )
          );
          const additions = rows.filter(
            (row) => row.dataset.entryId && !known.has(row.dataset.entryId)
          );
          const anchor = scrollAnchor();
          // Prepend the earlier chronological page without reordering current work.
          root.prepend(...additions);
          cursor = page.dataset.nextCursor || '';
          render();
          if (anchor?.node.isConnected) {
            window.scrollBy(0, anchor.node.getBoundingClientRect().top - anchor.top);
          }
          olderButton.hidden = !cursor;
        } catch (_) {
          olderButton.textContent = 'Réessayer';
        } finally {
          loading = false;
          olderButton.disabled = false;
          if (olderButton.textContent !== 'Réessayer') {
            olderButton.textContent = priorLabel;
          }
        }
      });
    }
    render();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else {
    boot();
  }
})();
