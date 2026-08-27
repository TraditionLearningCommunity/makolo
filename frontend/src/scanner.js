(() => {
  const scannerRoot = document.getElementById('scanner-console');
  if (!scannerRoot) return;

  const video = document.getElementById('scanner-video');
  const cameraState = document.getElementById('camera-state');
  const resultTitle = document.getElementById('result-title');
  const resultMessage = document.getElementById('result-message');
  const resultIcon = document.getElementById('result-icon');
  const ticketInfo = document.getElementById('ticket-info');
  const nextButton = document.getElementById('scan-next');
  const manualForm = document.getElementById('manual-form');
  const manualToken = document.getElementById('manual-token');
  const imageInput = document.getElementById('qr-image');
  const cameraPicker = document.getElementById('camera-picker');
  const cameraPickerWrap = document.getElementById('camera-picker-wrap');
  const flashButton = document.getElementById('toggle-flash');
  const startButton = document.getElementById('start-camera');
  const stopButton = document.getElementById('stop-camera');
  const fixedGate = document.getElementById('access-gate-id');
  const gateSelect = document.getElementById('access-gate-select');
  const csrfToken = manualForm.querySelector('[name=csrfmiddlewaretoken]').value;
  const scanUrl = scannerRoot.dataset.scanUrl;

  let qrScanner = null;
  let nativeDetector = null;
  let nativeStream = null;
  let nativeLoopRunning = false;
  let nativeLastDetectAt = 0;
  let running = false;
  let busy = false;
  let successLocked = false;
  let lastToken = '';
  let lastTokenAt = 0;

  function clientReference() {
    return window.crypto && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function selectedGateId() {
    return fixedGate ? fixedGate.value : (gateSelect ? gateSelect.value : '');
  }

  function setCameraState(message) {
    cameraState.textContent = message;
  }

  function effectiveResult(data) {
    return data.access_result || data.result || '';
  }

  function tactileFeedback(data) {
    if (!navigator.vibrate) return;
    try {
      navigator.vibrate(data.accepted || effectiveResult(data) === 'accepted' ? 45 : [25, 35, 25]);
    } catch (error) {}
  }

  function presentationFor(data) {
    const result = effectiveResult(data);
    if (data.accepted || result === 'accepted') return {title: 'Accès autorisé', tone: 'success', icon: '✓'};
    const presentations = {
      not_yet_valid: ['Contrôle pas encore ouvert', 'warning', 'i'],
      already_used: ['Billet déjà utilisé', 'warning', '!'],
      duplicate: ['Billet déjà utilisé', 'warning', '!'],
      expired: ['Billet expiré', 'danger', '×'],
      revoked: ['Billet révoqué', 'danger', '×'],
      cancelled: ['Billet annulé', 'danger', '×'],
      wrong_activity: ['Autre activité', 'danger', '×'],
      wrong_event: ['Autre activité ou occurrence', 'danger', '×'],
      wrong_occurrence: ['Autre occurrence', 'danger', '×'],
      invalid_credential: ['QR invalide ou non reconnu', 'danger', '×'],
      invalid_token: ['QR invalide ou non reconnu', 'danger', '×'],
      invalid_status: ['Billet non valide', 'danger', '×'],
      event_unavailable: ['Contrôle indisponible', 'warning', 'i'],
      gate_unavailable: ['Point de contrôle fermé', 'warning', 'i'],
      unknown_ticket: ['QR non reconnu', 'danger', '×'],
    };
    const item = presentations[result] || ['Contrôle impossible', 'danger', '×'];
    return {title: item[0], tone: item[1], icon: item[2]};
  }

  function iconClasses(tone) {
    const common = 'flex h-14 w-14 items-center justify-center rounded-2xl text-3xl font-black';
    if (tone === 'success') return `${common} bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300`;
    if (tone === 'warning') return `${common} bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300`;
    return `${common} bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300`;
  }

  function localTime(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
  }

  function setResult(data) {
    const presentation = presentationFor(data);
    resultIcon.textContent = presentation.icon;
    resultIcon.className = iconClasses(presentation.tone);
    resultTitle.textContent = presentation.title;
    resultMessage.textContent = data.message || 'Résultat du contrôle.';
    tactileFeedback(data);

    ticketInfo.innerHTML = '';
    const holderName = data.ticket?.holder_name || data.access?.beneficiary || '';
    const typeName = data.ticket?.ticket_type || '';
    const controlledAt = localTime(data.controlled_at || data.scanned_at);
    const acceptedAt = effectiveResult(data) === 'already_used' || effectiveResult(data) === 'duplicate'
      ? localTime(data.accepted_at)
      : '';
    if (holderName || typeName || data.gate || controlledAt || acceptedAt) {
      ticketInfo.classList.remove('hidden');
      if (holderName) {
        const holder = document.createElement('p');
        holder.className = 'font-bold';
        holder.textContent = holderName;
        ticketInfo.appendChild(holder);
      }
      if (typeName) {
        const type = document.createElement('p');
        type.className = 'mt-1 text-zinc-500';
        type.textContent = typeName;
        ticketInfo.appendChild(type);
      }
      if (controlledAt) {
        const controlled = document.createElement('p');
        controlled.className = 'mt-2 text-xs text-zinc-400';
        controlled.textContent = `Contrôlé à : ${controlledAt}`;
        ticketInfo.appendChild(controlled);
      }
      if (acceptedAt) {
        const accepted = document.createElement('p');
        accepted.className = 'mt-1 text-xs text-zinc-400';
        accepted.textContent = `Premier contrôle accepté : ${acceptedAt}`;
        ticketInfo.appendChild(accepted);
      }
      if (data.gate) {
        const gate = document.createElement('p');
        gate.className = 'mt-1 text-xs text-zinc-400';
        gate.textContent = `Point de contrôle : ${data.gate}`;
        ticketInfo.appendChild(gate);
      }
    } else {
      ticketInfo.classList.add('hidden');
    }

    if (data.accepted) {
      successLocked = true;
      nextButton?.classList.remove('hidden');
      setCameraState('Accès accepté · choisissez « Scanner le suivant » pour continuer');
    }
  }

  function resetForNextScan() {
    successLocked = false;
    busy = false;
    lastToken = '';
    lastTokenAt = 0;
    nextButton?.classList.add('hidden');
    ticketInfo.classList.add('hidden');
    ticketInfo.innerHTML = '';
    resultIcon.textContent = '—';
    resultIcon.className = 'flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800';
    resultTitle.textContent = 'Prêt à scanner';
    resultMessage.textContent = 'Présentez un QR Makolo devant la caméra.';
    setCameraState(running ? 'Caméra active · présentez le QR suivant' : 'Caméra arrêtée');
  }

  async function submitToken(token) {
    token = (token || '').trim();
    if (!token || busy || successLocked) return;
    const now = Date.now();
    if (token === lastToken && now - lastTokenAt < 4000) return;
    lastToken = token;
    lastTokenAt = now;
    busy = true;
    setCameraState('QR détecté · validation serveur…');

    const body = new URLSearchParams();
    body.set('token', token);
    body.set('client_reference', clientReference());
    const gateId = selectedGateId();
    if (gateId) body.set('access_gate_id', gateId);

    try {
      const response = await fetch(scanUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'},
        body: body.toString(),
        credentials: 'same-origin',
      });
      const data = await response.json();
      setResult(response.ok ? data : {
        accepted: false,
        result: data.result || 'invalid_credential',
        message: data.detail || data.message || 'Erreur de validation.',
      });
    } catch (error) {
      setResult({accepted: false, message: 'Connexion au serveur impossible.'});
    } finally {
      window.setTimeout(() => {
        busy = false;
        if (!successLocked) setCameraState(running ? 'Caméra active · présentez un QR' : 'Caméra arrêtée');
      }, 900);
    }
  }

  async function nativeScanLoop(timestamp) {
    if (!nativeLoopRunning) return;
    if (nativeDetector && video.readyState >= 2 && !busy && !successLocked && timestamp - nativeLastDetectAt > 300) {
      nativeLastDetectAt = timestamp;
      try {
        const codes = await nativeDetector.detect(video);
        if (codes.length && codes[0].rawValue) await submitToken(codes[0].rawValue);
      } catch (error) {}
    }
    requestAnimationFrame(nativeScanLoop);
  }

  async function populateCameraPicker() {
    if (!window.QrScanner || !qrScanner) return;
    try {
      const cameras = await QrScanner.listCameras(true);
      cameraPicker.innerHTML = '';
      cameras.forEach((camera, index) => {
        const option = document.createElement('option');
        option.value = camera.id;
        option.textContent = camera.label || `Caméra ${index + 1}`;
        cameraPicker.appendChild(option);
      });
      cameraPickerWrap.classList.toggle('hidden', cameras.length < 2);
    } catch (error) {
      cameraPickerWrap.classList.add('hidden');
    }
  }

  async function configureFlash() {
    flashButton.classList.add('hidden');
    if (!qrScanner) return;
    try {
      if (await qrScanner.hasFlash()) flashButton.classList.remove('hidden');
    } catch (error) {}
  }

  async function startWithQrScanner() {
    if (!window.QrScanner) return false;
    if (!(await QrScanner.hasCamera())) throw new Error('Aucune caméra détectée sur cet appareil.');
    if (!qrScanner) {
      qrScanner = new QrScanner(
        video,
        result => submitToken(result && result.data ? result.data : result),
        {
          preferredCamera: 'environment',
          maxScansPerSecond: 6,
          highlightScanRegion: true,
          highlightCodeOutline: true,
          returnDetailedScanResult: true,
          onDecodeError: () => {},
        },
      );
    }
    await qrScanner.start();
    running = true;
    setCameraState('Caméra active · moteur QR compatible');
    await populateCameraPicker();
    await configureFlash();
    return true;
  }

  async function startWithNativeDetector() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !('BarcodeDetector' in window)) return false;
    nativeDetector = new BarcodeDetector({formats: ['qr_code']});
    nativeStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: 'environment'}}, audio: false});
    video.srcObject = nativeStream;
    await video.play();
    running = true;
    nativeLoopRunning = true;
    setCameraState('Caméra active · détection QR native');
    requestAnimationFrame(nativeScanLoop);
    return true;
  }

  async function startCamera() {
    if (running) return;
    startButton.disabled = true;
    setCameraState('Demande d’accès à la caméra…');
    try {
      if (await startWithQrScanner()) return;
      if (await startWithNativeDetector()) return;
      setCameraState('Scanner caméra indisponible. Utilisez une image QR ou la saisie manuelle.');
    } catch (error) {
      const message = error && error.message ? error.message : String(error || '');
      setCameraState(/permission|denied|notallowed/i.test(message)
        ? 'Accès caméra refusé. Autorisez la caméra dans le navigateur ou utilisez une image QR.'
        : 'Caméra indisponible. Utilisez une image QR ou la saisie manuelle.');
    } finally {
      startButton.disabled = false;
    }
  }

  function stopCamera() {
    running = false;
    nativeLoopRunning = false;
    if (qrScanner) qrScanner.stop();
    if (nativeStream) nativeStream.getTracks().forEach(track => track.stop());
    nativeStream = null;
    if (!qrScanner) video.srcObject = null;
    flashButton.classList.add('hidden');
    setCameraState('Caméra arrêtée');
  }

  nextButton?.addEventListener('click', resetForNextScan);
  startButton.addEventListener('click', startCamera);
  stopButton.addEventListener('click', stopCamera);
  cameraPicker.addEventListener('change', async () => {
    if (!qrScanner || !cameraPicker.value) return;
    try {
      await qrScanner.setCamera(cameraPicker.value);
      setCameraState('Caméra changée · présentez un QR');
    } catch (error) {
      setCameraState('Impossible de changer de caméra.');
    }
  });
  flashButton.addEventListener('click', async () => {
    if (!qrScanner) return;
    try {
      await qrScanner.toggleFlash();
    } catch (error) {
      setCameraState('Lampe non disponible sur cette caméra.');
    }
  });
  imageInput.addEventListener('change', async () => {
    const file = imageInput.files && imageInput.files[0];
    if (!file || successLocked) return;
    setCameraState('Lecture de l’image QR…');
    try {
      if (!window.QrScanner) throw new Error('Moteur QR non chargé');
      const result = await QrScanner.scanImage(file, {returnDetailedScanResult: true, alsoTryWithoutScanRegion: true});
      await submitToken(result && result.data ? result.data : result);
    } catch (error) {
      setResult({accepted: false, result: 'invalid_credential', message: 'Aucun QR lisible trouvé dans cette image.'});
      setCameraState(running ? 'Caméra active · présentez un QR' : 'Choisissez une autre image ou utilisez la saisie manuelle.');
    } finally {
      imageInput.value = '';
    }
  });
  manualForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (successLocked) return;
    const token = manualToken.value;
    manualToken.value = '';
    await submitToken(token);
  });
  window.addEventListener('pagehide', () => {
    stopCamera();
    if (qrScanner) qrScanner.destroy();
  });

  startCamera();
})();