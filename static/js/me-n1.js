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
    if (!id || !label) return;
    // Existing family roots contain the preview. Newly inserted rows retain
    // identity as an attribute to suppress accidental duplicates.
    const isConsiderations = host.dataset.meTerritory === 'considerations';
    if (isConsiderations) {
      let entry;
      if (host.classList.contains('mk-me-n1-chips')) {
        entry = node('span', '', label);
      } else {
        const ownerHref = family === 'watches'
          ? item.links?.web : host.dataset.meOwnerHref;
        entry = ownerHref && ownerHref.startsWith('/') && !ownerHref.startsWith('//')
          ? node('a', 'mk-me-n1-appended', label)
          : node('span', 'mk-me-n1-appended', label);
        if (entry.tagName === 'A') entry.href = ownerHref;
      }
      if (family === 'bookmarks') {
        // Same filled saved-orbit state as Discover. Icon conveys status,
        // not a second save/un-save action owned by Discovery.
        const status = node('span', 'mk-me-saved-orbit');
        status.setAttribute('role', 'img');
        status.setAttribute('aria-label', 'Enregistré');
        const title = node('span', 'mk-me-n1-saved-title', label);
        const chevron = node('span', 'mk-me-n1-saved-chevron', '›');
        chevron.setAttribute('aria-hidden', 'true');
        const imageBinding = item.media_bindings?.find(binding =>
          binding?.purpose === 'RECOGNIZE' &&
          binding?.target?.kind === 'activity' &&
          String(binding?.target?.id) === String(item.activity?.id) &&
          binding?.resource?.kind === 'presentation_media_use' &&
          ['image/jpeg', 'image/png'].includes(binding?.resource?.mime_type) &&
          typeof binding?.resource?.url === 'string' &&
          binding.resource.url.startsWith('/') &&
          !binding.resource.url.startsWith('//') &&
          !binding.resource.url.includes('?')
        );
        if (imageBinding) {
          const preview = node('img', 'mk-me-n1-recognition');
          preview.src = imageBinding.resource.url;
          preview.alt = '';
          preview.width = 72;
          preview.height = 56;
          preview.loading = 'lazy';
          preview.decoding = 'async';
          entry.replaceChildren(status, title, preview, chevron);
        } else {
          entry.replaceChildren(status, title, chevron);
        }
      }
      entry.dataset.meId = id;
      host.append(entry);
      return;
    }
    const groupUrl = family === 'groups' ? item.links?.web : null;
    const safeGroupUrl = typeof groupUrl === 'string' &&
      groupUrl.startsWith('/') && !groupUrl.startsWith('//');
    const row = node(safeGroupUrl ? 'a' : 'div', 'mk-me-n1-person-row');
    if (safeGroupUrl) row.href = groupUrl;
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

  function renderedIds(host) {
    const seen = new Set();
    if (host.matches('.mk-me-n1-group')) {
      let next = host.nextElementSibling;
      while (next && !next.matches('.mk-me-n1-group')) {
        if (next.dataset.meId) seen.add(next.dataset.meId);
        next = next.nextElementSibling;
      }
    } else {
      host.querySelectorAll('[data-me-id]').forEach(el => {
        if (el.dataset.meId) seen.add(el.dataset.meId);
      });
    }
    return seen;
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
          !Number.isSafeInteger(part.next_offset) ||
          part.next_offset < offset ||
          (part.has_more && part.items.length === 0)) {
        throw new Error('Invalid owner continuation');
      }
      const seen = renderedIds(host);
      for (const item of part.items) {
        const id = String(item.id || '');
        if (!id || seen.has(id)) continue;
        seen.add(id);
        render(host, item);
      }
      host.dataset.meLoaded = String(part.next_offset);
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
