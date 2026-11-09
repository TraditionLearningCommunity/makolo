(() => {
  const boundRoots = new WeakSet();

  const copyText = async (value) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    if (!copied) throw new Error('copy-failed');
  };

  const bindShare = (root) => {
    if (boundRoots.has(root)) return;
    const createUrl = root.dataset.createUrl;
    const publicUrl = root.dataset.publicUrl;
    const searchUrl = root.dataset.profileSearchUrl;
    const form = root.querySelector('form');
    const csrf = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    const intent = form?.querySelector('input[name="intent"]')?.value || '';
    const nativeButton = root.querySelector('[data-share-native]');
    const copyButton = root.querySelector('[data-share-copy]');
    const qrButton = root.querySelector('[data-share-qr-button]');
    const internalButton = root.querySelector('[data-share-internal]');
    const internalPanel = root.querySelector('[data-share-internal-panel]');
    const personSearch = root.querySelector('[data-share-person-search]');
    const personResults = root.querySelector('[data-share-person-results]');
    const qrPanel = root.querySelector('[data-share-qr-panel]');
    const qrImage = root.querySelector('[data-share-qr]');
    const feedback = root.querySelector('[data-share-feedback]');
    let shareDataPromise = null;
    let searchTimer = null;
    let sendingRecipient = null;

    if ((!createUrl || !form) && !publicUrl) return;
    boundRoots.add(root);
    if (!navigator.share && nativeButton) nativeButton.hidden = true;
    if (publicUrl) {
      if (internalButton) internalButton.hidden = true;
      if (qrButton) qrButton.hidden = true;
    }

    const setFeedback = (message) => {
      if (feedback) feedback.textContent = message;
    };

    const bodyFor = (recipientId = '') => {
      const body = new URLSearchParams();
      if (intent) body.set('intent', intent);
      if (recipientId) body.set('recipient_id', recipientId);
      return body;
    };

    const postShare = async (recipientId = '') => {
      if (!createUrl || !form) throw new Error('share-create-unavailable');
      const response = await fetch(createUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: bodyFor(recipientId).toString(),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'share-failed');
      return payload;
    };

    const shareData = () => {
      if (shareDataPromise) return shareDataPromise;
      if (publicUrl) {
        try {
          const target = new URL(publicUrl, window.location.origin);
          if (target.origin !== window.location.origin) {
            throw new Error('share-url-origin-mismatch');
          }
          const url = target.toString();
          shareDataPromise = Promise.resolve({
            title: root.dataset.shareTitle || 'Makolo',
            text: root.dataset.shareText || '',
            url,
          });
        } catch (_error) {
          shareDataPromise = Promise.reject(new Error('share-url-invalid'));
        }
        return shareDataPromise;
      }
      shareDataPromise = postShare().catch((error) => {
        shareDataPromise = null;
        throw error;
      });
      return shareDataPromise;
    };

    const renderPeople = (results) => {
      if (!personResults) return;
      personResults.replaceChildren();
      results.forEach((person) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'mk-btn mk-btn-secondary';
        button.setAttribute('role', 'option');
        button.style.justifyContent = 'space-between';
        button.textContent = person.username && person.username !== person.name
          ? `${person.name} · @${person.username}`
          : person.name;
        button.addEventListener('click', async () => {
          if (sendingRecipient) return;
          sendingRecipient = person.id;
          button.disabled = true;
          setFeedback(`Envoi à ${person.name}…`);
          try {
            await postShare(person.id);
            setFeedback('Partage envoyé.');
            if (internalPanel) internalPanel.hidden = true;
            if (personSearch) personSearch.value = '';
            personResults.replaceChildren();
          } catch (error) {
            setFeedback(error.message || 'Impossible d’envoyer ce partage.');
          } finally {
            sendingRecipient = null;
            button.disabled = false;
          }
        });
        personResults.appendChild(button);
      });
      if (!results.length) setFeedback('Aucun Profil correspondant.');
    };

    internalButton?.addEventListener('click', () => {
      if (!internalPanel) return;
      internalPanel.hidden = !internalPanel.hidden;
      if (!internalPanel.hidden) personSearch?.focus();
    });

    personSearch?.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      const query = personSearch.value.trim();
      if (query.length < 2) {
        personResults?.replaceChildren();
        setFeedback('Saisissez au moins 2 caractères.');
        return;
      }
      searchTimer = window.setTimeout(async () => {
        try {
          const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          if (!response.ok) throw new Error('search-failed');
          const payload = await response.json();
          renderPeople(payload.results || []);
        } catch (_error) {
          setFeedback('Impossible de rechercher des Profils pour le moment.');
        }
      }, 220);
    });

    nativeButton?.addEventListener('click', async () => {
      try {
        const payload = await shareData();
        await navigator.share({
          title: payload.title || root.dataset.shareTitle || 'Makolo',
          text: payload.text || root.dataset.shareText || '',
          url: payload.url,
        });
        setFeedback('Partage ouvert.');
      } catch (error) {
        if (error?.name !== 'AbortError') setFeedback('Le partage système n’est pas disponible. Vous pouvez copier le lien.');
      }
    });

    copyButton?.addEventListener('click', async () => {
      try {
        const payload = await shareData();
        await copyText(payload.url);
        setFeedback('Lien copié.');
      } catch (_error) {
        setFeedback('Impossible de copier automatiquement le lien. Réessayez depuis un navigateur récent.');
      }
    });

    qrButton?.addEventListener('click', async () => {
      try {
        const payload = await shareData();
        if (qrImage) qrImage.src = payload.qr_url;
        if (qrPanel) qrPanel.hidden = false;
        setFeedback('QR de partage prêt.');
      } catch (_error) {
        setFeedback('Impossible de générer le QR de partage.');
      }
    });
  };

  const bindAll = (scope = document) => {
    if (scope?.matches?.('[data-makolo-share]')) bindShare(scope);
    scope?.querySelectorAll?.('[data-makolo-share]').forEach(bindShare);
  };

  window.MakoloShare = { bind: bindAll };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => bindAll(document), { once: true });
  } else {
    bindAll(document);
  }
})();
