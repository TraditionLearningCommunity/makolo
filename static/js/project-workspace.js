/* Project depth: one owner projection, three local views. No inferred deadlines. */
(() => {
  'use strict';
  const root = document.querySelector('[data-project-workspace]');
  const json = document.getElementById('mk-project-workspace-data');
  if (!root || !json) return;
  let payload;
  try { payload = JSON.parse(json.textContent); } catch (_) { return; }
  if (!payload.identity || payload.identity.id !== root.dataset.projectId) return;
  const lens = payload.actor_context || {kind: 'personal'};
  const spaceSlug = lens.kind === 'space' ? lens.space?.slug : null;
  if (lens.kind === 'space' && typeof spaceSlug !== 'string') return;
  const scopeParam = spaceSlug ? '&context=space&space=' +
    encodeURIComponent(spaceSlug) : '';
  const scopeSuffix = spaceSlug ? '?context=space&space=' +
    encodeURIComponent(spaceSlug) : '';

  const $ = (selector) => root.querySelector(selector);
  const area = $('[data-project-content]');
  const more = $('[data-project-more]');
  const moreButton = $('[data-project-more-button]');
  const moreError = $('[data-project-more-error]');
  const state = {
    view: 'overview', q: '', status: 'all', readiness: 'all',
    sort: 'deadline', calendar: 'all',
    rows: Array.isArray(payload.visible_dossiers) ? payload.visible_dossiers : [],
    page: payload.dossiers_page || {}, pending: false,
  };
  const csrf = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  const el = (tag, cls, text) => {
    const result = document.createElement(tag);
    if (cls) result.className = cls;
    if (text !== undefined) result.textContent = text;
    return result;
  };
  const icon = (value) => {
    const node = el('i');
    node.setAttribute('data-lucide', value);
    node.setAttribute('aria-hidden', 'true');
    return node;
  };
  const add = (parent, node) => { parent.appendChild(node); return node; };
  const safeHref = (value) => typeof value === 'string' &&
    value.startsWith('/') && !value.startsWith('//') ? value : '#';
  const title = (row) => String(row.title || 'Dossier');
  const stateText = (code) => ({
    draft: 'En préparation', active: 'En cours', completed: 'Terminé',
    cancelled: 'Annulé', archived: 'Archivé',
    blocked: 'Bloqué', action_required: 'Action requise',
    waiting: 'En attente', ready: 'Prêt', complete: 'Terminé',
  })[code] || 'Situation non disponible';
  const localDay = (date) => date.getFullYear() + '-' +
    String(date.getMonth() + 1).padStart(2, '0') + '-' +
    String(date.getDate()).padStart(2, '0');
  const parse = (value) => typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : null;
  const when = (value) => {
    const parsed = parse(value);
    return parsed ? parsed.split('-').reverse().join('/') : '';
  };
  const fold = (value) => String(value || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').trim().toLocaleLowerCase('fr');
  const unique = () => {
    const seen = new Set();
    return state.rows.filter((row) => {
      if (!row || typeof row.id !== 'string' || typeof row.title !== 'string' ||
          seen.has(row.id)) return false;
      seen.add(row.id); return true;
    });
  };
  const sorted = (rows) => rows.slice().sort((a, b) => {
    if (state.sort === 'title') return fold(a.title).localeCompare(fold(b.title), 'fr');
    const aValue = state.sort === 'state' ? (a.state || '') : (parse(a[state.sort]) || '');
    const bValue = state.sort === 'state' ? (b.state || '') : (parse(b[state.sort]) || '');
    if (!aValue && bValue) return 1;
    if (!bValue && aValue) return -1;
    return aValue.localeCompare(bValue) || a.id.localeCompare(b.id);
  });
  const filtered = () => sorted(unique().filter((row) => {
    if (state.status !== 'all' && row.state !== state.status) return false;
    if (state.readiness !== 'all' &&
        (row.readiness || {}).state !== state.readiness) return false;
    return !state.q || fold(title(row) + ' ' + (row.description || '')).includes(fold(state.q));
  }));
  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  }
  function empty(message) {
    const container = el('div', 'mk-project__empty');
    add(container, icon('folder-open'));
    add(container, el('strong', '', message));
    add(container, el('p', '', 'Le Projet peut exister sans dossier, puis évoluer à votre rythme.'));
    return container;
  }
  function metric(number, label) {
    const node = el('div', 'mk-project__number');
    add(node, el('strong', '', String(number)));
    add(node, el('span', '', label));
    return node;
  }
  function dossierLink(row) {
    const link = el('a', '', title(row));
    link.href = safeHref(row.web_url) === '#' ? '#' :
      safeHref(row.web_url) + scopeSuffix;
    return link;
  }
  function postForm(action, fields) {
    const form = el('form');
    form.method = 'post';
    form.action = safeHref(action) === '#' ? '#' :
      safeHref(action) + scopeSuffix;
    const csrfField = el('input');
    csrfField.type = 'hidden'; csrfField.name = 'csrfmiddlewaretoken'; csrfField.value = csrf;
    add(form, csrfField);
    for (const [key, value] of Object.entries(fields || {})) {
      const node = el('input');
      node.type = 'hidden'; node.name = key; node.value = value;
      add(form, node);
    }
    add(document.body, form);
    form.submit();
  }
  function actionDialog(row, mode) {
    const dialog = el('dialog', 'mk-project__dialog');
    const inner = el('div');
    inner.style.padding = '24px';
    const form = el('div');
    add(form, el('h2', '', mode === 'unlink'
      ? 'Détacher ce dossier ?' : 'Déplacer ce dossier'));
    add(form, el('p', 'mk-project__hint', mode === 'unlink'
      ? 'Le dossier restera disponible indépendamment. Aucune démarche ne sera supprimée.'
      : 'Choisissez un Projet cible autorisé. Le Dossier conserve ses démarches.'));
    let targets;
    if (mode === 'move') {
      targets = el('select');
      targets.setAttribute('aria-label', 'Projet cible');
      targets.style.width = '100%';
      targets.style.padding = '12px';
      targets.style.margin = '14px 0';
      for (const option of payload.move_targets || []) {
        const choice = el('option', '', option.title);
        choice.value = option.id;
        add(targets, choice);
      }
      add(form, targets);
    }
    const actions = el('div', 'mk-project__dialog-actions');
    const cancel = el('button', 'mk-action-button', 'Annuler');
    cancel.dataset.variant = 'ghost';
    cancel.type = 'button'; cancel.addEventListener('click', () => dialog.close());
    add(actions, cancel);
    const confirm = el('button', 'mk-action-button', mode === 'unlink'
      ? 'Détacher' : 'Déplacer');
    confirm.dataset.variant = mode === 'unlink' ? 'danger' : 'primary';
    confirm.type = 'button';
    confirm.addEventListener('click', () => {
      const path = (row.web_actions || {})[mode];
      if (!safeHref(path) || path === '#') return;
      if (mode === 'move' && (!targets || !targets.value)) return;
      confirm.disabled = true;
      postForm(path, mode === 'move'
        ? {target_project_id: targets.value} : {});
    });
    add(actions, confirm);
    add(form, actions); add(inner, form); add(dialog, inner);
    add(root, dialog);
    dialog.addEventListener('close', () => dialog.remove(), {once: true});
    dialog.showModal();
  }
  function menu(row) {
    if (!row.capabilities || !row.capabilities.length || !csrf) return null;
    const box = el('div', 'mk-project__card-menu');
    if (row.capabilities.includes('move') &&
        Array.isArray(payload.move_targets) && payload.move_targets.length) {
      const button = el('button', 'mk-action-button');
      button.dataset.variant = 'secondary'; button.dataset.size = 'icon';
      button.type = 'button'; button.title = 'Déplacer le dossier';
      button.setAttribute('aria-label', 'Déplacer ' + title(row));
      add(button, icon('folder-input'));
      button.addEventListener('click', () => actionDialog(row, 'move'));
      add(box, button);
    }
    if (row.capabilities.includes('unlink')) {
      const button = el('button', 'mk-action-button');
      button.dataset.variant = 'danger'; button.dataset.size = 'icon';
      button.type = 'button'; button.title = 'Détacher le dossier';
      button.setAttribute('aria-label', 'Détacher ' + title(row));
      add(button, icon('unlink'));
      button.addEventListener('click', () => actionDialog(row, 'unlink'));
      add(box, button);
    }
    return box;
  }
  function card(row) {
    const node = el('article', 'mk-project__card');
    const head = el('div', 'mk-project__card-top');
    add(head, icon('folder'));
    add(head, dossierLink(row));
    const actions = menu(row);
    if (actions) add(head, actions);
    add(node, head);
    const meta = el('div', 'mk-project__card-meta');
    add(meta, el('span', '', stateText(row.state)));
    if (row.deadline) add(meta, el('span', '', 'Échéance ' + when(row.deadline)));
    const readiness = row.readiness || {};
    if (readiness.label) {
      add(meta, el('span', '', 'Situation : ' + readiness.label +
        (readiness.partial ? ' (partielle)' : '')));
    }
    add(node, meta);
    if (row.description) add(node, el('p', '', row.description));
    return node;
  }
  function renderOverview(rows) {
    add(area, el('h2', '', 'Vue d’ensemble'));
    add(area, el('p', 'mk-project__hint', 'Les compteurs concernent uniquement les Dossiers visibles acquis.'));
    const stats = el('div', 'mk-project__numbers');
    add(stats, metric(rows.length, state.page.has_more ? 'Dossiers acquis (partiel)' : 'Dossiers visibles'));
    add(stats, metric(rows.filter((x) => x.state === 'active').length, 'En cours · acquis'));
    add(stats, metric(rows.filter((x) => x.state === 'draft').length, 'En préparation · acquis'));
    add(stats, metric(rows.filter((x) => x.state === 'completed').length, 'Terminés · acquis'));
    add(area, stats);
    const today = localDay(new Date());
    const deadlines = rows.filter((row) => parse(row.deadline) &&
      parse(row.deadline) >= today)
      .sort((a, b) => parse(a.deadline).localeCompare(parse(b.deadline)));
    if (deadlines.length) {
      const next = el('p', 'mk-project__hint');
      const strong = el('strong', '', 'Prochaine échéance visible : ');
      add(next, strong); add(next, dossierLink(deadlines[0]));
      add(next, el('span', '', ' · ' + when(deadlines[0].deadline)));
      add(area, next);
    }
    const action = rows.filter((row) =>
      (row.readiness || {}).state === 'action_required');
    if (action.length) {
      add(area, el('h3', 'mk-project__subtitle', 'À suivre'));
      for (const row of action.slice(0, 3)) {
        const line = el('div', 'mk-project__row');
        add(line, icon('circle-alert'));
        const text = el('div', 'mk-project__row-body');
        add(text, dossierLink(row));
        add(text, el('small', '', 'Une action est requise selon les faits visibles.'));
        add(line, text); add(area, line);
      }
    }
    add(area, el('h3', 'mk-project__subtitle', 'Dossiers du Projet'));
    const cards = el('div', 'mk-project__cards');
    for (const row of rows.slice(0, 6)) add(cards, card(row));
    if (!rows.length) add(cards, empty('Aucun Dossier visible dans ce Projet'));
    add(area, cards);
    if (rows.length > 6) {
      const btn = el('button', 'mk-action-button', 'Voir tous les dossiers acquis');
      btn.dataset.variant = 'secondary';
      btn.type = 'button';
      btn.addEventListener('click', () => { state.view = 'dossiers'; render(); });
      add(area, btn);
    }
  }
  function dropdown(label, values, selected, onSelect) {
    const box = el('label', '', label);
    const select = el('select');
    for (const [value, caption] of values) {
      const option = el('option', '', caption);
      option.value = value;
      add(select, option);
    }
    select.value = selected;
    select.addEventListener('change', () => onSelect(select.value));
    add(box, select);
    return box;
  }
  function renderDossiers(rows) {
    add(area, el('h2', '', 'Dossiers du Projet'));
    add(area, el('p', 'mk-project__hint', 'Recherchez et triez les dossiers déjà acquis, sans requête réseau.'));
    const filter = el('div', 'mk-project__filters');
    const inputBox = el('label', '', 'Recherche locale');
    const search = el('input');
    search.type = 'search'; search.placeholder = 'Nom ou description';
    search.value = state.q;
    search.addEventListener('input', () => {
      state.q = search.value;
      // Repaint only the result rows while retaining the active input focus.
      renderRows();
    });
    add(inputBox, search); add(filter, inputBox);
    add(filter, dropdown('État', [
      ['all', 'Tous'], ['draft', 'En préparation'], ['active', 'En cours'],
      ['completed', 'Terminés'], ['cancelled', 'Annulés'], ['archived', 'Archivés'],
    ], state.status, (value) => { state.status = value; render(); }));
    add(filter, dropdown('Readiness', [
      ['all', 'Toutes'], ['blocked', 'Bloqué'], ['action_required', 'Action requise'],
      ['waiting', 'En attente'], ['ready', 'Prêt'], ['complete', 'Terminé'],
    ], state.readiness, (value) => { state.readiness = value; render(); }));
    add(filter, dropdown('Tri', [
      ['title', 'Nom'], ['deadline', 'Échéance'], ['state', 'État'],
      ['created_at', 'Création'], ['updated_at', 'Modification'],
    ], state.sort, (value) => { state.sort = value; render(); }));
    add(area, filter);
    const list = el('div');
    add(area, list);
    function renderRows() {
      list.replaceChildren();
      const matching = filtered();
      add(list, el('p', 'mk-project__hint', matching.length + ' résultat(s) acquis'));
      if (!matching.length) { add(list, empty('Aucun résultat pour ces critères')); return; }
      for (const row of matching) {
        const line = el('div', 'mk-project__row');
        add(line, icon('folder'));
        const text = el('div', 'mk-project__row-body');
        add(text, dossierLink(row));
        add(text, el('small', '', stateText(row.state) +
          (row.deadline ? ' · Échéance ' + when(row.deadline) : '') +
          ((row.readiness || {}).label ? ' · ' + row.readiness.label : '')));
        add(line, text);
        const actions = menu(row);
        if (actions) add(line, actions);
        add(list, line);
      }
      refreshIcons();
    }
    renderRows();
  }
  function renderCalendar(rows) {
    add(area, el('h2', '', 'Calendrier du Projet'));
    add(area, el('p', 'mk-project__hint', 'Une échéance est un jalon ponctuel. Aucune barre de durée ni pourcentage n’est inventé pour un Dossier.'));
    const horizon = payload.horizon || {};
    const start = parse(horizon.starts_on);
    const end = parse(horizon.ends_on);
    const panel = el('div', 'mk-project__calendar');
    add(panel, el('h3', '', 'Horizon du Projet'));
    add(panel, el('p', 'mk-project__hint', start || end
      ? 'Début : ' + (start ? when(start) : 'non défini') +
        ' · Fin : ' + (end ? when(end) : 'non définie')
      : 'Aucune date d’horizon renseignée.'));
    if (start && end && end > start) {
      const line = el('div', 'mk-project__line');
      const first = Date.parse(start + 'T00:00:00Z');
      const duration = Date.parse(end + 'T00:00:00Z') - first;
      for (const row of rows) {
        const deadline = parse(row.deadline);
        if (!deadline || deadline < start || deadline > end) continue;
        const pct = (Date.parse(deadline + 'T00:00:00Z') - first) / duration * 100;
        const anchor = el('a', 'mk-project__point');
        anchor.href = safeHref(row.web_url);
        anchor.style.left = pct + '%';
        anchor.title = title(row) + ' · ' + when(deadline);
        anchor.setAttribute('aria-label', anchor.title);
        add(line, anchor);
      }
      add(panel, line);
      const bounds = el('div', 'mk-project__horizon');
      add(bounds, el('span', '', when(start)));
      add(bounds, el('span', '', when(end)));
      add(panel, bounds);
    }
    add(area, panel);
    const control = el('div', 'mk-project__filters');
    const options = [
      ['all', 'Tous les jalons'], ['upcoming', '30 prochains jours'],
      ['late', 'En retard'], ['active', 'Dossiers actifs'],
      ['undated', 'Sans date'],
    ];
    add(control, dropdown('Afficher', options, state.calendar, (value) => {
      state.calendar = value; render();
    }));
    const today = el('button', 'mk-action-button', 'Aujourd’hui');
    today.dataset.variant = 'secondary';
    today.type = 'button';
    today.addEventListener('click', () => {
      state.calendar = 'upcoming'; render();
    });
    add(control, today); add(area, control);
    const now = new Date(), day = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayDate = localDay(day);
    const in30 = localDay(new Date(day.getTime() + 30 * 86400000));
    const dates = rows.filter((row) => {
      const d = parse(row.deadline);
      switch (state.calendar) {
        case 'upcoming': return d && d >= todayDate && d <= in30;
        case 'late': return d && d < todayDate && row.state === 'active';
        case 'active': return row.state === 'active';
        case 'undated': return !d;
        default: return true;
      }
    }).sort((a, b) => {
      const first = parse(a.deadline), second = parse(b.deadline);
      return !first ? (second ? 1 : 0) : !second ? -1 : first.localeCompare(second);
    });
    if (!dates.length) add(area, empty('Aucun jalon correspondant'));
    for (const row of dates) {
      const line = el('div', 'mk-project__milestone');
      add(line, icon(row.deadline ? 'flag' : 'calendar-off'));
      add(line, dossierLink(row));
      add(line, el('small', '', row.deadline
        ? 'Échéance · ' + when(row.deadline) : 'Sans échéance'));
      add(area, line);
    }
  }
  function render() {
    area.replaceChildren();
    for (const button of root.querySelectorAll('[data-project-view]')) {
      button.setAttribute('aria-pressed', String(button.dataset.projectView === state.view));
    }
    const rows = unique();
    if (state.view === 'dossiers') renderDossiers(rows);
    else if (state.view === 'calendar') renderCalendar(rows);
    else renderOverview(rows);
    more.hidden = state.page.has_more !== true;
    refreshIcons();
  }
  for (const button of root.querySelectorAll('[data-project-view]')) {
    button.addEventListener('click', () => {
      state.view = button.dataset.projectView; render();
    });
  }
  for (const opener of root.querySelectorAll('[data-dialog-open]')) {
    opener.addEventListener('click', () => {
      const dialog = document.getElementById(opener.dataset.dialogOpen);
      if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
    });
  }
  for (const closer of root.querySelectorAll('[data-dialog-close]')) {
    closer.addEventListener('click', () => closer.closest('dialog')?.close());
  }
  moreButton.addEventListener('click', async () => {
    if (state.pending || !state.page.has_more) return;
    state.pending = true; moreButton.disabled = true; moreError.hidden = true;
    moreButton.textContent = 'Chargement…';
    try {
      const offset = state.page.next_offset;
      const url = '/api/v1/objectives/projects/' +
        encodeURIComponent(root.dataset.projectId) + '/dossiers/' +
        '?limit=50&offset=' + encodeURIComponent(offset) + scopeParam;
      const response = await fetch(url, {credentials: 'same-origin',
        headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('Project Dossier continuation unavailable');
      const envelope = await response.json();
      const page = envelope.data;
      const pageLens = page?.actor_context || {kind: 'personal'};
      if (!page || page.project_id !== root.dataset.projectId ||
          pageLens.kind !== lens.kind ||
          (spaceSlug && pageLens.space?.slug !== spaceSlug) ||
          page.page?.offset !== offset || !Array.isArray(page.items)) {
        throw new Error('Project owner projection mismatch');
      }
      state.rows.push(...page.items);
      state.page = page.page;
      render();
    } catch (_) {
      moreError.hidden = false;
    } finally {
      state.pending = false; moreButton.disabled = false;
      moreButton.textContent = 'Charger d’autres dossiers';
    }
  });
  render();
})();
