'use strict';
(() => {
  const form = document.querySelector('#session-form');
  if (!form || document.body.dataset.page !== 'form') return;
  const video = document.querySelector('#setup-camera');
  const cameraButton = document.querySelector('#setup-camera-toggle');
  const micButton = document.querySelector('#setup-mic-toggle');
  const mirrorButton = document.querySelector('#setup-mirror-toggle');
  const fullscreenButton = document.querySelector('#setup-fullscreen-toggle');
  const panel = document.querySelector('#setup-preview-panel');
  const placeholder = document.querySelector('#setup-camera-placeholder');
  const status = document.querySelector('#setup-device-status');
  const error = document.querySelector('#setup-device-error');
  const meter = document.querySelector('#setup-mic-meter');
  let cameraStream = null, micStream = null, audioContext = null, meterFrame = null;
  let disposed = false, generation = 0;

  function renderDevices() {
    const cameraOn = !!cameraStream?.getVideoTracks().some(track => track.readyState === 'live');
    const micOn = !!micStream?.getAudioTracks().some(track => track.readyState === 'live');
    cameraButton.setAttribute('aria-pressed', String(cameraOn));
    micButton.setAttribute('aria-pressed', String(micOn));
    cameraButton.setAttribute('aria-label', cameraOn ? 'Matikan kamera' : 'Aktifkan kamera');
    micButton.setAttribute('aria-label', micOn ? 'Matikan mikrofon' : 'Aktifkan mikrofon');
    cameraButton.title = cameraButton.getAttribute('aria-label');
    micButton.title = micButton.getAttribute('aria-label');
    placeholder.hidden = cameraOn;
    meter.hidden = !micOn;
    status.textContent = !cameraOn && !micOn ? 'Kamera dan mikrofon nonaktif' :
      `Kamera ${cameraOn ? 'aktif' : 'nonaktif'} · Mikrofon ${micOn ? 'aktif' : 'nonaktif'}`;
  }

  function stopCamera() {
    cameraStream?.getTracks().forEach(track => track.stop());
    cameraStream = null;
    video.srcObject = null;
    renderDevices();
  }

  function stopMic() {
    cancelAnimationFrame(meterFrame);
    micStream?.getTracks().forEach(track => track.stop());
    micStream = null;
    audioContext?.close().catch(() => {});
    audioContext = null;
    meter.value = 0;
    renderDevices();
  }

  function deviceError(cause) {
    error.textContent = cause.name === 'NotAllowedError' ? 'Izin perangkat belum diberikan. Izinkan kamera atau mikrofon melalui pengaturan browser, lalu coba lagi.' :
      cause.name === 'NotFoundError' ? 'Perangkat tidak ditemukan. Hubungkan kamera atau mikrofon, lalu coba lagi.' :
      'Perangkat belum bisa diaktifkan. Pastikan tidak sedang dipakai aplikasi lain, lalu coba lagi.';
    error.hidden = false;
  }

  async function enableDevice(kind) {
    const button = kind === 'camera' ? cameraButton : micButton;
    const requestedGeneration = generation;
    button.disabled = true;
    error.hidden = true;
    status.textContent = kind === 'camera' ? 'Mengaktifkan kamera…' : 'Mengaktifkan mikrofon…';
    let acquired = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Media unavailable');
      acquired = await navigator.mediaDevices.getUserMedia(kind === 'camera' ?
        {video: {width: {ideal: 1280}, height: {ideal: 960}, facingMode: 'user'}, audio: false} :
        {video: false, audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
      if (disposed || requestedGeneration !== generation) {acquired.getTracks().forEach(track => track.stop()); return;}
      if (kind === 'camera') {
        cameraStream = acquired;
        video.srcObject = cameraStream;
        await video.play();
        if (disposed || requestedGeneration !== generation) return;
        cameraStream.getVideoTracks().forEach(track => track.addEventListener('ended', stopCamera, {once: true}));
      } else {
        micStream = acquired;
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        await audioContext.resume();
        if (disposed || requestedGeneration !== generation || !micStream) return;
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        audioContext.createMediaStreamSource(micStream).connect(analyser);
        const values = new Uint8Array(analyser.fftSize);
        function tick() {
          analyser.getByteTimeDomainData(values);
          const rms = Math.sqrt(values.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / values.length);
          meter.value = Math.min(100, rms * 400);
          meterFrame = requestAnimationFrame(tick);
        }
        tick();
        micStream.getAudioTracks().forEach(track => track.addEventListener('ended', stopMic, {once: true}));
      }
    } catch (cause) {
      acquired?.getTracks().forEach(track => track.stop());
      if (kind === 'camera') stopCamera(); else stopMic();
      if (!disposed && requestedGeneration === generation) deviceError(cause);
    } finally {
      button.disabled = false;
      renderDevices();
    }
  }

  cameraButton.addEventListener('click', () => cameraStream ? stopCamera() : enableDevice('camera'));
  micButton.addEventListener('click', () => micStream ? stopMic() : enableDevice('mic'));
  function mirror(enabled) {
    video.classList.toggle('is-mirrored', enabled);
    mirrorButton.setAttribute('aria-pressed', String(enabled));
    sessionStorage.setItem('preptiva-mirror', String(enabled));
  }
  mirror(sessionStorage.getItem('preptiva-mirror') === 'true');
  mirrorButton.addEventListener('click', () => mirror(mirrorButton.getAttribute('aria-pressed') !== 'true'));
  fullscreenButton.disabled = !document.fullscreenEnabled;
  fullscreenButton.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await panel.requestFullscreen();
    } catch {
      error.textContent = 'Fullscreen tidak tersedia. Pratinjau tetap dapat digunakan.';
      error.hidden = false;
    }
  });
  document.addEventListener('fullscreenchange', () => {
    const enabled = document.fullscreenElement === panel;
    fullscreenButton.setAttribute('aria-pressed', String(enabled));
    fullscreenButton.setAttribute('aria-label', enabled ? 'Keluar fullscreen' : 'Buka fullscreen');
    fullscreenButton.title = fullscreenButton.getAttribute('aria-label');
  });

  const modeInput = form.elements.interview_mode;
  const panelInputs = [...form.querySelectorAll('[name=panel]')];
  function validatePanel() {
    const panelMode = modeInput.value === 'panel';
    const count = panelInputs.filter(input => input.checked).length;
    panelInputs[0].setCustomValidity(panelMode && count < 2 ? 'Pilih minimal dua pewawancara untuk panel.' : '');
  }
  function renderMode() {
    const panelMode = modeInput.value === 'panel';
    document.querySelector('#single-personas').hidden = panelMode;
    document.querySelector('#panel-personas').hidden = !panelMode;
    panelInputs.forEach(input => {input.disabled = !panelMode;});
    validatePanel();
  }
  modeInput.addEventListener('change', renderMode);
  panelInputs.forEach(input => input.addEventListener('change', validatePanel));
  renderMode();
  form.addEventListener('reset', event => queueMicrotask(() => {
    if (!event.defaultPrevented) {renderMode(); validateCv();}
  }));
  form.querySelectorAll('[name=interviewer]').forEach(input => input.addEventListener('change', () => {
    document.querySelector('#setup-persona-description').textContent = input.dataset.description;
  }));
  form.elements.candidate_name.addEventListener('input', () => {
    document.querySelector('#setup-preview-name').textContent = form.elements.candidate_name.value.trim() || 'Preview Anda';
  });
  function validateCv() {
    const pdf = form.elements.cv_pdf;
    const text = form.elements.cv_text;
    const file = pdf.files[0];
    pdf.setCustomValidity(file?.size > 5 * 1024 * 1024 ? 'PDF maksimal 5 MB.' : '');
    const hasCv = !!file || form.elements.use_last_cv.checked || text.value.trim().length >= 200;
    text.setCustomValidity(hasCv ? '' : 'Unggah PDF atau tempel teks CV minimal 200 karakter.');
  }
  ['cv_pdf', 'cv_text', 'use_last_cv'].forEach(name => {
    form.elements[name].addEventListener('input', validateCv);
    form.elements[name].addEventListener('change', validateCv);
  });
  form.addEventListener('invalid', event => {
    const section = event.target.closest('details');
    if (section) section.open = true;
  }, true);
  validateCv();
  function dispose() {disposed = true; generation++; stopCamera(); stopMic();}
  window.addEventListener('pagehide', dispose);
  window.addEventListener('pageshow', () => {disposed = false;});
  renderDevices();
})();
