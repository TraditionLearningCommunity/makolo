(() => {
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
    const createUrl = root.dataset.createUrl;
    const form = root.querySelector('form');
    const csrf = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    const intent = form?.querySelector('input[name="intent"]')?.value || '';
    const nativeButton = root.querySelector('[data-share-native]');
    const copyButton = root.querySelector('[data-share-copy]');
    const qrButton = root.querySelector('[data-share-qr-button]');
    const qrPanel = root.querySelector('[data-share-qr-panel]');
    const qrImage = root.querySelector('[data-share-qr]');
    const feedback = root.querySelector('[data-share-feedback]');
    let shareDataPromise = null;

    if (!createUrl || !form) return;
    if (!navigator.share && nativeButton) nativeButton.hidden = true;

    const setFeedback = (message) => {
      if (feedback) feedback.textContent = message;
    };

    const shareData = () => {
      if (shareDataPromise) return shareDataPromise;
      const body = new URLSearchParams();
      if (intent) body.set('intent', intent);
      shareDataPromise = fetch(createUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: body.toString(),
      }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'share-failed');
        return payload;
      }).catch((error) => {
        shareDataPromise = null;
        throw error;
      });
      return shareDataPromise;
    };

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

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-makolo-share]').forEach(bindShare);
  });
})();
