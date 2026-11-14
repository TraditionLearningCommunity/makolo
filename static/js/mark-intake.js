(() => {
  'use strict';

  const MAX_TEXT = 600;
  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const MAX_FILES = 4;
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const initialized = new WeakSet();

  function init(root) {
    if (initialized.has(root)) return;
    initialized.add(root);

    const workspace = root.querySelector('[data-mk-mark-window]');
    const form = root.querySelector('[data-mk-mark-form]');
    const input = form?.querySelector('textarea[name="intent"], textarea[name="value"]');
    if (!workspace || !form || !input) return;

    const $ = (selector) => root.querySelector(selector);
    const announce = (message) => {
      const feedback = $('[data-mk-mark-feedback]');
      if (feedback) {
        feedback.textContent = message;
        feedback.hidden = !message;
      }
    };
    const scope = root.dataset.mkMarkScope || 'unknown';
    const draftKey = 'mk:mark:tab-draft:' + scope;
    let links = [];
    let attachments = [];
    let consent = false;
    let submission = null;
    let recognizer = null;
    let previousFocus = null;
    let mode = 'inline';
    let previewUrl = null;
    const hasLocalReferences = () => attachments.length > 0 || links.length > 0;

    // Only the active browser tab may keep a text/link draft. No File, media,
    // Profile cache or credential is written to browser storage.
    function persist() {
      try {
        const snapshot = { text: input.value.slice(0, 12000), links };
        window.sessionStorage.setItem(draftKey, JSON.stringify(snapshot));
      } catch (_) {
        // Private browsing and disabled storage still allow in-memory editing.
      }
    }

    function restore() {
      try {
        const raw = window.sessionStorage.getItem(draftKey);
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (!input.value && typeof saved.text === 'string') input.value = saved.text;
        if (Array.isArray(saved.links)) {
          links = saved.links.filter((url) => typeof url === 'string' && isSafeUrl(url)).slice(0, 8);
        }
      } catch (_) {
        links = [];
      }
    }

    function isSafeUrl(value) {
      if (typeof value !== 'string' || value.length > 2048) return false;
      try {
        const url = new URL(value);
        return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !!url.hostname;
      } catch (_) {
        return false;
      }
    }

    function resetConsent() {
      consent = false;
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
    }

    function closePreview() {
      const dialog = $('[data-mk-mark-preview]');
      if (dialog?.open) dialog.close();
      const body = $('[data-mk-mark-preview-body]');
      body?.replaceChildren();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }

    function previewFile(file) {
      const dialog = $('[data-mk-mark-preview]');
      const body = $('[data-mk-mark-preview-body]');
      if (!dialog?.showModal || !body) return;
      closePreview();
      const type = file.type || '';
      let visual;
      if (['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(type)) {
        visual = document.createElement('img');
        visual.alt = file.name || 'Image locale';
        visual.className = 'mk-mark-preview-media';
      } else if (['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/webm', 'audio/x-m4a'].includes(type)) {
        visual = document.createElement('audio');
        visual.controls = true;
        visual.className = 'mk-mark-preview-media';
      }
      const description = document.createElement('p');
      description.textContent = file.name || 'Pièce locale';
      body.appendChild(description);
      if (visual) {
        previewUrl = URL.createObjectURL(file);
        visual.src = previewUrl;
        body.appendChild(visual);
      } else {
        const note = document.createElement('p');
        note.textContent = 'Aperçu indisponible pour ce format. Le fichier reste local.';
        body.appendChild(note);
      }
      dialog.showModal();
      $('[data-mk-mark-preview-close]')?.focus();
    }

    function closeAssetForm() {
      const panel = $('[data-mk-mark-owner-panel]');
      const ownerForm = $('[data-mk-mark-owner-form]');
      if (panel) panel.hidden = true;
      ownerForm?.reset();
    }

    function canSaveAsPersonalAsset(file) {
      const name = (file?.name || '').toLowerCase();
      return ['.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png']
        .some((extension) => name.endsWith(extension));
    }

    function openAssetForm(file) {
      const panel = $('[data-mk-mark-owner-panel]');
      const ownerForm = $('[data-mk-mark-owner-form]');
      if (!panel || !ownerForm || !canSaveAsPersonalAsset(file)) return;
      const fileInput = ownerForm.querySelector('input[name="file"][type="file"]');
      if (!fileInput || typeof DataTransfer === 'undefined') {
        announce('Ouvrez Mes documents pour sélectionner ce fichier et le conserver.');
        return;
      }
      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
      } catch (_) {
        announce('Le navigateur ne permet pas ce transfert local. Utilisez Mes documents.');
        return;
      }
      const title = ownerForm.elements.namedItem('title');
      if (title) title.value = file.name.replace(/\.[^.]+$/, '').slice(0, 220);
      ['kind', 'sensitivity'].forEach((name) => {
        const select = ownerForm.elements.namedItem(name);
        if (!(select instanceof HTMLSelectElement)) return;
        if (!select.querySelector('option[value=""]')) {
          const option = document.createElement('option');
          option.value = '';
          option.textContent = 'Choisir…';
          option.disabled = true;
          select.prepend(option);
        }
        select.value = '';
      });
      panel.hidden = false;
      panel.scrollIntoView({ block: 'nearest', behavior: 'auto' });
      title?.focus();
      announce('Complétez le type et la confidentialité. Rien n’est encore envoyé.');
    }


    const thumbnailUrls = new Map();
    function imageUrl(file) {
      if (!thumbnailUrls.has(file)) thumbnailUrls.set(file, URL.createObjectURL(file));
      return thumbnailUrls.get(file);
    }
    function releaseUnusedThumbnails() {
      for (const [file, url] of thumbnailUrls) {
        if (!attachments.includes(file)) {
          URL.revokeObjectURL(url);
          thumbnailUrls.delete(file);
        }
      }
    }
    function typedLinks() {
      const recognized = new Set();
      const pattern = /https?:\/\/[^\s<>"']+/ig;
      for (const match of input.value.matchAll(pattern)) {
        const url = match[0].replace(/[.,;!?)]*$/, '');
        if (isSafeUrl(url) && !links.includes(url)) recognized.add(url);
      }
      return [...recognized].slice(0, 6);
    }
    function renderReferences() {
      const target = $('[data-mk-mark-references]');
      if (!target) return;
      releaseUnusedThumbnails();
      target.replaceChildren();
      for (const url of [...links, ...typedLinks()]) {
        const chip = document.createElement('span');
        chip.className = 'mk-mark-link-chip';
        chip.title = 'Lien présent dans votre demande';
        const icon = document.createElement('span');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = '↗';
        const label = document.createElement('span');
        label.textContent = url;
        chip.append(icon, label);
        if (links.includes(url)) {
          const remove = document.createElement('button');
          remove.type = 'button';
          remove.setAttribute('aria-label', 'Retirer le lien ' + url);
          remove.textContent = '×';
          remove.addEventListener('click', () => {
            links = links.filter((entry) => entry !== url);
            resetConsent();
            renderReferences();
            persist();
          });
          chip.appendChild(remove);
        }
        target.appendChild(chip);
      }
      attachments.forEach((file) => {
        const item = document.createElement('div');
        item.className = 'mk-mark-file-tile';
        const preview = document.createElement('button');
        preview.type = 'button';
        preview.className = 'mk-mark-file-preview';
        preview.setAttribute('aria-label', 'Aperçu de ' + (file.name || 'Pièce'));
        preview.addEventListener('click', () => previewFile(file));
        if (file.type.startsWith('image/')) {
          const thumbnail = document.createElement('img');
          thumbnail.alt = '';
          thumbnail.loading = 'lazy';
          thumbnail.src = imageUrl(file);
          preview.appendChild(thumbnail);
        } else {
          const extension = (file.name.split('.').pop() || 'FILE').toUpperCase().slice(0, 5);
          const symbol = document.createElement('span');
          symbol.className = 'mk-mark-file-type';
          symbol.textContent = extension;
          preview.appendChild(symbol);
        }
        const name = document.createElement('span');
        name.className = 'mk-mark-file-name';
        name.textContent = file.name || 'Pièce';
        item.append(preview, name);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'mk-mark-file-remove';
        remove.setAttribute('aria-label', 'Retirer ' + (file.name || 'la pièce'));
        remove.textContent = '×';
        remove.addEventListener('click', () => {
          attachments = attachments.filter((entry) => entry !== file);
          closeAssetForm();
          resetConsent();
          renderReferences();
        });
        item.appendChild(remove);
        if (canSaveAsPersonalAsset(file) && $('[data-mk-mark-owner-panel]')) {
          const save = document.createElement('button');
          save.type = 'button';
          save.className = 'mk-mark-file-save';
          save.textContent = 'Conserver';
          save.addEventListener('click', () => openAssetForm(file));
          item.appendChild(save);
        }
        target.appendChild(item);
      });
    }

    function addFiles(list) {
      if (!list?.length) return;
      const files = Array.from(list);
      if (files.length + attachments.length > MAX_FILES) {
        announce('Ajoutez au maximum quatre pièces à cette demande.');
        return;
      }
      if (files.some((file) => !file.size || file.size > MAX_FILE_BYTES)) {
        announce('Les pièces doivent être non vides et ne pas dépasser 25 Mo chacune.');
        return;
      }
      attachments.push(...files);
      closeAssetForm();
      resetConsent();
      renderReferences();
      announce('');
    }

    function setMode(next) {
      if (next === 'minimized' || next === 'inline') closePreview();
      const desktop = window.matchMedia('(min-width: 1200px)').matches;
      mode = desktop ? next : 'inline';
      root.dataset.mkMarkMode = mode;
      const floatBtn = $('[data-mk-mark-float]');
      const minimizeBtn = $('[data-mk-mark-minimize]');
      const inlineBtn = $('[data-mk-mark-inline]');
      const restoreBtn = $('[data-mk-mark-restore]');
      if (floatBtn) floatBtn.hidden = !desktop || mode !== 'inline';
      if (minimizeBtn) minimizeBtn.hidden = mode !== 'floating';
      if (inlineBtn) inlineBtn.hidden = mode !== 'floating';
      if (restoreBtn) restoreBtn.hidden = mode !== 'minimized';
      if (mode === 'minimized') restoreBtn?.focus();
      else if (next === 'inline') previousFocus?.focus();
      else if (next === 'floating') input.focus();
    }

    restore();
    renderReferences();
    setMode('inline');
    $('[data-mk-mark-preview-close]')?.addEventListener('click', closePreview);
    $('[data-mk-mark-owner-cancel]')?.addEventListener('click', closeAssetForm);
    $('[data-mk-mark-preview]')?.addEventListener('close', closePreview);

    const attachOpen = $('[data-mk-mark-attach-open]');
    const attachMenu = $('[data-mk-mark-attach-menu]');
    attachOpen?.addEventListener('click', () => {
      if (!attachMenu) return;
      attachMenu.hidden = !attachMenu.hidden;
      attachOpen.setAttribute('aria-expanded', String(!attachMenu.hidden));
      if (!attachMenu.hidden) attachMenu.querySelector('button')?.focus();
      updateComposer();
    });
    const pickerMap = {
      '[data-mk-mark-photo-open]': '[data-mk-mark-photo]',
      '[data-mk-mark-gallery-open]': '[data-mk-mark-gallery]',
      '[data-mk-mark-files-open]': '[data-mk-mark-files]',
    };
    Object.entries(pickerMap).forEach(([button, picker]) => {
      $(button)?.addEventListener('click', () => {
        if (attachMenu) attachMenu.hidden = true;
        attachOpen?.setAttribute('aria-expanded', 'false');
        updateComposer();
        $(picker)?.click();
      });
    });
    root.querySelectorAll(
      '[data-mk-mark-files],[data-mk-mark-photo],[data-mk-mark-gallery]',
    ).forEach((picker) => {
      picker.addEventListener('change', () => {
        addFiles(picker.files);
        picker.value = '';
      });
    });

    function updateComposer() {
      const count = $('[data-mk-mark-count]');
      const send = $('[data-mk-mark-send]');
      if (count) {
        count.hidden = input.value.length < 500;
        count.textContent = input.value.length + '/600';
      }
      if (send) send.disabled = !input.value.trim() || input.value.length > MAX_TEXT;
      root.classList.toggle(
        'mk-mark-writing',
        document.activeElement === input ||
          (attachMenu && !attachMenu.hidden) ||
          (speechPanel && !speechPanel.hidden),
      );
    }

    input.addEventListener('input', () => {
      resetConsent();
      persist();
      renderReferences();
      updateComposer();
      announce(input.value.length > MAX_TEXT
        ? 'Raccourcissez votre demande avant de continuer.'
        : '');
    });
    input.addEventListener('focus', updateComposer);
    input.addEventListener('blur', updateComposer);

    $('[data-mk-mark-clear-selection]')?.addEventListener('click', () => {
      $('[data-mk-mark-selected]')?.remove();
      resetConsent();
      input.focus();
    });

    // SpeechRecognition may delegate recognition outside this browser/device.
    // The person is asked once before microphone capture; the only Mark
    // mutation is their explicitly accepted editable text.
    const voiceButton = $('[data-mk-mark-voice]');
    const speechPanel = $('[data-mk-mark-dictation]');
    const status = $('[data-mk-mark-speech-status]');
    const start = $('[data-mk-mark-speech-start]');
    const stop = $('[data-mk-mark-speech-stop]');
    const useSpeech = $('[data-mk-mark-speech-use]');
    let dictationBase = '';
    let spoken = '';
    let speechConsent = false;

    function closeDictation(keep = false) {
      try { recognizer?.abort(); } catch (_) {}
      recognizer = null;
      if (!keep) input.value = dictationBase;
      if (speechPanel) speechPanel.hidden = true;
      if (start) start.disabled = false;
      if (stop) stop.disabled = true;
      if (useSpeech) useSpeech.disabled = true;
      spoken = '';
      resetConsent();
      renderReferences();
      updateComposer();
      if (keep) persist();
      input.focus();
    }

    function startDictation() {
      if (!Speech || recognizer) return;
      if (!speechConsent) {
        if (!window.confirm(
          'La dictée peut utiliser un service de reconnaissance du navigateur. Continuer ?',
        )) return;
        speechConsent = true;
      }
      dictationBase = input.value;
      spoken = '';
      if (speechPanel) speechPanel.hidden = false;
      updateComposer();
      if (useSpeech) useSpeech.disabled = true;
      if (status) status.textContent = 'J’écoute…';
      try {
        const active = new Speech();
        recognizer = active;
        active.lang = document.documentElement.lang || 'fr-FR';
        active.interimResults = true;
        active.continuous = false;
        active.maxAlternatives = 1;
        active.onresult = (event) => {
          if (recognizer !== active) return;
          let combined = '';
          for (let i = 0; i < event.results.length; i++) {
            combined += event.results[i][0]?.transcript || '';
          }
          spoken = combined;
          input.value = [dictationBase.trim(), spoken.trim()].filter(Boolean).join(' ');
          renderReferences();
          updateComposer();
          if (status) status.textContent = 'J’écoute…';
        };
        active.onerror = () => {
          if (status) status.textContent = 'Dictée interrompue. Réessayez.';
        };
        active.onend = () => {
          if (recognizer !== active) return;
          recognizer = null;
          if (start) start.disabled = false;
          if (stop) stop.disabled = true;
          if (useSpeech) useSpeech.disabled = !spoken.trim();
          if (status && spoken.trim()) status.textContent = 'Vous pouvez corriger le texte';
        };
        active.start();
        if (start) start.disabled = true;
        if (stop) stop.disabled = false;
      } catch (_) {
        recognizer = null;
        if (status) status.textContent = 'Dictée indisponible';
        if (start) start.disabled = false;
        if (stop) stop.disabled = true;
      }
    }

    if (Speech && voiceButton && speechPanel) {
      voiceButton.hidden = false;
      voiceButton.addEventListener('click', startDictation);
      start?.addEventListener('click', startDictation);
      stop?.addEventListener('click', () => recognizer?.stop());
      useSpeech?.addEventListener('click', () => {
        if (recognizer || !spoken.trim()) return;
        closeDictation(true);
      });
      $('[data-mk-mark-speech-cancel]')?.addEventListener(
        'click', () => closeDictation(false),
      );
    }

    function proceedWithText() {
      if (!input.value.trim()) {
        announce('Écrivez une demande avant de continuer avec le texte seul.');
        return;
      }
      consent = true;
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
      if (submission && form.contains(submission)) form.requestSubmit(submission);
      else form.requestSubmit();
    }

    form.addEventListener('submit', (event) => {
      if (event.submitter?.name === 'cancel_confirmation') return;
      if (!input.value.trim() || input.value.length > MAX_TEXT) {
        event.preventDefault();
        announce(!input.value.trim()
          ? 'Écrivez ce que vous souhaitez faire avant de continuer.'
          : 'Limitez votre demande à 600 caractères.');
        input.focus();
        return;
      }
      if (hasLocalReferences() && !consent) {
        event.preventDefault();
        submission = event.submitter;
        const panel = $('[data-mk-mark-text-consent]');
        if (panel) {
          panel.hidden = false;
          panel.querySelector('button')?.focus();
        }
        announce('Vos supports restent locaux ; vous pouvez choisir de continuer avec le texte seul.');
      } else {
        persist();
      }
    });

    $('[data-mk-mark-confirm-text]')?.addEventListener('click', proceedWithText);
    $('[data-mk-mark-keep-draft]')?.addEventListener('click', () => {
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
      input.focus();
    });

    $('[data-mk-mark-clear]')?.addEventListener('click', () => {
      if (!window.confirm('Effacer votre brouillon de cet onglet ? Cette action ne revient pas sur les décisions déjà confirmées.')) return;
      closePreview();
      closeAssetForm();
      if (speechPanel && !speechPanel.hidden) closeDictation(false);
      else if (recognizer) recognizer.abort();
      input.value = '';
      links = [];
      attachments = [];
      resetConsent();
      try { window.sessionStorage.removeItem(draftKey); } catch (_) {}
      renderReferences();
      announce('');
      updateComposer();
      input.focus();
    });

    $('[data-mk-mark-float]')?.addEventListener('click', () => {
      previousFocus = document.activeElement;
      setMode('floating');
    });
    $('[data-mk-mark-minimize]')?.addEventListener('click', () => setMode('minimized'));
    $('[data-mk-mark-inline]')?.addEventListener('click', () => setMode('inline'));
    $('[data-mk-mark-restore]')?.addEventListener('click', () => setMode('floating'));

    root.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && mode === 'floating') {
        event.preventDefault();
        setMode('inline');
      }
    });
    function handleResize() {
      if (!window.matchMedia('(min-width: 1200px)').matches && mode !== 'inline') {
        setMode('inline');
      }
    }
    function teardown() {
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('htmx:beforeSwap', beforeSwap);
      window.removeEventListener('pagehide', teardown);
      try { recognizer?.abort(); } catch (_) {}
      recognizer = null;
      closePreview();
      for (const url of thumbnailUrls.values()) URL.revokeObjectURL(url);
      thumbnailUrls.clear();
    }
    function beforeSwap(event) {
      const target = event.detail?.target || event.target;
      if (target && (target === root || target.contains?.(root))) teardown();
    }
    window.addEventListener('resize', handleResize);
    document.addEventListener('htmx:beforeSwap', beforeSwap);
    window.addEventListener('pagehide', teardown);
    updateComposer();
    // Files intentionally cannot survive a navigation/reload; the server must
    // never be told that they were submitted by the text-only Mark endpoint.
  }

  function scan(container = document) {
    if (container.matches?.('[data-mk-mark-root]')) init(container);
    container.querySelectorAll?.('[data-mk-mark-root]').forEach(init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => scan(), { once: true });
  } else {
    scan();
  }
  document.addEventListener('htmx:afterSwap', (event) => scan(event.detail?.target || document));
})();
