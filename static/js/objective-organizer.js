/* Moi > Mes démarches. Owner data arrives in the page; all view interactions
   are local. Never persist private facts into browser localStorage. */
(() => {
  'use strict';
  const root = document.querySelector('[data-organizer]');
  const data = document.getElementById('mk-organizer-data');
  if (!root || !data) return;

  let initial;
  try { initial = JSON.parse(data.textContent); } catch (_) { return; }
  if (!initial.actor || initial.actor.id !== root.dataset.actor) return;

  const $ = (selector) => root.querySelector(selector);
  const results = $('[data-results]');
  const summary = $('[data-summary]');
  const suggestions = $('[data-suggestions]');
  const continuation = $('[data-continuation]');
  const more = $('[data-more]');
  const error = $('[data-more-error]');
  const state = {
    rows: Array.isArray(initial.items) ? initial.items : [],
    hasMore: !!(initial.page && initial.page.has_more),
    nextOffset: initial.page ? initial.page.next_offset : 50,
    expanded: new Set(),
    mode: 'cards',
    descending: false,
    loading: false,
  };
  const lens = initial.actor_context || {kind: 'personal'};
  const spaceSlug = lens.kind === 'space' ? lens.space?.slug : null;
  if (lens.kind === 'space' && typeof spaceSlug !== 'string') return;
  const scopeParam = spaceSlug ? '&context=space&space=' +
    encodeURIComponent(spaceSlug) : '';
  const scopeSuffix = spaceSlug ? '?context=space&space=' +
    encodeURIComponent(spaceSlug) : '';
  const viewKey = 'mk.organizer.mode.' + initial.actor.id +
    (spaceSlug ? ':space:' + spaceSlug : '');
  try {
    const saved = localStorage.getItem(viewKey);
    if (['cards', 'list', 'explorer'].includes(saved)) state.mode = saved;
  } catch (_) { /* A private browsing mode may refuse preferences. */ }

  const element = (tag, className, label) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (label != null) node.textContent = label;
    return node;
  };
  const icon = (name) => {
    const node = element('i');
    node.setAttribute('data-lucide', name);
    node.setAttribute('aria-hidden', 'true');
    return node;
  };
  const iconName = (row) => ({
    project: 'folder-kanban',
    dossier: 'folder',
    journey: 'route',
  })[row.kind] || 'file';
  const kindLabel = (row) => ({
    project: 'Projet',
    dossier: 'Dossier',
    journey: 'Démarche',
  })[row.kind] || 'Élément';
  const humanState = (row) => ({
    draft: 'En préparation', active: 'En cours',
    completed: 'Terminé', fulfilled: 'Terminé',
    cancelled: 'Annulé', archived: 'Archivé',
    expired: 'Expirée', rejected: 'Refusée',
    submitted: 'Soumise', pending_approval: 'Approbation attendue',
    pending_payment: 'Paiement attendu',
    confirmed: 'Confirmée', approved: 'Approuvée',
    in_progress: 'En cours',
  })[row.state] || 'État indisponible';
  const id = (row) => row.kind + ':' + row.id;
  const fold = (value) => String(value || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').trim().toLocaleLowerCase('fr');
  const validUrl = (value) => typeof value === 'string' &&
    value.startsWith('/') && !value.startsWith('//');
  const url = (row) => {
    if (!validUrl(row.web_url)) return '#';
    return spaceSlug && (row.kind === 'project' || row.kind === 'dossier')
      ? row.web_url + scopeSuffix : row.web_url;
  };
  const all = () => {
    const seen = new Set();
    return state.rows.filter((row) => {
      if (!row || !['project', 'dossier', 'journey'].includes(row.kind) ||
          typeof row.id !== 'string' || typeof row.title !== 'string') return false;
      if (seen.has(id(row))) return false;
      seen.add(id(row));
      return true;
    });
  };
  const byId = () => new Map(all().map((row) => [id(row), row]));
  const parentFor = (row, index) => {
    if (row.kind === 'dossier' && row.project_id) {
      return index.get('project:' + row.project_id);
    }
    if (row.kind === 'journey' && Array.isArray(row.dossier_ids)) {
      for (const dossierId of row.dossier_ids) {
        const parent = index.get('dossier:' + dossierId);
        if (parent) return parent;
      }
    }
    return null;
  };
  const independent = (row) => row.kind === 'project' ||
    (row.kind === 'dossier' && !row.project_id) ||
    (row.kind === 'journey' && !(row.dossier_ids || []).length);
  const dateValue = (row, field) => {
    let key = field;
    if (field === 'deadline') {
      key = row.kind === 'project' ? 'ends_on' :
        row.kind === 'journey' ? null : 'deadline';
    } else if (field === 'fulfilled_at') {
      key = row.kind === 'journey' ? 'fulfilled_at' : null;
    } else if (field === 'starts_on') {
      key = row.kind === 'journey' ? 'started_at' :
        row.kind === 'dossier' ? null : 'starts_on';
    }
    const value = key ? row[key] : null;
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
    return value.slice(0, 10);
  };
  const displayDate = (row) => {
    const field = row.kind === 'dossier' ? 'deadline' :
      row.kind === 'project' ? 'ends_on' : null;
    const label = field === 'deadline' ? 'Échéance' : 'Fin de l’horizon';
    const value = field ? row[field] : null;
    if (!value) return '';
    const date = String(value).slice(0, 10).split('-');
    return date.length === 3 ? label + ' · ' + date.reverse().join('/') : '';
  };
  const controls = () => ({
    q: fold($('[data-search]').value),
    kind: $('[data-filter-kind]').value,
    status: $('[data-filter-status]').value,
    placement: $('[data-filter-placement]').value,
    period: $('[data-filter-period]').value,
    dateField: $('[data-filter-date-field]').value,
    sort: $('[data-sort]').value,
  });
  const matches = (row, options) => {
    if (options.kind !== 'all' && row.kind !== options.kind) return false;
    if (options.placement === 'independent' && !independent(row)) return false;
    if (options.status !== 'all') {
      if (row.kind === 'journey' && options.status === 'active') {
        if (['fulfilled', 'rejected', 'cancelled', 'expired'].includes(row.state)) return false;
      } else if (row.kind === 'journey' && options.status === 'completed') {
        if (row.state !== 'fulfilled') return false;
      } else if (row.state !== options.status) return false;
    }
    if (options.q && !fold([row.title, row.description,
      row.space && row.space.name].join(' ')).includes(options.q)) return false;
    if (options.period !== 'all') {
      const date = dateValue(row, options.dateField);
      if (!date) return false;
      const now = new Date();
      const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
      const parsed = Date.parse(date + 'T00:00:00Z');
      if (parsed < today || parsed > today + Number(options.period) * 86400000) return false;
    }
    return true;
  };
  const order = (rows, options) => rows.slice().sort((a, b) => {
    let comparison = 0;
    if (options.sort === 'title') {
      comparison = fold(a.title).localeCompare(fold(b.title), 'fr');
    } else {
      const first = dateValue(a, options.sort);
      const second = dateValue(b, options.sort);
      if (!first && second) return 1;
      if (!second && first) return -1;
      if (first && second) comparison = first.localeCompare(second);
    }
    if (state.descending) comparison = -comparison;
    return comparison || id(a).localeCompare(id(b));
  });
  const children = (row, rows, options) => {
    if (row.kind === 'project') return order(rows.filter(
      (child) => child.kind === 'dossier' && child.project_id === row.id,
    ), options);
    if (row.kind === 'dossier') return order(rows.filter(
      (child) => child.kind === 'journey' &&
        Array.isArray(child.dossier_ids) && child.dossier_ids.includes(row.id),
    ), options);
    return [];
  };
  const appendTag = (container, label) => {
    if (label) container.appendChild(element('span', 'mk-organizer__tag', label));
  };
  const link = (row, className) => {
    const node = element('a', className);
    node.href = url(row);
    node.appendChild(icon(iconName(row)));
    node.appendChild(element('span', 'mk-organizer__link-title', row.title));
    return node;
  };

  const card = (row, rows, options) => {
    const card = element('article', 'mk-organizer__card');
    const head = element('div', 'mk-organizer__card-head');
    head.appendChild(icon(iconName(row)));
    head.appendChild(element('span', 'mk-organizer__state', humanState(row)));
    card.appendChild(head);
    card.appendChild(link(row, 'mk-organizer__card-title'));
    if (row.description?.trim())
      card.appendChild(element('p', 'mk-organizer__card-description',
        row.description));
    const tags = element('div', 'mk-organizer__tags');
    appendTag(tags, kindLabel(row));
    appendTag(tags, displayDate(row));
    card.appendChild(tags);
    const preview = children(row, rows, options).slice(0, 3);
    if (preview.length) {
      const sub = element('div', 'mk-organizer__preview');
      for (const item of preview) sub.appendChild(link(item, 'mk-organizer__preview-item'));
      card.appendChild(sub);
    }
    return card;
  };
  const listRow = (row, index) => {
    const item = element('div', 'mk-organizer__list-item');
    const anchor = link(row, 'mk-organizer__list-link');
    const copy = element('div', 'mk-organizer__list-copy');
    const parent = parentFor(row, index);
    const meta = [kindLabel(row), humanState(row)];
    if (parent) meta.push('Dans : ' + parent.title);
    if (displayDate(row)) meta.push(displayDate(row));
    copy.appendChild(element('p', 'mk-organizer__meta', meta.join(' · ')));
    anchor.appendChild(copy);
    anchor.appendChild(icon('chevron-right'));
    item.appendChild(anchor);
    return item;
  };
  const treeNode = (row, rows, options, depth) => {
    const visible = children(row, rows, options).filter(
      (child) => matchTree(child, rows, options),
    );
    const wrapper = element('div', 'mk-organizer__node');
    const horizontal = element('div', 'mk-organizer__node-head');
    horizontal.style.paddingInlineStart = Math.min(depth * 20, 50) + 'px';
    if (visible.length) {
      const toggle = element('button', 'mk-organizer__node-toggle');
      toggle.type = 'button';
      const expanded = state.expanded.has(id(row)) || !!options.q;
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.setAttribute('aria-label', (expanded ? 'Replier ' : 'Déplier ') + row.title);
      toggle.appendChild(icon(expanded ? 'chevron-down' : 'chevron-right'));
      toggle.addEventListener('click', () => {
        if (state.expanded.has(id(row))) state.expanded.delete(id(row));
        else state.expanded.add(id(row));
        render();
      });
      horizontal.appendChild(toggle);
    } else {
      horizontal.appendChild(element('span', 'mk-organizer__node-spacer'));
    }
    horizontal.appendChild(link(row, 'mk-organizer__node-link'));
    horizontal.appendChild(element('span', 'mk-organizer__meta', humanState(row)));
    wrapper.appendChild(horizontal);
    if (visible.length && (state.expanded.has(id(row)) || !!options.q)) {
      const inside = element('div', 'mk-organizer__node-children');
      for (const item of visible) inside.appendChild(treeNode(item, rows, options, depth + 1));
      wrapper.appendChild(inside);
    }
    return wrapper;
  };
  const matchTree = (row, rows, options) =>
    matches(row, options) || children(row, rows, options)
      .some((child) => matchTree(child, rows, options));

  function renderSuggestions(rows, options) {
    suggestions.replaceChildren();
    if (!options.q) {
      suggestions.hidden = true;
      return;
    }
    const found = order(rows.filter((row) => matches(row, options)), options).slice(0, 5);
    suggestions.hidden = !found.length;
    for (const item of found) {
      const chip = link(item, 'mk-organizer__suggestion');
      chip.setAttribute('title', kindLabel(item) + ' · ' + item.title);
      suggestions.appendChild(chip);
    }
  }

  function render() {
    const rows = all();
    const index = byId();
    const options = controls();
    const filtered = order(rows.filter((row) => matches(row, options)), options);
    const roots = order(rows.filter((row) =>
      row.kind === 'project' ||
      (row.kind === 'dossier' && (!row.project_id ||
        !index.has('project:' + row.project_id))) ||
      (row.kind === 'journey' && (!(row.dossier_ids || []).length ||
        !row.dossier_ids.some((parentId) => index.has('dossier:' + parentId)))),
    ), options).filter((row) => matchTree(row, rows, options));
    const showFlat = state.mode === 'list' ||
      (state.mode === 'cards' && (options.kind !== 'all' ||
        options.placement === 'independent'));
    const visible = showFlat ? filtered : roots;

    for (const button of root.querySelectorAll('[data-view]')) {
      const active = button.dataset.view === state.mode;
      button.setAttribute('aria-pressed', String(active));
    }
    // The selected filter is indicated by the icon treatment; values are
    // always available through the native accessible select menu.
    for (const [selector, defaultValue] of [
      ['[data-filter-kind]', 'all'],
      ['[data-filter-status]', 'all'],
      ['[data-filter-placement]', 'all'],
      ['[data-filter-date-field]', 'created_at'],
      ['[data-filter-period]', 'all'],
      ['[data-sort]', 'title'],
    ]) {
      const control = $(selector);
      control?.closest('.mk-organizer__icon-filter')?.classList.toggle(
        'is-active', control.value !== defaultValue,
      );
    }
    results.className = 'mk-organizer__results mk-organizer__results--' + state.mode;
    results.replaceChildren();
    renderSuggestions(rows, options);
    summary.textContent = filtered.length
      ? filtered.length + ' résultat' + (filtered.length > 1 ? 's' : '') +
          (state.hasMore ? ' · affichage partiel' : '')
      : state.hasMore ? 'Chargement partiel' : '';

    if (!visible.length) {
      const empty = element('p', 'mk-organizer__empty');
      empty.textContent = rows.length
        ? 'Aucun résultat.'
        : state.hasMore ? 'Aucun élément chargé.' : 'Aucune démarche.';
      results.appendChild(empty);
    } else if (state.mode === 'cards') {
      for (const row of visible) results.appendChild(card(row, rows, options));
    } else if (showFlat) {
      for (const row of visible) results.appendChild(listRow(row, index));
    } else {
      for (const row of visible) {
        results.appendChild(treeNode(row, rows, options, 0));
      }
    }
    continuation.hidden = !state.hasMore;
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  }

  for (const field of root.querySelectorAll('[data-search], [data-filter-kind], ' +
      '[data-filter-status], [data-filter-placement], [data-filter-date-field], ' +
      '[data-filter-period], [data-sort]')) {
    field.addEventListener(field.matches('input') ? 'input' : 'change', render);
  }
  for (const button of root.querySelectorAll('[data-view]')) {
    button.addEventListener('click', () => {
      state.mode = button.dataset.view;
      try { localStorage.setItem(viewKey, state.mode); } catch (_) {}
      render();
    });
  }
  $('[data-reverse]').addEventListener('click', () => {
    state.descending = !state.descending;
    $('[data-reverse]').setAttribute('aria-label', state.descending
      ? 'Ordre décroissant' : 'Ordre croissant');
    render();
  });
  $('[data-reset]').addEventListener('click', () => {
    $('[data-search]').value = '';
    $('[data-filter-kind]').value = 'all';
    $('[data-filter-status]').value = 'all';
    $('[data-filter-placement]').value = 'all';
    $('[data-filter-date-field]').value = 'created_at';
    $('[data-filter-period]').value = 'all';
    $('[data-sort]').value = 'title';
    state.descending = false;
    render();
  });
  more.addEventListener('click', async () => {
    if (state.loading || !state.hasMore) return;
    state.loading = true;
    more.disabled = true;
    more.textContent = 'Chargement des éléments suivants…';
    error.hidden = true;
    try {
      const offset = state.nextOffset;
      const response = await fetch('/api/v1/objectives/organizer/?limit=50&offset=' +
        encodeURIComponent(offset) + scopeParam, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {Accept: 'application/json'},
      });
      if (!response.ok) throw new Error('Organizer continuation unavailable');
      const envelope = await response.json();
      const incoming = envelope.data;
      const incomingLens = incoming?.actor_context || {kind: 'personal'};
      if (!incoming || !incoming.actor ||
          incoming.actor.id !== initial.actor.id ||
          incomingLens.kind !== lens.kind ||
          (spaceSlug && incomingLens.space?.slug !== spaceSlug) ||
          !incoming.page || incoming.page.offset !== offset ||
          !Array.isArray(incoming.items)) throw new Error('Organizer owner mismatch');
      state.rows.push(...incoming.items);
      state.nextOffset = incoming.page.next_offset;
      state.hasMore = incoming.page.has_more === true;
      render();
    } catch (_) {
      error.hidden = false;
    } finally {
      state.loading = false;
      more.disabled = false;
      more.textContent = 'Charger les éléments suivants';
    }
  });
  render();
})();
