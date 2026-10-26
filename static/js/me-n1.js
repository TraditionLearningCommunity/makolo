/* Moi N1 — private, progressive enhancement; no business state is created here. */
(() => {
  'use strict';
  const root = document.querySelector('.mk-me-n1');
  const sentinel = document.getElementById('me-n1-scroll-sentinel');
  if (!root || !sentinel) return;
  const families = [...root.querySelectorAll('[data-me-territory][data-me-family]')]
    .filter(el => el.dataset.meMore === 'true');
  let loading = false;
  let stopped = false;
  let retryCount = 0;

  function safeText(value) { return typeof value === 'string' ? value : ''; }
  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = safeText(value);
    return node;
  }

  function row(host, family, item) {
    if (host.dataset.meTerritory === 'considerations') {
      let title = '';
      if (family === 'interests') title = item.topic?.label;
      if (family === 'open_to') title = [item.label, item.topic?.label].filter(Boolean).join(' · ');
      if (family === 'watches') title = item.name;
      if (family === 'bookmarks') title = item.activity?.title;
      if (family === 'followed_spaces') title = item.space?.name;
      if (family === 'followed_profiles') title = item.profile?.display_name;
      if (!title) return;
      if (host.classList.contains('mk-me-n1-chips')) {
        host.append(element('span', '', title));
      } else {
        // A deep link is provided only by the existing owner route in N1.
        host.append(element('span', 'mk-me-n1-appended', title));
      }
      return;
    }
    const wrapper = element('div', 'mk-me-n1-person-row');
    const icon = element('span', 'mk-me-n1-monogram', (
      safeText(item.name || item.title || item.proof_type_label).slice(0,1) || '•'
    ).toUpperCase());
    icon.setAttribute('aria-hidden', 'true');
    const details = element('span', 'mk-me-n1-row-copy');
    details.append(element('strong', '', item.name || item.title || item.proof_type_label));
    const sub = item.space?.name || item.asset_kind_label || item.status_label ||
      item.credential_type_label || '';
    if (sub) details.append(element('small', '', sub));
    wrapper.append(icon, details);
    // Insert adjacent to the other family rows, not at the end of another family.
    const nextGroup = host.nextElementSibling;
    if (nextGroup) host.parentNode.insertBefore(wrapper, nextGroup);
    else host.parentNode.append(wrapper);
  }

  async function loadFamily(host) {
    const territory = host.dataset.meTerritory;
    const family = host.dataset.meFamily;
    let count = Number(host.dataset.meLoaded || 6);
    if (!Number.isInteger(count) || count < 0) count = 6;
    const query = new URLSearchParams({offset: String(count), limit: '24'});
    const response = await fetch('/api/v1/me/preview/' + encodeURIComponent(territory) + '/?' + query, {
      credentials: 'same-origin',
      headers: {'Accept': 'application/json'},
      cache: 'no-store'
    });
    if (!response.ok) throw new Error('N1 continuation unavailable');
    const data = (await response.json()).data;
    const part = data?.collections?.[family];
    if (data?.territory !== territory || data?.offset !== count || !Array.isArray(part?.items)) {
      throw new Error('Invalid N1 continuation');
    }
    const items = part.items;
    for (const item of items) row(host, family, item);
    host.dataset.meLoaded = String(count + items.length);
    host.dataset.meMore = part.has_more ? 'true' : 'false';
  }

  async function load() {
    if (loading || stopped) return;
    const host = families.find(el => el.isConnected && el.dataset.meMore === 'true');
    if (!host) {
      stopped = true;
      sentinel.textContent = 'Vous avez tout exploré';
      observer.disconnect();
      return;
    }
    loading = true;
    sentinel.textContent = '';
    try {
      await loadFamily(host);
      retryCount = 0;
    } catch (_) {
      retryCount++;
      // Never claim completion when the server cannot confirm exhaustion.
      sentinel.textContent = 'Impossible de charger la suite.';
      if (retryCount >= 2) {
        stopped = true;
        observer.disconnect();
        const retry = element('button', 'mk-me-n1-retry', 'Réessayer');
        retry.type = 'button';
        retry.addEventListener('click', () => {
          stopped = false;
          retryCount = 0;
          sentinel.textContent = '';
          retry.remove();
          observer.observe(sentinel);
          void load();
        }, {once: true});
        sentinel.append(retry);
      }
    } finally {
      loading = false;
    }
    if (!stopped && sentinel.getBoundingClientRect().top < window.innerHeight + 480) {
      queueMicrotask(() => { void load(); });
    }
  }
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) void load();
  }, {rootMargin: '480px'});
  observer.observe(sentinel);
})();
