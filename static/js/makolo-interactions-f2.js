/* Makolo Interaction Grammar F2 — local presentation and owner-bound intents.
 * No permissions, rank persistence, business mutation or navigation API lives here.
 * Data attributes are opt-in. Reconciliation remains owned by each caller.
 */
(() => {
  'use strict';

  const rootFor = (node, selector) => node && node.closest(selector);
  const safeText = (node) => (node.textContent || '').trim();

  // SELECT: DOM-local, identity-stable, never a generic bulk mutation.
  function updateSelection(scope) {
    const boxes = [...scope.querySelectorAll('[data-mk-select-item]')];
    const selected = boxes.filter((box) => box.checked && !box.disabled)
      .map((box) => box.value);
    const count = scope.querySelector('[data-mk-selection-count]');
    const bar = scope.querySelector('[data-mk-selection-bar]');
    if (count) count.textContent = String(selected.length);
    if (bar) bar.hidden = selected.length === 0;
    scope.dispatchEvent(new CustomEvent('makolo:selection-change', {
      bubbles: true, detail: { ids: [...selected] }
    }));
  }

  function clearSelection(scope) {
    scope.querySelectorAll('[data-mk-select-item]').forEach((box) => {
      box.checked = false;
    });
    updateSelection(scope);
  }

  // FILTER/SORT: explicitly local to the acquired DOM corpus, NEVER Discovery rank.
  const stableIndex = new WeakMap();
  function acquireIndex(item, i) {
    if (!stableIndex.has(item)) stableIndex.set(item, i);
    return stableIndex.get(item);
  }

  function applyLocalQuery(scope) {
    if (scope.dataset.mkQueryLocal !== 'true') return;
    const container = scope.querySelector('[data-mk-query-items]');
    if (!container) return;
    const all = [...container.querySelectorAll(':scope > [data-mk-query-item]')];
    all.forEach((item, i) => acquireIndex(item, i));
    const searchField = scope.querySelector('[data-mk-query-search]');
    const filterField = scope.querySelector('[data-mk-query-filter]');
    const sortField = scope.querySelector('[data-mk-query-sort]');
    const search = (searchField ? searchField.value : '').trim().toLocaleLowerCase();
    const filter = filterField ? filterField.value : '';
    const sort = sortField ? sortField.value : '';
    if (sortField && sort) {
      const allowed = (scope.dataset.mkSortKeys || '').split(',').map((key) => key.trim());
      if (allowed.includes(sort)) {
        const order = scope.dataset.mkSortDescending === 'true' ? -1 : 1;
        all.sort((a, b) => {
          const left = a.getAttribute('data-mk-sort-' + sort) || '';
          const right = b.getAttribute('data-mk-sort-' + sort) || '';
          const result = left.localeCompare(right, undefined, {
            numeric: true, sensitivity: 'base'
          });
          return result ? result * order : acquireIndex(a, 0) - acquireIndex(b, 0);
        });
        all.forEach((node) => container.append(node));
      }
    }
    let visible = 0;
    all.forEach((item, i) => {
      acquireIndex(item, i);
      const haystack = (item.dataset.mkSearchText || safeText(item)).toLocaleLowerCase();
      const category = item.dataset.mkFilterValue || '';
      item.hidden = Boolean((search && !haystack.includes(search)) ||
        (filter && filter !== category));
      if (!item.hidden) visible += 1;
    });
    const counter = scope.querySelector('[data-mk-query-count]');
    const empty = scope.querySelector('[data-mk-query-empty]');
    if (counter) counter.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
    scope.dispatchEvent(new CustomEvent('makolo:query-change', {
      bubbles: true, detail: { visible, total: all.length, scope: 'acquired-dom' }
    }));
  }

  // PREVIEW: native <dialog> gives Escape, focus trap and accessible modal semantics.
  const previewOrigins = new WeakMap();
  function openPreview(trigger) {
    const id = trigger.dataset.mkPreviewTarget;
    const dialog = id && document.getElementById(id);
    if (!dialog || dialog.tagName !== 'DIALOG' ||
        typeof dialog.showModal !== 'function') return;
    previewOrigins.set(dialog, trigger);
    if (!dialog.open) dialog.showModal();
  }
  function closePreview(button) {
    const dialog = button.closest('dialog[data-mk-preview]');
    if (dialog && dialog.open) dialog.close();
  }

  // INLINE EDIT: existing owner form POST remains the only save mechanism.
  // Initial field values are reset on Cancel, never on failed owner submission.
  function showEditor(scope) {
    const view = scope.querySelector('[data-mk-edit-view]');
    const form = scope.querySelector('form[data-mk-edit-form]');
    if (!view || !form) return;
    view.hidden = true;
    form.hidden = false;
    const field = form.querySelector('input:not([disabled]), textarea:not([disabled]), select:not([disabled])');
    if (field) field.focus();
  }
  function cancelEditor(scope) {
    const view = scope.querySelector('[data-mk-edit-view]');
    const form = scope.querySelector('form[data-mk-edit-form]');
    if (!view || !form) return;
    form.reset();
    form.hidden = true;
    view.hidden = false;
    const trigger = scope.querySelector('[data-mk-edit-open]');
    if (trigger) trigger.focus();
  }

  // REORDER: presentation proposes a requested order to an owner adapter.
  // It never moves DOM nodes before the owner confirms the request.
  const reorderAdapters = new WeakMap();
  let activeDrag = null;
  const reorderBusy = new WeakSet();
  function reorderScope(scope) {
    const container = scope.querySelector('[data-mk-reorder-items]');
    if (!container) return null;
    const list = [...container.querySelectorAll(':scope > [data-mk-reorder-item]')];
    if (list.some((item) => !item.dataset.mkReorderId)) return null;
    const ids = list.map((item) => item.dataset.mkReorderId);
    if (new Set(ids).size !== ids.length) return null;
    return { container, list, ids };
  }
  async function requestReorder(scope, from, to) {
    const adapter = reorderAdapters.get(scope);
    const state = reorderScope(scope);
    if (!adapter || !state || reorderBusy.has(scope) ||
        from < 0 || to < 0 || from >= state.list.length ||
        to >= state.list.length || from === to) return;
    const order = [...state.ids];
    const movedId = order.splice(from, 1)[0];
    order.splice(to, 0, movedId);
    reorderBusy.add(scope);
    scope.setAttribute('aria-busy', 'true');
    try {
      // Adapter must only return true after authoritative confirmation and
      // should refresh its owner projection if the order is not canonical.
      const confirmed = await adapter(Object.freeze([...order]), movedId);
      if (confirmed !== true || !scope.isConnected) return;
      const latest = reorderScope(scope);
      if (!latest || latest.ids.join('|') !== state.ids.join('|')) return;
      const byId = new Map(latest.list.map((item) => [item.dataset.mkReorderId, item]));
      order.forEach((id) => latest.container.append(byId.get(id)));
      const moved = byId.get(movedId);
      const focus = moved.querySelector('[data-mk-reorder-up], [data-mk-reorder-down]');
      if (focus) focus.focus();
      scope.dispatchEvent(new CustomEvent('makolo:reorder-confirmed', {
        bubbles: true, detail: { ids: order, movedId }
      }));
    } catch (_) {
      // Owner adapter handles its human-readable error; never invent success.
      scope.dispatchEvent(new CustomEvent('makolo:reorder-failed', {
        bubbles: true, detail: { movedId }
      }));
    } finally {
      reorderBusy.delete(scope);
      scope.removeAttribute('aria-busy');
    }
  }

  function handleClick(event) {
    const clear = rootFor(event.target, '[data-mk-selection-clear]');
    if (clear) {
      const scope = rootFor(clear, '[data-mk-selection-scope]');
      if (scope) { event.preventDefault(); clearSelection(scope); }
      return;
    }
    const previewOpen = rootFor(event.target, '[data-mk-preview-target]');
    if (previewOpen) { event.preventDefault(); openPreview(previewOpen); return; }
    const previewClose = rootFor(event.target, '[data-mk-preview-close]');
    if (previewClose) { event.preventDefault(); closePreview(previewClose); return; }
    const editOpen = rootFor(event.target, '[data-mk-edit-open]');
    if (editOpen) {
      const scope = rootFor(editOpen, '[data-mk-inline-edit]');
      if (scope) { event.preventDefault(); showEditor(scope); }
      return;
    }
    const editCancel = rootFor(event.target, '[data-mk-edit-cancel]');
    if (editCancel) {
      const scope = rootFor(editCancel, '[data-mk-inline-edit]');
      if (scope) { event.preventDefault(); cancelEditor(scope); }
      return;
    }
    const reorderButton = rootFor(event.target,
      '[data-mk-reorder-up], [data-mk-reorder-down]');
    if (reorderButton) {
      const scope = rootFor(reorderButton, '[data-mk-reorder-scope]');
      const state = scope && reorderScope(scope);
      const item = rootFor(reorderButton, '[data-mk-reorder-item]');
      if (!state || !item) return;
      event.preventDefault();
      const index = state.list.indexOf(item);
      const delta = reorderButton.hasAttribute('data-mk-reorder-up') ? -1 : 1;
      void requestReorder(scope, index, index + delta);
    }
  }

  // Drag is optional, only from an explicit handle and registered owner adapter.
  // Touch/keyboard users have the same operation via Up/Down buttons.
  document.addEventListener('dragstart', (event) => {
    const handle = rootFor(event.target, '[data-mk-reorder-handle]');
    const scope = handle && rootFor(handle, '[data-mk-reorder-scope]');
    const item = handle && rootFor(handle, '[data-mk-reorder-item]');
    if (!scope || !item || !reorderAdapters.has(scope) || reorderBusy.has(scope)) {
      if (handle) event.preventDefault();
      return;
    }
    const state = reorderScope(scope);
    if (!state || !state.list.includes(item)) { event.preventDefault(); return; }
    activeDrag = { scope, id: item.dataset.mkReorderId };
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', activeDrag.id);
    }
  });
  document.addEventListener('dragover', (event) => {
    const target = rootFor(event.target, '[data-mk-reorder-item]');
    if (!target || !activeDrag) return;
    const scope = rootFor(target, '[data-mk-reorder-scope]');
    if (scope !== activeDrag.scope || reorderBusy.has(scope)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  });
  document.addEventListener('drop', (event) => {
    const target = rootFor(event.target, '[data-mk-reorder-item]');
    const current = activeDrag;
    activeDrag = null;
    if (!target || !current) return;
    const scope = rootFor(target, '[data-mk-reorder-scope]');
    if (scope !== current.scope) return;
    const state = reorderScope(scope);
    if (!state) return;
    event.preventDefault();
    const from = state.ids.indexOf(current.id);
    const to = state.list.indexOf(target);
    void requestReorder(scope, from, to);
  });
  document.addEventListener('dragend', () => { activeDrag = null; });
  document.addEventListener('click', handleClick);
  document.addEventListener('change', (event) => {
    if (event.target.matches('[data-mk-select-item]')) {
      const scope = rootFor(event.target, '[data-mk-selection-scope]');
      if (scope) updateSelection(scope);
    }
    if (event.target.matches('[data-mk-query-sort], [data-mk-query-filter]')) {
      const scope = rootFor(event.target, '[data-mk-query-scope]');
      if (scope) applyLocalQuery(scope);
    }
  });
  document.addEventListener('input', (event) => {
    if (event.target.matches('[data-mk-query-search]')) {
      const scope = rootFor(event.target, '[data-mk-query-scope]');
      if (scope) applyLocalQuery(scope);
    }
  });
  document.addEventListener('close', (event) => {
    if (!event.target.matches('dialog[data-mk-preview]')) return;
    const origin = previewOrigins.get(event.target);
    previewOrigins.delete(event.target);
    if (origin?.isConnected) origin.focus();
  }, true);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      const scope = rootFor(event.target, '[data-mk-inline-edit]');
      if (scope && scope.querySelector('form[data-mk-edit-form]:not([hidden])')) {
        event.preventDefault();
        cancelEditor(scope);
      }
    }
  });

  window.MakoloInteractions = Object.freeze({
    // Register a real owner transport. No registered adapter means no reorder.
    registerReorder(scope, adapter) {
      if (!(scope instanceof Element) || typeof adapter !== 'function') return false;
      reorderAdapters.set(scope, adapter);
      return true;
    },
    unregisterReorder(scope) { reorderAdapters.delete(scope); },
    selectedIds(scope) {
      if (!(scope instanceof Element)) return [];
      return [...scope.querySelectorAll('[data-mk-select-item]')]
        .filter((box) => box.checked && !box.disabled).map((box) => box.value);
    },
    clearSelection(scope) { if (scope instanceof Element) clearSelection(scope); },
    applyLocalQuery(scope) { if (scope instanceof Element) applyLocalQuery(scope); },
    closePreview(dialog) { if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close(); },
  });
})();
