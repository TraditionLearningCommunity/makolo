(() => {
  'use strict';
  const root = document.querySelector('[data-notification-inbox]');
  if (!root) return;
  const api = new URL(root.dataset.apiUrl, window.location.origin);
  const list = root.querySelector('[data-notification-list]');
  const status = root.querySelector('[data-notification-status]');
  const retry = root.querySelector('[data-notification-retry]');
  const sentinel = root.querySelector('[data-notification-sentinel]');
  const token = root.querySelector('[data-notification-token] input[name=csrfmiddlewaretoken]')?.value;
  const unreadFilter = root.dataset.filter === 'unread';
  const known = new Set(Array.from(list.querySelectorAll('[data-notification-id]'), node => node.dataset.notificationId));
  const timeFormat = new Intl.RelativeTimeFormat('fr', { numeric: 'auto' });
  let next = api.pathname + (unreadFilter ? '?filter=unread' : '');
  let busy = false;
  let ended = false;
  let observer;

  function timeLabel(value) {
    const date = new Date(value);
    const seconds = Math.round((date.getTime() - Date.now()) / 1000);
    if (!Number.isFinite(seconds)) return '';
    const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
    for (const [unit, size] of units) {
      if (Math.abs(seconds) >= size) return timeFormat.format(Math.round(seconds / size), unit);
    }
    return 'À l’instant';
  }

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function appendRow(row) {
    const id = String(row.id || '');
    if (!id || known.has(id)) return;
    known.add(id);
    const article = el('article', null, 'mk-notification-item' + (row.is_read ? '' : ' is-unread'));
    article.dataset.notificationId = id;
    article.append(el('span', null, 'mk-notification-dot'));
    const copy = el('div', null, 'mk-notification-copy');
    const meta = el('div', null, 'mk-notification-meta');
    meta.append(el('span', row.category || 'Information'));
    const time = el('time', timeLabel(row.created_at));
    if (row.created_at) time.dateTime = row.created_at;
    meta.append(time);
    copy.append(meta, el('h2', row.title || 'Notification'), el('p', row.message || ''));
    const actions = el('div', null, 'mk-notification-actions');
    const url = typeof row.action_url === 'string' ? row.action_url : '';
    const localAction = url.startsWith('/') && !url.startsWith('//') && !url.includes('\\');
    const navigation = row.navigation;
    const ownerHandoff = navigation && (
      ['conversation', 'access', 'journey', 'occurrence'].includes(navigation.target)
      || typeof navigation.access_id === 'string'
      || typeof navigation.journey_id === 'string'
    );
    if (localAction || ownerHandoff) {
      const open = el('a', 'Ouvrir');
      open.href = '/notifications/' + encodeURIComponent(id) + '/open/';
      actions.append(open);
    }
    if (!row.is_read) {
      const form = el('form', null, 'mk-notification-read-form');
      form.method = 'post';
      form.action = '/notifications/' + encodeURIComponent(id) + '/read/';
      form.dataset.readId = id;
      const csrf = el('input');
      csrf.type = 'hidden'; csrf.name = 'csrfmiddlewaretoken'; csrf.value = token || '';
      form.append(csrf, el('button', 'Marquer comme lue'));
      form.querySelector('button').type = 'submit';
      actions.append(form);
    }
    copy.append(actions);
    article.append(copy);
    list.append(article);
  }

  async function load() {
    if (busy || ended || !next) return;
    busy = true;
    retry.hidden = true;
    status.textContent = 'Chargement…';
    try {
      const target = new URL(next, window.location.origin);
      if (target.pathname !== api.pathname) throw new Error('Invalid continuation');
      const response = await fetch(api.pathname + target.search, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Fetch failed');
      const page = await response.json();
      if (!Array.isArray(page.results)) throw new Error('Invalid page');
      const total = root.querySelector('[data-notification-total]');
      const unread = root.querySelector('[data-notification-unread]');
      if (total && Number.isInteger(page.total_count)) total.textContent = String(page.total_count);
      if (unread && Number.isInteger(page.unread_count)) unread.textContent = String(page.unread_count);
      page.results.forEach(appendRow);
      const empty = root.querySelector('[data-notification-empty]');
      if (empty && known.size > 0) empty.remove();
      next = typeof page.next === 'string' ? page.next : null;
      ended = !next;
      status.textContent = ended ? (known.size ? 'Fin des notifications' : '') : '';
      if (ended) observer?.disconnect();
    } catch (_) {
      status.textContent = 'Chargement indisponible.';
      retry.hidden = false;
    } finally {
      busy = false;
    }
  }

  retry.addEventListener('click', load);
  list.addEventListener('submit', async event => {
    const form = event.target.closest('form[data-read-id]');
    if (!form || !token) return;
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      const result = await fetch('/api/v1/notifications/' + encodeURIComponent(form.dataset.readId) + '/read/', {
        method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': token, Accept: 'application/json' },
      });
      if (!result.ok) throw new Error('Read not confirmed');
      const article = form.closest('[data-notification-id]');
      article?.classList.remove('is-unread');
      form.remove();
      const unread = root.querySelector('[data-notification-unread]');
      if (unread) unread.textContent = String(Math.max(0, Number(unread.textContent || 0) - 1));
      if (unreadFilter) article?.remove();
    } catch (_) {
      button.disabled = false;
      status.textContent = 'Lecture non confirmée.';
    }
  });
  if ('IntersectionObserver' in window) {
    observer = new IntersectionObserver(entries => {
      if (entries.some(item => item.isIntersecting)) load();
    }, { rootMargin: '500px' });
    observer.observe(sentinel);
  } else {
    window.addEventListener('scroll', () => {
      if (sentinel.getBoundingClientRect().top < window.innerHeight + 500) load();
    }, { passive: true });
  }
  load();
})();
