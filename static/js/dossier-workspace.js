/* Dossier workspace: same authorized projection as Flutter.
 * Local-only views, filters, timeline and causal graph. Business mutations are
 * confirmed by the server's existing Objectives services.
 */
(() => {
  'use strict';
  const root = document.querySelector('[data-dossier-workspace]');
  const source = document.getElementById('mk-dossier-data');
  if (!root || !source) return;
  let data;
  try { data = JSON.parse(source.textContent); } catch (_) { return; }
  if (data.identity?.id !== root.dataset.dossierId) return;
  const lens = data.actor_context || {kind: 'personal'};
  const spaceSlug = lens.kind === 'space' ? lens.space?.slug : null;
  if (lens.kind === 'space' && typeof spaceSlug !== 'string') return;
  const scopeSuffix = spaceSlug ? '?context=space&space=' +
    encodeURIComponent(spaceSlug) : '';

  const stage = root.querySelector('[data-dossier-content]');
  const rows = Array.isArray(data.visible_journeys) ? data.visible_journeys : [];
  const dependencies = Array.isArray(data.visible_dependencies)
    ? data.visible_dependencies : [];
  const byId = new Map(rows.map((r) => [r.id, r]));
  const csrf = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  const state = {
    view: 'overview', query: '', filter: 'all', sort: 'recent',
    zoom: 1, panX: 0, panY: 0, timeScale: 'month',
  };
  const el = (tag, cls, value) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value != null) node.textContent = String(value);
    return node;
  };
  const svgEl = (tag, attrs = {}, value = null) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, val] of Object.entries(attrs)) node.setAttribute(key, String(val));
    if (value != null) node.textContent = String(value);
    return node;
  };
  const icon = (name) => {
    const node = el('i');
    node.setAttribute('data-lucide', name);
    node.setAttribute('aria-hidden', 'true');
    return node;
  };
  const append = (target, child) => { target.appendChild(child); return child; };
  const validUrl = (url) => typeof url === 'string' &&
    url.startsWith('/') && !url.startsWith('//') ? url : '#';
  const fold = (text) => String(text || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('fr').trim();
  const date = (value) => value && !Number.isNaN(new Date(value).getTime())
    ? new Date(value) : null;
  const dateLabel = (raw) => {
    const item = date(raw);
    return item ? new Intl.DateTimeFormat('fr-FR', {
      dateStyle: 'medium', timeStyle: 'short',
    }).format(item) : '';
  };
  const stateLabel = (value) => ({
    draft: 'En préparation', submitted: 'Soumise',
    pending_approval: 'Approbation attendue', approved: 'Approuvée',
    pending_payment: 'Paiement attendu', confirmed: 'Confirmée',
    in_progress: 'En cours', fulfilled: 'Réalisée',
    rejected: 'Refusée', cancelled: 'Annulée', expired: 'Expirée',
    blocked: 'Bloquée', action_required: 'Action requise',
    waiting: 'En attente', ready: 'Prête', complete: 'Terminée',
  })[value] || 'Situation non précisée';
  const finished = (r) => ['fulfilled', 'cancelled', 'rejected', 'expired'].includes(r.state);
  const sortDate = (r) => r.updated_at || r.created_at || '';
  const status = (r) => r.readiness_label || stateLabel(r.state);
  const link = (row, text) => {
    const anchor = el('a', 'mk-dossier__item-link', text || row.label);
    anchor.href = validUrl(row.web_url);
    return anchor;
  };
  const btn = (label, iconName, onClick, className = '') => {
    // Owner-bound callback stays here; only the visual action grammar is shared.
    const button = el('button', 'mk-action-button');
    button.type = 'button';
    button.dataset.variant = className === 'mk-dossier__submit' ? 'primary'
      : /^(Retirer|Révoquer|Retirer le lien|Lever le prérequis)$/.test(label)
        ? 'danger' : 'secondary';
    button.append(icon(iconName), document.createTextNode(label));
    button.addEventListener('click', onClick);
    return button;
  };
  const renderIcons = () => {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  };
  function submit(url, fields) {
    if (!csrf || validUrl(url) === '#') return;
    const form = el('form');
    form.method = 'post'; form.action = url + scopeSuffix; form.hidden = true;
    for (const [key, value] of Object.entries({
      csrfmiddlewaretoken: csrf, ...(fields || {}),
    })) {
      const input = el('input');
      input.type = 'hidden'; input.name = key; input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
  }
  function confirmAction(title, description, url, fields, requiresReason = false) {
    if (validUrl(url) === '#') return;
    const dialog = el('dialog', 'mk-dossier__dialog');
    const content = el('div', 'mk-dossier__dialog-inner');
    append(content, el('h2', '', title));
    append(content, el('p', 'mk-dossier__hint', description));
    const reason = el('input');
    if (requiresReason) {
      reason.type = 'text'; reason.maxLength = 280;
      reason.placeholder = 'Raison de la levée du prérequis';
      reason.setAttribute('aria-label', 'Raison obligatoire');
      reason.className = 'mk-dossier__reason';
      append(content, reason);
    }
    const actions = el('div', 'mk-dossier__dialog-actions');
    append(actions, btn('Annuler', 'x', () => dialog.close()));
    append(actions, btn('Confirmer', 'check', () => {
      if (requiresReason && !reason.value.trim()) {
        reason.focus(); return;
      }
      submit(url, {...fields, ...(requiresReason ? {reason: reason.value.trim()} : {})});
    }, 'mk-dossier__submit'));
    append(content, actions); append(dialog, content);
    append(root, dialog);
    dialog.addEventListener('close', () => dialog.remove(), {once: true});
    dialog.showModal(); renderIcons();
  }

  function journeyRow(row, {compact = false} = {}) {
    const article = el('article', 'mk-dossier__journey');
    append(article, icon('route'));
    const copy = el('div', 'mk-dossier__journey-copy');
    append(copy, link(row));
    const meta = [stateLabel(row.state)];
    if (row.readiness_label) meta.push('Situation : ' + row.readiness_label);
    if (row.hidden_dependency) meta.push('Une condition n’est pas visible');
    append(copy, el('p', 'mk-dossier__hint', meta.join(' · ')));
    if (!compact && row.next_action?.label) {
      append(copy, el('p', 'mk-dossier__next', row.next_action.label));
    }
    append(article, copy);
    if (row.capabilities?.includes('unlink')) {
      append(article, btn('Retirer', 'unlink', () =>
        confirmAction('Retirer la démarche du Dossier ?',
          'Le lien sera retiré ; la Journey ne sera ni supprimée ni annulée.',
          row.web_unlink_url, {})));
    } else {
      append(article, icon('chevron-right'));
    }
    return article;
  }
  function heading(text, hint) {
    append(stage, el('h2', '', text));
    if (hint) append(stage, el('p', 'mk-dossier__hint', hint));
  }
  function empty(title, detail) {
    const card = el('div', 'mk-dossier__empty');
    append(card, icon('folder-open'));
    append(card, el('strong', '', title));
    append(card, el('p', '', detail));
    append(stage, card);
  }
  function meter(value, label) {
    const node = el('div', 'mk-dossier__metric');
    append(node, el('strong', '', String(value)));
    append(node, el('span', '', label));
    return node;
  }
  function collaboration() {
    const assignments = Array.isArray(data.assignments) ? data.assignments : [];
    const mandates = Array.isArray(data.mandates) ? data.mandates : [];
    if (!assignments.length && !mandates.length) return;
    append(stage, el('h3', 'mk-dossier__subhead', 'Collaboration et responsabilités'));
    const panel = el('div', 'mk-dossier__collaboration');
    for (const assignment of assignments) {
      const row = el('div', 'mk-dossier__collab-row');
      append(row, icon('user-round'));
      append(row, el('span', '', assignment.label +
        (assignment.self ? ' · vous' : '') + ' · responsabilité opérationnelle'));
      if (assignment.capabilities?.includes('remove')) {
        append(row, btn('Retirer', 'user-minus', () =>
          confirmAction('Retirer cette responsabilité ?', 'Aucun mandat ne sera modifié.',
            assignment.web_remove_url, {})));
      }
      append(panel, row);
    }
    for (const mandate of mandates) {
      const row = el('div', 'mk-dossier__collab-row');
      append(row, icon('shield-check'));
      append(row, el('span', '', mandate.profile + ' · ' + mandate.role));
      if (mandate.capabilities?.includes('revoke')) {
        append(row, btn('Révoquer', 'shield-off', () =>
          confirmAction('Révoquer ce mandat ?', 'L’autorité sur ce Dossier sera retirée.',
            mandate.web_revoke_url, {})));
      }
      append(panel, row);
    }
    append(stage, panel);
    append(stage, el('p', 'mk-dossier__hint',
      'Une responsabilité n’accorde pas automatiquement une permission ; un mandat Dossier ne donne pas d’autorité sur les Journeys.'));
  }
  function overview() {
    heading('Vue d’ensemble', 'Une lecture opérationnelle du résultat attendu, sans pourcentage arbitraire.');
    const readiness = data.readiness || {};
    const focus = el('div', 'mk-dossier__focus');
    append(focus, icon(readiness.state === 'blocked' ? 'circle-alert' : 'activity'));
    const copy = el('div');
    append(copy, el('strong', '', readiness.label || 'Situation à confirmer'));
    if (readiness.next_action?.label) {
      append(copy, el('p', '', 'Prochaine intervention : ' + readiness.next_action.label));
      const row = byId.get(readiness.next_action.journey_id);
      if (row) append(copy, link(row, 'Ouvrir cette démarche'));
    } else {
      append(copy, el('p', '', readiness.partial
        ? 'La situation collective est partielle selon vos autorisations.'
        : 'Aucune prochaine intervention personnelle explicitement signalée.'));
    }
    if (readiness.hidden_signal) {
      append(copy, el('p', 'mk-dossier__hint', readiness.hidden_signal));
    }
    append(focus, copy); append(stage, focus);
    const stats = el('div', 'mk-dossier__metrics');
    append(stats, meter(rows.length, 'Démarches visibles'));
    append(stats, meter(rows.filter((r) => r.state === 'fulfilled').length, 'Réalisées'));
    append(stats, meter(rows.filter((r) => r.readiness_state === 'action_required').length, 'Action requise'));
    append(stats, meter(dependencies.filter((d) => d.state === 'active').length, 'Prérequis visibles actifs'));
    append(stage, stats);
    append(stage, el('h3', 'mk-dossier__subhead', 'Démarches du Dossier'));
    if (!rows.length) {
      empty('Aucune démarche visible liée',
        'Vous pouvez relier une Journey existante si le Dossier vous en donne l’autorité.');
    } else {
      for (const row of rows.slice(0, 7)) append(stage, journeyRow(row, {compact: true}));
      if (rows.length > 7) {
        append(stage, btn('Voir toutes les démarches', 'list', () => {
          state.view = 'list'; render();
        }));
      }
    }
    collaboration();
  }

  function filteredRows() {
    const q = fold(state.query);
    const result = rows.filter((row) => {
      if (q && !fold(row.label).includes(q)) return false;
      if (state.filter === 'action' && row.readiness_state !== 'action_required') return false;
      if (state.filter === 'waiting' && row.readiness_state !== 'waiting') return false;
      if (state.filter === 'blocked' && row.readiness_state !== 'blocked') return false;
      if (state.filter === 'fulfilled' && row.state !== 'fulfilled') return false;
      if (state.filter === 'undated' && !isUndated(row)) return false;
      if (state.filter === 'mine' &&
          !(data.readiness?.next_action?.journey_id === row.id)) return false;
      return true;
    });
    return result.sort((a, b) => {
      if (state.sort === 'name') return fold(a.label).localeCompare(fold(b.label), 'fr');
      if (state.sort === 'status') return stateLabel(a.state).localeCompare(stateLabel(b.state), 'fr');
      if (state.sort === 'action') {
        const first = a.readiness_state === 'action_required' ? 0 : 1;
        const second = b.readiness_state === 'action_required' ? 0 : 1;
        return first - second;
      }
      const fields = {
        created: 'created_at', started: 'started_at',
        fulfilled: 'fulfilled_at', expiry: 'expires_at',
      };
      if (fields[state.sort]) {
        const first = a[fields[state.sort]] || '';
        const second = b[fields[state.sort]] || '';
        if (!first && second) return 1;
        if (!second && first) return -1;
        return state.sort === 'created' || state.sort === 'fulfilled'
          ? second.localeCompare(first) : first.localeCompare(second);
      }
      return sortDate(b).localeCompare(sortDate(a));
    });
  }
  function dropdown(label, options, value, setValue) {
    const wrapper = el('label', '', label);
    const input = el('select');
    for (const [key, title] of options) {
      const opt = el('option', '', title); opt.value = key; append(input, opt);
    }
    input.value = value;
    input.addEventListener('change', () => { setValue(input.value); render(); });
    append(wrapper, input);
    return wrapper;
  }
  function renderList() {
    heading('Toutes les démarches', 'La recherche et le tri opèrent localement sur les démarches visibles acquises.');
    const controls = el('div', 'mk-dossier__filters');
    const searchLabel = el('label', '', 'Rechercher');
    const input = el('input'); input.type = 'search';
    input.placeholder = 'Nom de la démarche'; input.value = state.query;
    append(searchLabel, input); append(controls, searchLabel);
    append(controls, dropdown('Situation', [
      ['all', 'Toutes'], ['action', 'Action requise'],
      ['waiting', 'En attente'], ['blocked', 'Bloquées'],
      ['fulfilled', 'Réalisées'], ['undated', 'Sans date de parcours'],
      ['mine', 'Prochaine intervention personnelle'],
    ], state.filter, (value) => { state.filter = value; }));
    append(controls, dropdown('Trier', [
      ['recent', 'Modification récente'], ['name', 'Nom A–Z'],
      ['status', 'État'], ['action', 'Action utile'],
      ['created', 'Date de création'], ['started', 'Date de début'],
      ['fulfilled', 'Date de réalisation'], ['expiry', 'Expiration indiquée'],
    ], state.sort, (value) => { state.sort = value; }));
    append(stage, controls);
    const list = el('div', 'mk-dossier__journeys');
    append(stage, list);
    function redraw() {
      list.replaceChildren();
      const results = filteredRows();
      append(list, el('p', 'mk-dossier__hint',
        results.length + ' démarche(s) visibles correspondent aux critères.'));
      if (!results.length) {
        append(list, el('div', 'mk-dossier__empty',
          'Aucune démarche correspondant à ces critères.'));
      }
      for (const row of results) append(list, journeyRow(row));
      renderIcons();
    }
    input.addEventListener('input', () => { state.query = input.value; redraw(); });
    redraw();
  }
  const eventsFor = (row) => [
    ['created_at', 'Démarche créée', 'creation'],
    ['submitted_at', 'Soumise', 'actual'],
    ['confirmed_at', 'Confirmée', 'actual'],
    ['started_at', 'Commencée', 'actual'],
    ['fulfilled_at', 'Réalisée', 'actual'],
    ['expires_at', 'Expiration indiquée', 'deadline'],
  ].flatMap(([key, label, kind]) => {
    const d = date(row[key]);
    return d ? [{at: d, row, label, kind}] : [];
  });
  const isUndated = (row) => ![
    'submitted_at', 'confirmed_at', 'started_at', 'fulfilled_at', 'expires_at',
  ].some((field) => !!date(row[field]));
  function renderTimeline() {
    heading('Chronologie des démarches',
      'Les dates ci-dessous sont des faits de Journey, pas des dépendances implicites.');
    const controls = el('div', 'mk-dossier__filters');
    append(controls, dropdown('Échelle', [
      ['week', 'Semaine'], ['month', 'Mois'], ['quarter', 'Trimestre'],
    ], state.timeScale, (value) => { state.timeScale = value; }));
    append(controls, btn('Aujourd’hui', 'calendar-days', () => {
      document.querySelector('[data-today-marker]')?.scrollIntoView({
        behavior: 'smooth', block: 'center',
      });
    }));
    append(stage, controls);
    const events = rows.flatMap(eventsFor).sort((a, b) => a.at - b.at);
    const today = new Date();
    const todayText = new Intl.DateTimeFormat('fr-FR', {dateStyle: 'long'}).format(today);
    const line = el('ol', 'mk-dossier__timeline');
    let previousGroup = '';
    let markedToday = false;
    for (const event of events) {
      const dateValue = event.at;
      const scaleKey = state.timeScale === 'week'
        ? Math.floor(dateValue.getTime() / (7 * 86400000)).toString()
        : state.timeScale === 'quarter'
          ? dateValue.getFullYear() + '-T' + Math.ceil((dateValue.getMonth() + 1) / 3)
          : dateValue.getFullYear() + '-' + dateValue.getMonth();
      if (scaleKey !== previousGroup) {
        const divider = el('li', 'mk-dossier__timeline-group',
          state.timeScale === 'quarter'
            ? 'Trimestre ' + Math.ceil((dateValue.getMonth() + 1) / 3) +
              ' · ' + dateValue.getFullYear()
            : new Intl.DateTimeFormat('fr-FR', {month: 'long', year: 'numeric'}).format(dateValue));
        append(line, divider); previousGroup = scaleKey;
      }
      if (!markedToday && dateValue > today) {
        const todayNode = el('li', 'mk-dossier__timeline-today', 'Aujourd’hui · ' + todayText);
        todayNode.dataset.todayMarker = '';
        append(line, todayNode); markedToday = true;
      }
      const li = el('li', 'mk-dossier__timeline-entry');
      append(li, el('time', '', dateLabel(event.at)));
      const text = el('div');
      append(text, el('strong', '', event.label));
      append(text, link(event.row));
      append(li, text);
      append(line, li);
    }
    if (!markedToday) {
      const todayNode = el('li', 'mk-dossier__timeline-today', 'Aujourd’hui · ' + todayText);
      todayNode.dataset.todayMarker = ''; append(line, todayNode);
    }
    append(stage, line);
    const undated = rows.filter(isUndated);
    if (undated.length) {
      append(stage, el('h3', 'mk-dossier__subhead', 'Sans autre date de parcours'));
      append(stage, el('p', 'mk-dossier__hint',
        'Une création enregistrée n’indique pas automatiquement un rendez-vous ou une échéance.'));
      for (const row of undated) append(stage, journeyRow(row, {compact: true}));
    }
    if (!rows.length) empty('Chronologie vide', 'Aucune démarche visible n’est liée.');
  }

  function graphPositions() {
    const incoming = new Map(rows.map((r) => [r.id, []]));
    for (const dep of dependencies) {
      if (dep.state !== 'active' || !incoming.has(dep.dependent_journey_id) ||
          !incoming.has(dep.required_journey_id)) continue;
      incoming.get(dep.dependent_journey_id).push(dep.required_journey_id);
    }
    const cache = new Map();
    const depth = (id, seen = new Set()) => {
      if (cache.has(id)) return cache.get(id);
      if (seen.has(id)) return 0; // Never draw an inferred cycle.
      const next = new Set(seen); next.add(id);
      const value = Math.min(10, (incoming.get(id) || []).reduce(
        (max, required) => Math.max(max, depth(required, next) + 1), 0,
      ));
      cache.set(id, value);
      return value;
    };
    const layers = new Map();
    for (const row of rows) {
      const level = depth(row.id);
      if (!layers.has(level)) layers.set(level, []);
      layers.get(level).push(row);
    }
    const positions = new Map();
    const maxLayer = Math.max(0, ...layers.keys());
    const maxCount = Math.max(1, ...[...layers.values()].map((group) => group.length));
    for (const [layer, group] of layers) {
      group.sort((a, b) => fold(a.label).localeCompare(fold(b.label), 'fr'));
      group.forEach((row, index) => positions.set(row.id, {
        x: 35 + layer * 245, y: 35 + index * 118,
      }));
    }
    return {positions, width: Math.max(440, (maxLayer + 1) * 245 + 35),
      height: Math.max(260, maxCount * 118 + 25)};
  }
  function renderGraph() {
    heading('Dépendances causales',
      'Une flèche signifie : la démarche requise doit être satisfaite avant la démarche dépendante.');
    if (data.graph_partial || data.readiness?.partial) {
      const note = el('div', 'mk-dossier__partial',
        'Vue potentiellement partielle : certaines conditions ne sont pas visibles selon vos autorisations.');
      append(stage, note);
    }
    if (!dependencies.length) {
      empty('Aucune dépendance visible définie',
        'Aucun lien causal n’est inventé à partir de l’ordre des démarches ou des dates.');
    } else {
      const toolbar = el('div', 'mk-dossier__graph-toolbar');
      const graph = el('div', 'mk-dossier__graph-frame');
      const {positions, width, height} = graphPositions();
      const svg = svgEl('svg', {
        viewBox: '0 0 ' + width + ' ' + height,
        role: 'img', 'aria-label': 'Graphe des dépendances visibles',
        tabindex: '0',
      });
      const defs = svgEl('defs');
      const markerId = 'mk-arrow-' + data.identity.id.replace(/[^a-z0-9]/gi, '');
      const marker = svgEl('marker', {
        id: markerId, markerWidth: 7, markerHeight: 7,
        refX: 6, refY: 3.5, orient: 'auto', viewBox: '0 0 7 7',
      });
      marker.appendChild(svgEl('path', {d: 'M0 0 L7 3.5 L0 7 Z',
        fill: '#8582a0'}));
      defs.appendChild(marker); svg.appendChild(defs);
      const viewport = svgEl('g');
      const transform = () => viewport.setAttribute('transform',
        'translate(' + state.panX + ' ' + state.panY + ') scale(' + state.zoom + ')');
      transform(); svg.appendChild(viewport);

      for (const dep of dependencies) {
        const required = positions.get(dep.required_journey_id);
        const dependent = positions.get(dep.dependent_journey_id);
        if (!required || !dependent) continue;
        const x1 = required.x + 194, y1 = required.y + 33;
        const x2 = dependent.x - 8, y2 = dependent.y + 33;
        const d = 'M ' + x1 + ' ' + y1 + ' C ' +
          (x1 + 44) + ' ' + y1 + ', ' + (x2 - 44) + ' ' + y2 +
          ', ' + x2 + ' ' + y2;
        const path = svgEl('path', {
          d, fill: 'none',
          stroke: dep.state === 'waived' ? '#b0a1c6' : '#8582a0',
          'stroke-width': 2, 'stroke-dasharray': dep.state === 'waived' ? '5 4' : '',
          'marker-end': 'url(#' + markerId + ')',
        });
        viewport.appendChild(path);
        const hit = svgEl('path', {
          d, fill: 'none', stroke: 'transparent', 'stroke-width': 18,
          role: 'button', tabindex: '0', cursor: 'pointer',
          'aria-label': 'Prérequis : ' + (byId.get(dep.required_journey_id)?.label || '') +
            ' avant ' + (byId.get(dep.dependent_journey_id)?.label || ''),
        });
        const selected = () => {
          const message = dep.state === 'waived' ? 'Prérequis levé'
            : dep.satisfied ? 'Prérequis satisfait' : 'Prérequis à satisfaire';
          detail.textContent = message + ' · ' +
            (byId.get(dep.required_journey_id)?.label || '') + ' → ' +
            (byId.get(dep.dependent_journey_id)?.label || '');
        };
        hit.addEventListener('click', selected);
        hit.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault(); selected();
          }
        });
        viewport.appendChild(hit);
      }
      for (const row of rows) {
        const p = positions.get(row.id);
        if (!p) continue;
        const a = svgEl('a', {
          href: validUrl(row.web_url),
          'aria-label': 'Ouvrir ' + row.label,
        });
        a.appendChild(svgEl('rect', {
          x: p.x, y: p.y, width: 194, height: 70, rx: 12,
          fill: row.readiness_state === 'action_required' ? '#f7f2ff' : '#fff',
          stroke: row.readiness_state === 'action_required' ? '#5232db' : '#d4cfdf',
          'stroke-width': 1.5,
        }));
        a.appendChild(svgEl('text', {
          x: p.x + 12, y: p.y + 27, 'font-size': 12, 'font-weight': 700,
          fill: '#1e2040',
        }, row.label.length > 25 ? row.label.slice(0, 23) + '…' : row.label));
        a.appendChild(svgEl('text', {
          x: p.x + 12, y: p.y + 49, 'font-size': 10, fill: '#737082',
        }, status(row)));
        a.appendChild(svgEl('title', {}, row.label + ' · ' + status(row)));
        viewport.appendChild(a);
      }
      const zoom = (factor) => {
        state.zoom = Math.max(.4, Math.min(2.5, state.zoom * factor));
        transform();
      };
      append(toolbar, btn('Zoom +', 'zoom-in', () => zoom(1.2)));
      append(toolbar, btn('Zoom −', 'zoom-out', () => zoom(1 / 1.2)));
      append(toolbar, btn('Recentrer', 'focus', () => {
        state.zoom = 1; state.panX = 0; state.panY = 0; transform();
      }));
      append(stage, toolbar);
      let dragging = null;
      svg.addEventListener('pointerdown', (event) => {
        if (event.target.closest('a') || event.target.getAttribute('role') === 'button') return;
        dragging = {x: event.clientX, y: event.clientY,
          oldX: state.panX, oldY: state.panY};
        svg.setPointerCapture(event.pointerId);
      });
      svg.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        const bounds = svg.getBoundingClientRect();
        const unit = width / Math.max(1, bounds.width);
        state.panX = dragging.oldX + (event.clientX - dragging.x) * unit;
        state.panY = dragging.oldY + (event.clientY - dragging.y) * unit;
        transform();
      });
      svg.addEventListener('pointerup', () => { dragging = null; });
      svg.addEventListener('pointercancel', () => { dragging = null; });
      svg.addEventListener('wheel', (event) => {
        event.preventDefault(); zoom(event.deltaY > 0 ? .9 : 1.1);
      }, {passive: false});
      svg.addEventListener('keydown', (event) => {
        if (event.target !== svg) return;
        const delta = 22;
        if (event.key === 'ArrowLeft') state.panX -= delta;
        else if (event.key === 'ArrowRight') state.panX += delta;
        else if (event.key === 'ArrowUp') state.panY -= delta;
        else if (event.key === 'ArrowDown') state.panY += delta;
        else if (event.key === '+') zoom(1.2);
        else if (event.key === '-') zoom(.83);
        else return;
        event.preventDefault(); transform();
      });
      append(graph, svg);
      append(stage, graph);
      const detail = el('p', 'mk-dossier__graph-detail',
        'Sélectionnez une flèche pour comprendre un prérequis, ou une démarche pour l’ouvrir.');
      append(stage, detail);
    }
    append(stage, el('h3', 'mk-dossier__subhead', 'Lecture accessible des dépendances'));
    if (!dependencies.length) return;
    const list = el('ul', 'mk-dossier__dep-list');
    for (const dep of dependencies) {
      const required = byId.get(dep.required_journey_id);
      const dependent = byId.get(dep.dependent_journey_id);
      if (!required || !dependent) continue;
      const item = el('li', 'mk-dossier__dep-item');
      const text = el('p');
      append(text, link(required));
      append(text, document.createTextNode(' est requis avant '));
      append(text, link(dependent));
      append(item, text);
      append(item, el('p', 'mk-dossier__hint',
        dep.state === 'waived' ? 'Prérequis levé'
          : dep.satisfied ? 'Prérequis satisfait' : 'Prérequis à satisfaire'));
      if (dep.capabilities?.includes('remove')) {
        append(item, btn('Retirer le lien', 'unlink', () =>
          confirmAction('Retirer cette dépendance ?',
            'Les démarches restent liées au Dossier.',
            dep.web_remove_url, {})));
      }
      if (dep.capabilities?.includes('waive')) {
        append(item, btn('Lever le prérequis', 'check-circle', () =>
          confirmAction('Lever ce prérequis ?',
            'La levée exige une raison. Elle ne termine pas la Journey requise.',
            dep.web_waive_url, {}, true)));
      }
      append(list, item);
    }
    append(stage, list);
  }
  function render() {
    stage.replaceChildren();
    for (const tab of root.querySelectorAll('[data-dossier-view]')) {
      tab.setAttribute('aria-pressed', String(tab.dataset.dossierView === state.view));
    }
    if (state.view === 'list') renderList();
    else if (state.view === 'timeline') renderTimeline();
    else if (state.view === 'dependencies') renderGraph();
    else overview();
    renderIcons();
  }
  for (const tab of root.querySelectorAll('[data-dossier-view]')) {
    tab.addEventListener('click', () => {
      state.view = tab.dataset.dossierView; render();
    });
  }
  for (const open of root.querySelectorAll('[data-dialog-open]')) {
    open.addEventListener('click', () => {
      const target = document.getElementById(open.dataset.dialogOpen);
      if (target && typeof target.showModal === 'function') target.showModal();
    });
  }
  for (const close of root.querySelectorAll('[data-dialog-close]')) {
    close.addEventListener('click', () => close.closest('dialog')?.close());
  }
  render();
})();
