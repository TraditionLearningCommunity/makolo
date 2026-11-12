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

    function renderReferences() {
      const target = $('[data-mk-mark-references]');
      if (!target) return;
      target.replaceChildren();
      [...links.map((url) => ({ label: url, type: 'link', value: url })),
        ...attachments.map((file, index) => ({
          label: file.name || 'Pièce locale', type: 'file', value: String(index),
        }))].forEach((entry) => {
        const item = document.createElement('span');
        item.className = 'mk-mark-reference';
        const text = document.createElement('span');
        text.textContent = entry.label;
        text.title = entry.label;
        item.appendChild(text);
        if (entry.type === 'file') {
          const preview = document.createElement('button');
          preview.type = 'button';
          preview.className = 'mk-mark-reference-remove';
          preview.textContent = '⌕';
          preview.setAttribute('aria-label', 'Aperçu de ' + entry.label);
          preview.addEventListener('click', () => {
            const file = attachments[Number(entry.value)];
            if (file) previewFile(file);
          });
          item.appendChild(preview);
        }
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'mk-mark-reference-remove';
        remove.textContent = '×';
        remove.setAttribute('aria-label', 'Retirer ' + entry.label);
        remove.addEventListener('click', () => {
          if (entry.type === 'link') links = links.filter((url) => url !== entry.value);
          else attachments.splice(Number(entry.value), 1);
          resetConsent();
          renderReferences();
          persist();
        });
        item.appendChild(remove);
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
      resetConsent();
      renderReferences();
      announce('Pièces conservées dans cet onglet uniquement. Utilisez Mes documents pour les transmettre.');
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
    $('[data-mk-mark-preview]')?.addEventListener('close', closePreview);

    root.querySelectorAll('[data-mk-mark-file-input]').forEach((picker) => {
      picker.addEventListener('change', () => {
        addFiles(picker.files);
        picker.value = '';
      });
    });
    root.querySelectorAll('[data-mk-mark-files],[data-mk-mark-photo]').forEach((picker) => {
      picker.addEventListener('change', () => {
        addFiles(picker.files);
        picker.value = '';
      });
    });

    input.addEventListener('input', () => {
      resetConsent();
      persist();
      announce(input.value.length > MAX_TEXT
        ? 'Votre demande dépasse 600 caractères. Raccourcissez-la avant de continuer.'
        : '');
    });

    $('[data-mk-mark-link-toggle]')?.addEventListener('click', () => {
      const editor = $('[data-mk-mark-link-editor]');
      if (!editor) return;
      editor.hidden = !editor.hidden;
      if (!editor.hidden) $('[data-mk-mark-link-input]')?.focus();
    });

    function addLink() {
      const field = $('[data-mk-mark-link-input]');
      const value = field?.value.trim();
      if (!isSafeUrl(value)) {
        announce('Utilisez une adresse http ou https complète, sans identifiants.');
        return;
      }
      if (links.length >= 8) {
        announce('Ajoutez au maximum huit liens.');
        return;
      }
      if (!links.includes(value)) links.push(value);
      field.value = '';
      resetConsent();
      renderReferences();
      persist();
      announce('Lien conservé localement ; son contenu n’a pas été analysé.');
    }
    $('[data-mk-mark-link-add]')?.addEventListener('click', addLink);
    $('[data-mk-mark-link-input]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        addLink();
      }
    });

    // Web Speech is capability-gated and may use a remote browser service.
    // No recognition or microphone access starts before a user gesture.
    const voiceButton = $('[data-mk-mark-voice]');
    const speechPanel = $('[data-mk-mark-dictation]');
    const transcript = $('[data-mk-mark-transcript]');
    const start = $('[data-mk-mark-speech-start]');
    const stop = $('[data-mk-mark-speech-stop]');
    if (Speech && voiceButton && speechPanel && transcript) {
      voiceButton.hidden = false;
      voiceButton.addEventListener('click', () => {
        speechPanel.hidden = !speechPanel.hidden;
        if (!speechPanel.hidden) transcript.focus();
        else if (recognizer) recognizer.abort();
      });
      start?.addEventListener('click', () => {
        if (recognizer) return;
        transcript.value = '';
        try {
          const active = new Speech();
          recognizer = active;
          active.lang = document.documentElement.lang || 'fr';
          active.interimResults = true;
          active.continuous = false;
          active.maxAlternatives = 1;
          active.onresult = (event) => {
            let combined = '';
            for (let index = 0; index < event.results.length; index++) {
              combined += event.results[index][0]?.transcript || '';
            }
            transcript.value = combined.slice(0, MAX_TEXT);
          };
          active.onerror = () => announce('La dictée du navigateur a échoué. Vous pouvez toujours écrire.');
          active.onend = () => {
            recognizer = null;
            if (start) start.disabled = false;
            if (stop) stop.disabled = true;
          };
          active.start();
          start.disabled = true;
          if (stop) stop.disabled = false;
          announce('Dictée en cours. Elle dépend du navigateur et peut utiliser un service externe.');
        } catch (_) {
          recognizer = null;
          start.disabled = false;
          if (stop) stop.disabled = true;
          announce('Dictée indisponible dans ce navigateur.');
        }
      });
      stop?.addEventListener('click', () => recognizer?.stop());
      $('[data-mk-mark-speech-use]')?.addEventListener('click', () => {
        if (recognizer) return;
        const spoken = transcript.value.trim();
        if (!spoken) return announce('Aucun texte reconnu à utiliser.');
        input.value = [input.value.trim(), spoken].filter(Boolean).join('\n');
        speechPanel.hidden = true;
        transcript.value = '';
        resetConsent();
        persist();
        input.focus();
        announce('Texte ajouté à la demande. Vérifiez-le avant de continuer.');
      });
    }

    function proceedWithText() {
      if (!input.value.trim()) {
        announce('Écrivez une demande avant de continuer avec le texte seul.');
        return;
      }
      consent = true;
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
      form.requestSubmit(submission && form.contains(submission) ? submission : undefined);
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
      if (recognizer) recognizer.abort();
      input.value = '';
      links = [];
      attachments = [];
      const transcript = $('[data-mk-mark-transcript]');
      if (transcript) transcript.value = '';
      resetConsent();
      try { window.sessionStorage.removeItem(draftKey); } catch (_) {}
      renderReferences();
      announce('Brouillon de cet onglet effacé.');
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
    window.addEventListener('resize', () => {
      if (!window.matchMedia('(min-width: 1200px)').matches && mode !== 'inline') {
        setMode('inline');
      }
    });
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
