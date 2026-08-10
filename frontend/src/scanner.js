(() => {
  const scannerRoot = document.getElementById('scanner-console');
  if (!scannerRoot) return;

  const video = document.getElementById('scanner-video');
  const cameraState = document.getElementById('camera-state');
  const resultTitle = document.getElementById('result-title');
  const resultMessage = document.getElementById('result-message');
  const resultIcon = document.getElementById('result-icon');
  const ticketInfo = document.getElementById('ticket-info');
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
  let lastToken = '';
  let lastTokenAt = 0;

  function clientReference() {
    return window.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function selectedGateId() {
    return fixedGate ? fixedGate.value : (gateSelect ? gateSelect.value : '');
  }

  function setCameraState(message) {
    cameraState.textContent = message;
  }

  function setResult(data) {
    const accepted = Boolean(data.accepted);
    resultIcon.textContent = accepted ? '✓' : '×';
    resultIcon.className = accepted
      ? 'flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-3xl font-black text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
      : 'flex h-14 w-14 items-center justify-center rounded-2xl bg-red-100 text-3xl font-black text-red-700 dark:bg-red-950 dark:text-red-300';
    resultTitle.textContent = accepted ? 'Accès autorisé' : 'Accès refusé';
    resultMessage.textContent = data.message || 'Résultat du contrôle.';
    if (data.ticket) {
      ticketInfo.classList.remove('hidden');
      ticketInfo.innerHTML = '';
      const holder = document.createElement('p');
      holder.className = 'font-bold';
      holder.textContent = data.ticket.holder_name || 'Participant';
      const type = document.createElement('p');
      type.className = 'mt-1 text-zinc-500';
      type.textContent = data.ticket.ticket_type || '';
      const gate = document.createElement('p');
      gate.className = 'mt-2 text-xs text-zinc-400';
      gate.textContent = data.gate ? `Porte : ${data.gate}` : '';
      ticketInfo.append(holder, type, gate);
    } else {
      ticketInfo.classList.add('hidden');
      ticketInfo.innerHTML = '';
    }
  }

  async function submitToken(token) {
    token = (token || '').trim();
    if (!token || busy) return;
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
      setResult(response.ok ? data : {accepted: false, message: data.detail || 'Erreur de validation.'});
    } catch (error) {
      setResult({accepted: false, message: 'Connexion au serveur impossible.'});
    } finally {
      window.setTimeout(() => {
        busy = false;
        setCameraState(running ? 'Caméra active · présentez un QR' : 'Caméra arrêtée');
      }, 900);
    }
  }

  async function nativeScanLoop(timestamp) {
    if (!nativeLoopRunning) return;
    if (nativeDetector && video.readyState >= 2 && !busy && timestamp - nativeLastDetectAt > 300) {
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
      if (/permission|denied|notallowed/i.test(message)) {
        setCameraState('Accès caméra refusé. Autorisez la caméra dans le navigateur ou utilisez une image QR.');
      } else {
        setCameraState('Caméra indisponible. Utilisez une image QR ou la saisie manuelle.');
      }
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
    if (!file) return;
    setCameraState('Lecture de l’image QR…');
    try {
      if (!window.QrScanner) throw new Error('Moteur QR non chargé');
      const result = await QrScanner.scanImage(file, {returnDetailedScanResult: true, alsoTryWithoutScanRegion: true});
      await submitToken(result && result.data ? result.data : result);
    } catch (error) {
      setResult({accepted: false, message: 'Aucun QR lisible trouvé dans cette image.'});
      setCameraState(running ? 'Caméra active · présentez un QR' : 'Choisissez une autre image ou utilisez la saisie manuelle.');
    } finally {
      imageInput.value = '';
    }
  });
  manualForm.addEventListener('submit', async event => {
    event.preventDefault();
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
