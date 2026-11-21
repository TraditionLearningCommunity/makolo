/* Preview only the canonical public Passport projection, when authorized. */
(() => {
  'use strict';
  const cache = new Map();
  async function populate(link) {
    if (!link?.dataset.publicProfileId) return;
    const id = link.dataset.publicProfileId;
    if (!cache.has(id)) {
      const path = '/api/v1/accounts/public-profiles/' +
        encodeURIComponent(id) + '/';
      cache.set(id, fetch(path, {credentials: 'same-origin'})
        .then(response => response.ok ? response.json() : null)
        .then(body => body?.data?.profile || null)
        .catch(() => null));
    }
    const profile = await cache.get(id);
    if (!profile || !link.isConnected) return;
    const card = link.querySelector('.mk-point-author-popover');
    if (!card) return;
    card.replaceChildren();
    const name = document.createElement('strong');
    name.textContent = profile.name || '';
    card.append(name);
    if (profile.headline) {
      const line = document.createElement('small');
      line.textContent = profile.headline;
      card.append(line);
    }
    if (profile.bio) {
      const bio = document.createElement('div');
      bio.className = 'mk-author-bio';
      bio.textContent = profile.bio;
      card.append(bio);
    }
  }
  document.addEventListener('pointerover', event => {
    const link = event.target.closest?.('[data-public-profile-id]');
    if (link) void populate(link);
  });
  document.addEventListener('focusin', event => {
    const link = event.target.closest?.('[data-public-profile-id]');
    if (link) void populate(link);
  });
})();
