(() => {
  'use strict';

  const MAX_TEXT = 600;
  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const MAX_FILES = 10;
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
    const intakeUrl = root.dataset.mkMarkIntakeUrl;
    let requestKey = null;
    let requestFingerprint = null;
    let received = false;
    let sending = false;
    let offerFallback = false;
    let editRevision = 0;
    let links = [];
    let attachments = [];
    let consent = false;
    let submission = null;
    let previousFocus = null;
    let mode = 'inline';
    let previewUrl = null;
    const hasLocalReferences = () => attachments.length > 0 || links.length > 0;

    // Only the active browser tab may keep a text/link draft. No File, media,
    // Profile cache or credential is written to browser storage.
    function setSaved(saved) {
      const action = $('[data-mk-mark-save]');
      if (!action) return;
      action.title = saved ? 'Enregistré' : 'Enregistrer';
      action.setAttribute('aria-label', action.title);
      const available = action.querySelector('[data-mk-orbit-available]');
      const retained = action.querySelector('[data-mk-orbit-saved]');
      if (available) available.hidden = saved;
      if (retained) retained.hidden = !saved;
    }

    function persist() {
      try {
        const snapshot = { text: input.value, links };
        window.sessionStorage.setItem(draftKey, JSON.stringify(snapshot));
        setSaved(Boolean(input.value.trim() || links.length));
        return true;
      } catch (_) {
        setSaved(false);
        // Browsers without session storage retain the in-memory editor.
        return false;
      }
    }

    function restore() {
      try {
        const raw = window.sessionStorage.getItem(draftKey);
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (!input.value && typeof saved.text === 'string') input.value = saved.text;
        setSaved(Boolean(input.value.trim() || saved.links?.length));
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
      editRevision += 1;
      received = false;
      offerFallback = false;
      consent = false;
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
      updateComposer();
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
      const choice = $('[data-mk-mark-text-consent]');
      if (choice && !consent) choice.hidden = !offerFallback;
    }

    function addFiles(list) {
      if (!list?.length) return;
      const files = Array.from(list);
      if (files.length + attachments.length > MAX_FILES) {
        announce('10 pièces maximum pour une demande.');
        return;
      }
      const docExtensions = /\\.(pdf|docx?|txt|jpe?g|png)$/i;
      const supported = /\\.(pdf|docx?|txt|jpe?g|png|webp|m4a|mp4|webm|wav|mp3|aac|ogg)$/i;
      if (files.some((file) =>
        !supported.test(file.name) || !file.size ||
        file.size > (docExtensions.test(file.name) ? 12 * 1024 * 1024 : MAX_FILE_BYTES))) {
        announce('Un fichier est vide, trop volumineux ou son format n’est pas accepté.');
        return;
      }
      const total = [...attachments, ...files].reduce((sum, file) => sum + file.size, 0);
      if (total > 60 * 1024 * 1024) {
        announce('La demande contient trop de pièces volumineuses.');
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
      if (next === 'minimized' && speechPanel && !speechPanel.hidden) {
        closeDictation(false);
      }
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

    function alignFocusedComposer() {
      const viewport = window.visualViewport;
      const offset = viewport && root.classList.contains('mk-mark-writing')
        ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
        : 0;
      root.style.setProperty('--mk-mark-keyboard-offset', offset + 'px');
    }

    function updateComposer() {
      const count = $('[data-mk-mark-count]');
      const send = $('[data-mk-mark-send]');
      if (count) {
        count.hidden = input.value.length < 500;
        count.textContent = input.value.length + '/600';
      }
      const hasParts = hasLocalReferences() || typedLinks().length > 0;
      const maxLength = hasParts && !consent ? 20000 : MAX_TEXT;
      if (send) send.disabled = sending || received ||
        (!input.value.trim() && !hasParts) ||
        input.value.length > maxLength;
      root.classList.toggle(
        'mk-mark-writing',
        document.activeElement === input ||
          (attachMenu && !attachMenu.hidden) ||
          (speechPanel && !speechPanel.hidden),
      );
      alignFocusedComposer();
    }

    input.addEventListener('input', () => {
      resetConsent();
      persist();
      renderReferences();
      updateComposer();
      announce(input.value.length > ((hasLocalReferences() || typedLinks().length) ? 20000 : MAX_TEXT)
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

    // A single browser recording session, not an OS dictation loop.
    // Transcription from a *recorded file* is not exposed without a real
    // configured audio-transcription owner. Never fake a transcript.
    const voiceButton = $('[data-mk-mark-voice]');
    const speechPanel = $('[data-mk-mark-dictation]');
    const status = $('[data-mk-mark-speech-status]');
    const pause = $('[data-mk-mark-speech-pause]');
    const stop = $('[data-mk-mark-speech-stop]');
    const attachAudio = $('[data-mk-mark-speech-use]');
    const transcribeAudio = $('[data-mk-mark-speech-transcribe]');
    const transcriptionEndpoint = '/api/v1/me/mark/transcription/';
    let canTranscribeAudio = false;
    if (root.dataset.mkMarkContext !== 'space') {
      fetch(transcriptionEndpoint, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      }).then((response) => response.ok ? response.json() : null)
        .then((payload) => {
          canTranscribeAudio = payload?.data?.available === true;
          if (transcribeAudio && readyAudio) {
            transcribeAudio.hidden = !canTranscribeAudio;
          }
        }).catch(() => { canTranscribeAudio = false; });
    }
    const supportsRecording = typeof window.MediaRecorder === 'function' &&
      Boolean(navigator.mediaDevices?.getUserMedia);
    let stream = null;
    let recorder = null;
    let audioTimer = null;
    let seconds = 0;
    let chunks = [];
    let readyAudio = null;
    let audioRevision = 0;
    let discardOnStop = false;

    function audioClock() {
      return String(Math.floor(seconds / 60)).padStart(2, '0') +
        ':' + String(seconds % 60).padStart(2, '0');
    }
    function audioStatus(text) {
      if (status) status.textContent = text;
    }
    function releaseMicrophone() {
      if (audioTimer) clearInterval(audioTimer);
      audioTimer = null;
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    function closeDictation(keep = false) {
      audioRevision += 1;
      discardOnStop = !keep;
      if (recorder && recorder.state !== 'inactive') {
        try { recorder.stop(); } catch (_) {}
      }
      releaseMicrophone();
      recorder = null;
      readyAudio = null;
      chunks = [];
      if (speechPanel) speechPanel.hidden = true;
      if (attachAudio) attachAudio.hidden = true;
      if (transcribeAudio) transcribeAudio.hidden = true;
      if (stop) stop.disabled = true;
      if (pause) pause.disabled = true;
      alignFocusedComposer();
    }
    function finalizeRecording(active) {
      if (recorder !== active) return;
      releaseMicrophone();
      recorder = null;
      if (discardOnStop) {
        chunks = [];
        readyAudio = null;
        return;
      }
      const mime = active.mimeType || 'audio/webm';
      const blob = new Blob(chunks, { type: mime });
      chunks = [];
      if (!blob.size || blob.size > MAX_FILE_BYTES) {
        readyAudio = null;
        audioStatus('Enregistrement indisponible');
        return;
      }
      const ext = mime.includes('mp4') ? 'm4a' : 'webm';
      readyAudio = new File(
        [blob], 'Audio-Mark-' + Date.now() + '.' + ext,
        { type: mime },
      );
      audioStatus('Audio · ' + audioClock());
      if (pause) pause.hidden = true;
      if (stop) stop.hidden = true;
      if (attachAudio) attachAudio.hidden = false;
      if (transcribeAudio) transcribeAudio.hidden = !canTranscribeAudio;
    }
    async function startRecording() {
      if (!supportsRecording || recorder || !speechPanel) return;
      audioRevision += 1;
      discardOnStop = false;
      chunks = [];
      readyAudio = null;
      seconds = 0;
      speechPanel.hidden = false;
      if (attachAudio) attachAudio.hidden = true;
      if (transcribeAudio) transcribeAudio.hidden = true;
      if (stop) {
        stop.hidden = false;
        stop.disabled = true;
      }
      if (pause) {
        pause.hidden = false;
        pause.disabled = true;
      }
      audioStatus('Microphone…');
      try {
        const acquired = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
          video: false,
        });
        if (!root.isConnected || document.hidden || speechPanel.hidden) {
          acquired.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = acquired;
        const mime = ['audio/webm;codecs=opus', 'audio/mp4']
          .find((type) => window.MediaRecorder.isTypeSupported?.(type) === true);
        const active = mime
          ? new window.MediaRecorder(acquired, { mimeType: mime })
          : new window.MediaRecorder(acquired);
        recorder = active;
        active.ondataavailable = (event) => {
          if (event.data?.size) chunks.push(event.data);
        };
        active.onstop = () => finalizeRecording(active);
        active.onerror = () => {
          audioStatus('Enregistrement interrompu');
          releaseMicrophone();
        };
        active.start(1000);
        if (pause) pause.disabled = false;
        if (stop) stop.disabled = false;
        audioStatus('En cours · ' + audioClock());
        audioTimer = setInterval(() => {
          if (active.state !== 'recording') return;
          seconds += 1;
          audioStatus('En cours · ' + audioClock());
          if (seconds >= 600) active.stop();
        }, 1000);
      } catch (_) {
        releaseMicrophone();
        recorder = null;
        audioStatus('Microphone indisponible');
        if (pause) pause.disabled = true;
        if (stop) stop.disabled = true;
      }
      alignFocusedComposer();
    }
    if (supportsRecording && voiceButton && speechPanel) {
      voiceButton.hidden = false;
      voiceButton.addEventListener('click', startRecording);
      pause?.addEventListener('click', () => {
        if (!recorder) return;
        if (recorder.state === 'recording') {
          recorder.pause();
          audioStatus('En pause · ' + audioClock());
          pause.title = 'Reprendre';
          pause.setAttribute('aria-label', 'Reprendre');
        } else if (recorder.state === 'paused') {
          recorder.resume();
          audioStatus('En cours · ' + audioClock());
          pause.title = 'Pause';
          pause.setAttribute('aria-label', 'Pause');
        }
      });
      stop?.addEventListener('click', () => {
        if (recorder && recorder.state !== 'inactive') recorder.stop();
      });
      attachAudio?.addEventListener('click', () => {
        if (!readyAudio) return;
        const countBefore = attachments.length;
        addFiles([readyAudio]);
        if (attachments.length > countBefore) closeDictation(true);
      });
      transcribeAudio?.addEventListener('click', async () => {
        if (!readyAudio || !canTranscribeAudio || transcribeAudio.disabled) return;
        const audio = readyAudio;
        const revision = audioRevision;
        transcribeAudio.disabled = true;
        audioStatus('Transcription…');
        try {
          const formData = new FormData();
          formData.append('audio', audio);
          const token = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
          const response = await fetch(transcriptionEndpoint, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              Accept: 'application/json',
              ...(token ? { 'X-CSRFToken': token } : {}),
            },
            body: formData,
          });
          if (!response.ok) throw new Error('No available transcription');
          const payload = await response.json();
          const transcript = payload?.data?.text;
          if (typeof transcript !== 'string' || !transcript.trim()) {
            throw new Error('Empty transcription');
          }
          if (revision !== audioRevision || readyAudio !== audio ||
              !root.isConnected) return;
          // Read the latest editor after the request. Never replace or
          // truncate what was typed while transcription was running.
          const text = transcript.trim();
          const existing = input.value;
          const separator = existing && !/\s$/.test(existing) ? '\n' : '';
          input.value = existing + separator + text;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          persist();
          closeDictation(true);
          input.focus();
        } catch (_) {
          audioStatus('Transcription indisponible. Réessayez.');
        } finally {
          transcribeAudio.disabled = false;
        }
      });
      $('[data-mk-mark-speech-cancel]')?.addEventListener('click', () => {
        closeDictation(false);
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
      if (submission && form.contains(submission)) form.requestSubmit(submission);
      else form.requestSubmit();
    }

    const fileIdentities = new WeakMap();
    function fileIdentity(file) {
      if (!fileIdentities.has(file)) {
        fileIdentities.set(file, String(Date.now()) + ':' + Math.random());
      }
      return fileIdentities.get(file);
    }
    function newRequestKey() {
      if (window.crypto?.randomUUID) return window.crypto.randomUUID();
      if (!window.crypto?.getRandomValues) throw new Error('Secure random unavailable');
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes, (x) => x.toString(16).padStart(2, '0')).join('');
    }
    function markContext() {
      const selected = {};
      for (const field of ['kind', 'id', 'family']) {
        const value = form.elements.namedItem('selected_' + field)?.value;
        if (value) selected[field] = value;
      }
      const result = {};
      if (Object.keys(selected).length) result.selected = selected;
      const responsibility = root.dataset.mkMarkResponsibility;
      if (root.dataset.mkMarkContext === 'space' && responsibility && responsibility !== 'all') {
        result.responsibility = responsibility;
      }
      return result;
    }
    function acknowledgeReceipt(revision) {
      if (revision !== editRevision || !root.isConnected) {
        announce('La demande précédente a été reçue. Votre modification reste à envoyer.');
        return;
      }
      received = true;
      offerFallback = false;
      const panel = $('[data-mk-mark-text-consent]');
      if (panel) panel.hidden = true;
      announce('Demande reçue.');
      try { window.sessionStorage.removeItem(draftKey); } catch (_) {}
      setSaved(false);
      updateComposer();
    }
    async function sendMultimodal() {
      if (!intakeUrl || sending) return;
      const allLinks = [...new Set([...links, ...typedLinks()])];
      const fingerprint = JSON.stringify({
        text: input.value,
        links: allLinks,
        files: attachments.map(fileIdentity),
        context: markContext(),
      });
      if (fingerprint !== requestFingerprint) {
        requestKey = null;
        requestFingerprint = fingerprint;
      }
      try {
        if (!requestKey) requestKey = newRequestKey();
      } catch (_) {
        announce('Envoi indisponible pour le moment.');
        return;
      }
      const revision = editRevision;
      const formData = new FormData();
      formData.append('request_key', requestKey);
      formData.append('text', input.value);
      formData.append('links', JSON.stringify(allLinks));
      formData.append('context', JSON.stringify(markContext()));
      for (const file of attachments) formData.append('files', file, file.name);
      const token = form.elements.namedItem('csrfmiddlewaretoken')?.value;
      sending = true;
      announce('');
      updateComposer();
      let uncertain = false;
      try {
        const response = await fetch(intakeUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: { Accept: 'application/json', ...(token ? { 'X-CSRFToken': token } : {}) },
          body: formData,
        });
        if (!response.ok) {
          const error = new Error('Reception rejected');
          error.status = response.status;
          throw error;
        }
        const payload = await response.json();
        if (payload?.data?.state !== 'received' || !payload?.data?.receipt_id) {
          throw new Error('Receipt missing');
        }
        acknowledgeReceipt(revision);
      } catch (error) {
        uncertain = !error.status;
        if (uncertain) {
          try {
            const verify = await fetch(intakeUrl + '?request_key=' + encodeURIComponent(requestKey), {
              credentials: 'same-origin',
              headers: { Accept: 'application/json' },
            });
            if (verify.ok) {
              const payload = await verify.json();
              if (payload?.data?.state === 'received') {
                acknowledgeReceipt(revision);
                return;
              }
            }
          } catch (_) { /* The original reception is still unknown. */ }
        }
        if (!received) {
          announce(uncertain ? 'Réception à confirmer. Réessayez.' :
            'Envoi impossible. Réessayez ou retirez la pièce concernée.');
          offerFallback = Boolean(input.value.trim() && attachments.length);
          const panel = $('[data-mk-mark-text-consent]');
          if (panel) panel.hidden = !offerFallback;
        }
      } finally {
        sending = false;
        updateComposer();
      }
    }

    form.addEventListener('submit', (event) => {
      if (event.submitter?.name === 'cancel_confirmation') return;
      if (sending || received) {
        event.preventDefault();
        return;
      }
      const hasParts = hasLocalReferences() || typedLinks().length > 0;
      const maxLength = hasParts && !consent ? 20000 : MAX_TEXT;
      if ((!input.value.trim() && !hasParts) || input.value.length > maxLength) {
        event.preventDefault();
        announce(input.value.length > maxLength
          ? 'Raccourcissez votre demande avant de continuer.'
          : 'Ajoutez du texte ou une pièce.');
        return;
      }
      if (hasParts && !consent) {
        event.preventDefault();
        void sendMultimodal();
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

    $('[data-mk-mark-save]')?.addEventListener('click', () => {
      if (!persist()) announce('Impossible d’enregistrer le brouillon ici.');
    });

    $('[data-mk-mark-clear]')?.addEventListener('click', () => {
      if (!window.confirm('Effacer votre brouillon de cet onglet ? Cette action ne revient pas sur les décisions déjà confirmées.')) return;
      closePreview();
      closeAssetForm();
      if (speechPanel && !speechPanel.hidden) closeDictation(false);
      input.value = '';
      links = [];
      attachments = [];
      resetConsent();
      try { window.sessionStorage.removeItem(draftKey); } catch (_) {}
      setSaved(false);
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
    function stopHiddenDictation() {
      if (document.hidden && speechPanel && !speechPanel.hidden) {
        closeDictation(false);
      }
    }
    function teardown() {
      window.removeEventListener('resize', handleResize);
      window.visualViewport?.removeEventListener('resize', alignFocusedComposer);
      window.visualViewport?.removeEventListener('scroll', alignFocusedComposer);
      document.removeEventListener('visibilitychange', stopHiddenDictation);
      document.removeEventListener('htmx:beforeSwap', beforeSwap);
      window.removeEventListener('pagehide', teardown);
      closeDictation(false);
      closePreview();
      for (const url of thumbnailUrls.values()) URL.revokeObjectURL(url);
      thumbnailUrls.clear();
    }
    function beforeSwap(event) {
      const target = event.detail?.target || event.target;
      if (target && (target === root || target.contains?.(root))) teardown();
    }
    window.addEventListener('resize', handleResize);
    window.visualViewport?.addEventListener('resize', alignFocusedComposer);
    window.visualViewport?.addEventListener('scroll', alignFocusedComposer);
    document.addEventListener('visibilitychange', stopHiddenDictation);
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
