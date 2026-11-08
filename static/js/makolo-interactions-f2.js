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
    if (!sortField || !sort) {
      all.sort((a, b) => stableIndex.get(a) - stableIndex.get(b));
      all.forEach((node) => container.append(node));
    } else {
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
  const moveAdapters = new WeakMap();
  const moveBusy = new WeakSet();
  let activeMove = null;
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
    const status = scope.querySelector('[data-mk-reorder-status]');
    if (!adapter || !state || reorderBusy.has(scope) ||
        from < 0 || to < 0 || from >= state.list.length ||
        to >= state.list.length || from === to) return;
    const order = [...state.ids];
    const movedId = order.splice(from, 1)[0];
    order.splice(to, 0, movedId);
    reorderBusy.add(scope);
    scope.setAttribute('aria-busy', 'true');
    if (status) status.textContent = 'Réorganisation en cours…';
    try {
      // Adapter must only return true after authoritative confirmation and
      // should refresh its owner projection if the order is not canonical.
      const confirmed = await adapter(Object.freeze([...order]), movedId);
      if (confirmed !== true) {
        if (status) status.textContent = 'Nouvel ordre non confirmé.';
        scope.dispatchEvent(new CustomEvent('makolo:reorder-failed', {
          bubbles: true, detail: { movedId }
        }));
        return;
      }
      if (!scope.isConnected) return;
      const latest = reorderScope(scope);
      if (!latest || latest.ids.length !== state.ids.length ||
          latest.ids.some((id, i) => id !== state.ids[i])) return;
      const byId = new Map(latest.list.map((item) => [item.dataset.mkReorderId, item]));
      order.forEach((id) => latest.container.append(byId.get(id)));
      const moved = byId.get(movedId);
      const focus = moved.querySelector('[data-mk-reorder-up], [data-mk-reorder-down]');
      if (focus) focus.focus();
      if (status) status.textContent = 'Nouvel ordre confirmé.';
      scope.dispatchEvent(new CustomEvent('makolo:reorder-confirmed', {
        bubbles: true, detail: { ids: order, movedId }
      }));
    } catch (_) {
      if (status) status.textContent = 'Nouvel ordre non confirmé.';
      scope.dispatchEvent(new CustomEvent('makolo:reorder-failed', {
        bubbles: true, detail: { movedId }
      }));
    } finally {
      reorderBusy.delete(scope);
      scope.removeAttribute('aria-busy');
    }
  }


  // MOVE: distinct from REORDER. The owner must provide a real transport
  // AND a visible native-form alternative before a drag is enabled.
  async function requestMove(scope, sourceId, destinationId) {
    const adapter = moveAdapters.get(scope);
    const status = scope.querySelector('[data-mk-move-status]');
    if (!adapter || moveBusy.has(scope) || !sourceId || !destinationId) return;
    moveBusy.add(scope);
    scope.setAttribute('aria-busy', 'true');
    if (status) status.textContent = 'Déplacement en cours…';
    try {
      const confirmed = await adapter(Object.freeze({ sourceId, destinationId }));
      if (confirmed === true) {
        if (status) status.textContent = 'Déplacement confirmé.';
        scope.dispatchEvent(new CustomEvent('makolo:move-confirmed', {
          bubbles: true, detail: { sourceId, destinationId }
        }));
      } else {
        if (status) status.textContent = 'Déplacement non confirmé.';
        scope.dispatchEvent(new CustomEvent('makolo:move-failed', {
          bubbles: true, detail: { sourceId, destinationId }
        }));
      }
    } catch (_) {
      if (status) status.textContent = 'Déplacement non confirmé.';
      scope.dispatchEvent(new CustomEvent('makolo:move-failed', {
        bubbles: true, detail: { sourceId, destinationId }
      }));
    } finally {
      moveBusy.delete(scope);
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
      event.dataTransfer.setData('text/plain', 'makolo-reorder');
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

  document.addEventListener('dragstart', (event) => {
    const handle = rootFor(event.target, '[data-mk-move-handle]');
    if (!handle) return;
    const scope = rootFor(handle, '[data-mk-move-scope]');
    const source = rootFor(handle, '[data-mk-move-source]');
    if (!scope || !source || !moveAdapters.has(scope) || moveBusy.has(scope) ||
        !source.dataset.mkMoveId) {
      event.preventDefault();
      return;
    }
    activeMove = { scope, sourceId: source.dataset.mkMoveId };
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', 'makolo-move');
    }
  });
  document.addEventListener('dragover', (event) => {
    const target = rootFor(event.target, '[data-mk-move-destination]');
    if (!target || !activeMove) return;
    const scope = rootFor(target, '[data-mk-move-scope]');
    if (scope !== activeMove.scope || moveBusy.has(scope) ||
        !target.dataset.mkDestinationId) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    target.setAttribute('data-mk-drop-active', 'true');
  });
  document.addEventListener('dragleave', (event) => {
    const target = rootFor(event.target, '[data-mk-move-destination]');
    if (target && !target.contains(event.relatedTarget)) {
      target.removeAttribute('data-mk-drop-active');
    }
  });
  document.addEventListener('drop', (event) => {
    const target = rootFor(event.target, '[data-mk-move-destination]');
    const request = activeMove;
    activeMove = null;
    document.querySelectorAll('[data-mk-drop-active]').forEach(
      (element) => element.removeAttribute('data-mk-drop-active')
    );
    if (!target || !request) return;
    const scope = rootFor(target, '[data-mk-move-scope]');
    if (scope !== request.scope || !target.dataset.mkDestinationId) return;
    event.preventDefault();
    void requestMove(scope, request.sourceId, target.dataset.mkDestinationId);
  });
  document.addEventListener('dragend', () => {
    activeMove = null;
    document.querySelectorAll('[data-mk-drop-active]').forEach(
      (element) => element.removeAttribute('data-mk-drop-active')
    );
  });


  // Optional right-click shortcut into the same accessible three-dot menu.
  // Never steal text selection, links, inputs or the browser menu by default.
  document.addEventListener('contextmenu', (event) => {
    const shortcut = rootFor(event.target, '[data-mk-context-shortcut]');
    if (!shortcut || event.target.closest(
      'a, input, select, textarea, [contenteditable="true"]')) return;
    const menu = shortcut.matches('[data-mk-action-menu]')
      ? shortcut : shortcut.querySelector('[data-mk-action-menu]');
    const trigger = menu?.querySelector('[data-mk-action-trigger]');
    if (!trigger || trigger.disabled) return;
    event.preventDefault();
    if (trigger.getAttribute('aria-expanded') !== 'true') trigger.click();
  });

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


  // State is returned to the caller only; never persisted outside the current
  // owner/actor scope by this shared presentation layer.
  function captureContext(scope) {
    if (!(scope instanceof Element) || !scope.dataset.mkContextKey) return null;
    const read = (selector) => scope.querySelector(selector)?.value || '';
    const focus = scope.contains(document.activeElement)
      ? document.activeElement.id || '' : '';
    return Object.freeze({
      scopeKey: scope.dataset.mkContextKey,
      query: read('[data-mk-query-search]'),
      sort: read('[data-mk-query-sort]'),
      filter: read('[data-mk-query-filter]'),
      selectedIds: Object.freeze([...scope.querySelectorAll('[data-mk-select-item]')]
        .filter((box) => box.checked && !box.disabled)
        .map((box) => box.value)),
      scrollTop: scope.scrollTop,
      focusId: focus,
    });
  }

  function restoreContext(scope, context) {
    if (!(scope instanceof Element) || !context || !context.scopeKey ||
        !scope.dataset.mkContextKey ||
        scope.dataset.mkContextKey !== context.scopeKey) return false;
    const put = (selector, value) => {
      const field = scope.querySelector(selector);
      if (field && typeof value === 'string') field.value = value;
    };
    put('[data-mk-query-search]', context.query);
    put('[data-mk-query-sort]', context.sort);
    put('[data-mk-query-filter]', context.filter);
    const selected = new Set(Array.isArray(context.selectedIds)
      ? context.selectedIds : []);
    scope.querySelectorAll('[data-mk-select-item]').forEach((box) => {
      box.checked = !box.disabled && selected.has(box.value);
    });
    updateSelection(scope);
    applyLocalQuery(scope);
    if (typeof context.scrollTop === 'number') {
      scope.scrollTop = Math.max(0, context.scrollTop);
    }
    if (context.focusId && typeof context.focusId === 'string') {
      const candidate = document.getElementById(context.focusId);
      if (candidate && scope.contains(candidate) &&
          typeof candidate.focus === 'function') candidate.focus();
    }
    return true;
  }


  // Central Web equivalent of MakoloInteractionIcons in Flutter.
  // Glyphs join the existing frontend bundle when real templates reference them.
  const icons = Object.freeze({
    open: 'external-link',
    inspect: 'panel-right-open',
    more: 'ellipsis',
    select: 'square-check',
    sort: 'arrow-down-up',
    filter: 'filter',
    reorder: 'grip-vertical',
    move: 'folder-input',
    link: 'link-2',
    unlink: 'unlink',
    transition: 'arrow-left-right',
    edit: 'pencil',
    bulk: 'square-check',
    undo: 'undo-2',
    search: 'search',
  });
  window.MakoloInteractionIcons = icons;

  window.MakoloInteractions = Object.freeze({
    // Register a real owner transport. No registered adapter means no reorder.
    registerReorder(scope, adapter) {
      if (!(scope instanceof Element) || typeof adapter !== 'function') return false;
      const state = reorderScope(scope);
      if (!state || state.list.length < 2 ||
          state.list.some((item) => !item.querySelector(
            '[data-mk-reorder-up], [data-mk-reorder-down]'))) return false;
      reorderAdapters.set(scope, adapter);
      return true;
    },
    unregisterReorder(scope) { reorderAdapters.delete(scope); },
    // Require an actual fallback form; never make drag the only route.
    registerMove(scope, adapter) {
      if (!(scope instanceof Element) || typeof adapter !== 'function') return false;
      const fallback = scope.querySelector('form[data-mk-move-form]');
      if (!fallback || fallback.method.toLowerCase() !== 'post' ||
          !fallback.getAttribute('action') ||
          !fallback.querySelector('select[name], input[name="destination_id"]') ||
          !fallback.querySelector('button[type="submit"], input[type="submit"]') ||
          !fallback.querySelector('input[name="csrfmiddlewaretoken"]')) return false;
      moveAdapters.set(scope, adapter);
      return true;
    },
    unregisterMove(scope) { moveAdapters.delete(scope); },
    selectedIds(scope) {
      if (!(scope instanceof Element)) return [];
      return [...scope.querySelectorAll('[data-mk-select-item]')]
        .filter((box) => box.checked && !box.disabled).map((box) => box.value);
    },
    clearSelection(scope) { if (scope instanceof Element) clearSelection(scope); },
    captureContext,
    restoreContext,
    applyLocalQuery(scope) { if (scope instanceof Element) applyLocalQuery(scope); },
    closePreview(dialog) { if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close(); },
  });
})();
