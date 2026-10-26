/* Moi N1 — same private owner collections as Flutter; no synthetic depth. */
(() => {
  'use strict';
  const root = document.querySelector('.mk-me-n1');
  const sentinel = document.getElementById('me-n1-scroll-sentinel');
  if (!root || !sentinel || !('IntersectionObserver' in window)) return;

  const all = [...root.querySelectorAll('[data-me-territory][data-me-family]')];
  const expectedProfile = root.dataset.meProfile || '';
  let busy = false;
  let stopped = false;
  let failed = false;

  function node(tag, klass, label) {
    const item = document.createElement(tag);
    if (klass) item.className = klass;
    if (label != null) item.textContent = String(label);
    return item;
  }

  function labelFor(family, item) {
    switch (family) {
      case 'interests': return item.topic?.label;
      case 'open_to': return [item.label, item.topic?.label].filter(Boolean).join(' · ');
      case 'watches': return item.name;
      case 'bookmarks': return item.activity?.title;
      case 'followed_spaces': return item.space?.name;
      case 'followed_profiles': return item.profile?.display_name;
      default: return item.name || item.title || item.proof_type_label;
    }
  }

  function render(host, item) {
    const family = host.dataset.meFamily;
    const id = String(item.id || '');
    const label = labelFor(family, item);
    if (!id || !label || [...host.parentElement.querySelectorAll('[data-me-id]')]
      .some(el => el.closest('[data-me-family]') === host && el.dataset.meId === id)) return;
    // Existing family roots contain the preview. Newly inserted rows retain
    // identity as an attribute to suppress accidental duplicates.
    const isConsiderations = host.dataset.meTerritory === 'considerations';
    if (isConsiderations) {
      let entry;
      if (host.classList.contains('mk-me-n1-chips')) {
        entry = node('span', '', label);
      } else {
        entry = node('span', 'mk-me-n1-appended', label);
      }
      entry.dataset.meId = id;
      host.append(entry);
      return;
    }
    const row = node('div', 'mk-me-n1-person-row');
    row.dataset.meId = id;
    const icon = node('span', 'mk-me-n1-monogram',
      (String(label).trim().slice(0, 1) || '•').toUpperCase());
    icon.setAttribute('aria-hidden', 'true');
    const copy = node('span', 'mk-me-n1-row-copy');
    copy.append(node('strong', '', label));
    const detail = item.space?.name || item.asset_kind_label ||
      item.credential_type_label || item.status_label;
    if (detail) copy.append(node('small', '', detail));
    row.append(icon, copy);
    // H3 is the existing group header. Insert just before the next family,
    // never between or ahead of rows already visible.
    let next = host.nextElementSibling;
    while (next && !next.matches('.mk-me-n1-group')) next = next.nextElementSibling;
    host.parentElement.insertBefore(row, next);
  }

  function hasMore() {
    return all.some(host => host.dataset.meMore === 'true');
  }

  async function loadOne() {
    if (busy || failed || stopped || document.hidden) return;
    const host = all.find(el => el.isConnected && el.dataset.meMore === 'true');
    if (!host) {
      stopped = true;
      sentinel.textContent = 'Vous avez tout exploré';
      observer.disconnect();
      return;
    }
    busy = true;
    sentinel.textContent = '';
    const territory = host.dataset.meTerritory;
    const family = host.dataset.meFamily;
    const offset = Number(host.dataset.meLoaded);
    try {
      if (!Number.isSafeInteger(offset) || offset < 0) throw new Error('Bad prefix');
      const query = new URLSearchParams({family, offset: String(offset), limit: '24'});
      const result = await fetch(
        '/api/v1/me/preview/' + encodeURIComponent(territory) + '/?' + query,
        {credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store'}
      );
      if (!result.ok) throw new Error('Owner unavailable');
      const data = (await result.json()).data;
      const part = data?.collection;
      if (data?.actor?.type !== 'profile' ||
          (expectedProfile && data?.actor?.id !== expectedProfile) ||
          data?.territory !== territory || data?.family !== family ||
          data?.offset !== offset || !Array.isArray(part?.items) ||
          typeof part.has_more !== 'boolean' ||
          !Number.isSafeInteger(part.count) ||
          (part.has_more && part.items.length === 0)) {
        throw new Error('Invalid owner continuation');
      }
      const seen = new Set([...host.querySelectorAll('[data-me-id]')]
        .map(el => el.dataset.meId));
      for (const item of part.items) {
        const id = String(item.id || '');
        if (!id || seen.has(id)) continue;
        seen.add(id);
        render(host, item);
      }
      host.dataset.meLoaded = String(offset + part.items.length);
      host.dataset.meMore = String(part.has_more);
    } catch (_) {
      failed = true;
      const retry = node('button', 'mk-me-n1-retry', 'Réessayer');
      retry.type = 'button';
      retry.addEventListener('click', () => {
        failed = false;
        sentinel.textContent = '';
        void loadOne();
      }, {once: true});
      sentinel.replaceChildren(node('span', '', 'Impossible de charger la suite. '), retry);
    } finally {
      busy = false;
    }
    if (!failed && !stopped) {
      if (!hasMore()) {
        stopped = true;
        sentinel.textContent = 'Vous avez tout exploré';
        observer.disconnect();
      } else if (sentinel.getBoundingClientRect().top < window.innerHeight + 480) {
        queueMicrotask(() => void loadOne());
      }
    }
  }

  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) void loadOne();
  }, {rootMargin: '480px'});
  observer.observe(sentinel);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !stopped && !failed) void loadOne();
  });
})();
