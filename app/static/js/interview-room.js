'use strict';
(() => {
  const sid = document.body.dataset.sid;
  const room = document.getElementById('meeting-room');
  if (!sid || !room) return;

  const ids = ['room-stage', 'interviewer-avatar', 'interviewer-name', 'interviewer-title', 'room-title', 'room-subtitle', 'room-status',
    'chat-progress', 'elapsed-time', 'stage-caption', 'camera', 'preflight-camera', 'camera-off-placeholder', 'candidate-mic-status',
    'interviewer-audio', 'preflight', 'open-preflight', 'close-preflight', 'devices', 'camera-check', 'test-sound', 'speaker-check',
    'mic-meter', 'mic-status', 'focus-check', 'fullscreen-check', 'start', 'connection-status', 'connection-retry', 'preflight-error',
    'room-error', 'room-countdown', 'countdown-number', 'chat-log', 'chat-empty', 'chat-activity', 'chat-activity-label', 'chat-new-messages', 'chat-panel', 'record-controls',
    'answer-timer', 'record', 'send', 'retry', 'replay', 'answer-preview', 'retry-upload', 'resume-flow', 'question-progress',
    'question-text', 'transcript', 'camera-toggle', 'mic-toggle', 'mirror-toggle', 'captions-toggle', 'chat-toggle',
    'avatar-motion-toggle', 'fullscreen', 'leave-room', 'leave-dialog', 'cancel-leave', 'confirm-leave', 'room-tools',
    'device-status', 'device-requirement', 'preflight-description', 'preflight-title', 'verification-status', 'preflight-body',
    'panel-members', 'participant-count', 'voice-mode', 'text-mode', 'use-text', 'use-voice', 'answer-mode-status', 'text-answer-area', 'text-answer', 'send-text', 'stop-audio',
    'interruption', 'interruption-status', 'retry-question', 'skip-question', 'realtime-mode', 'auto-send', 'barge-in', 'live-review', 'live-transcript'];
  const elements = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const node = id => elements[id];
  const base = `/api/sessions/${encodeURIComponent(sid)}`;
  const marker = `preptiva-active-${sid}`;
  const interviewerAudio = node('interviewer-audio');
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const mobileUserAgent = /Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Silk|Kindle|BlackBerry|webOS|Mobile/i.test(navigator.userAgent || '');
  const desktopModeIPad = (/Mac/i.test(navigator.platform || '') || /Macintosh/i.test(navigator.userAgent || '')) && navigator.maxTouchPoints > 1;
  const desktopSupported = !(mobileUserAgent || desktopModeIPad || navigator.userAgentData?.mobile || /Android|iOS/i.test(navigator.userAgentData?.platform || ''));
  const messages = new Map();
  const spoken = new Set();
  const resultFlows = new Map();
  const waits = new Map();
  const sentLatency = new Set();

  let state = null, current = null, stream = null, audioContext = null;
  let micSource = null, micAnalyser = null, audioSource = null, audioAnalyser = null;
  let meterFrame = null, avatarFrame = null, blinkTimer = null, blinkEndTimer = null;
  let recordingTimer = null, elapsedTimer = null, pollTimer = null, healthTimer = null;
  let pollController = null, healthController = null, uploadController = null;
  let recorder = null, recorded = null, previewUrl = null, playbackCancel = null, playbackStop = null, testTone = null;
  let ready = false, active = false, closed = false, disposed = false, phase = 'preparing';
  let startPending = false, startRequestSent = false, startAbandoned = false, leavePending = false;
  let acquiring = false, soundTesting = false, soundTested = false, micReady = false, micSamples = 0;
  let healthy = false, healthCheckedAt = -Infinity, openedPreflight = false;
  let uploadBusy = false, flowBusy = false, pendingFlow = null;
  let answerWithText = false, pendingText = null, interruptionPending = false, interruptBusy = false, recoveryBusy = false, recoveryState = null;
  let speakerRole = null, speakerPersona = null, lastMessageAuthor = null;
  let motionEnabled = !reducedMotion?.matches, motionChosen = false, speaking = false, captionsEnabled = false;
  let captionText = '', deviceGeneration = 0, acquisitionId = 0, lifecycle = 0, retries = 0, recordingStart = 0;
  let sessionStartedAt = 0, lastAvatarUpdate = 0, newMessageCount = 0, lastMessageRole = null;
  let realtimeVoice = null, realtimeAttempt = null, vadTimer = null, pendingBargeIn = false;
  let endOfTurnAt = null, latencyAnswer = null;

  function storage(kind, method, key, value) {
    try {return window[kind]?.[method](key, value);} catch {return null;}
  }
  function localMarker(method, value) {
    try {return localStorage[method](marker, value);} catch {return null;}
  }
  function available() {return !closed && !disposed;}
  function interrupted() {return new DOMException('Operasi dihentikan.', 'AbortError');}
  function guard(token = lifecycle) {if (!available() || token !== lifecycle) throw interrupted();}
  function formatTime(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  }
  function status(text) {node('room-status').textContent = text;}
  function showError(id, cause) {
    node(id).textContent = cause?.message || String(cause);
    node(id).hidden = false;
  }
  function clearError(id) {node(id).hidden = true; node(id).textContent = '';}
  function setPhase(next) {
    phase = next;
    room.classList.toggle('is-recording', next === 'recording');
    node('use-text').disabled = !['answer-ready', 'recorded', 'upload-error'].includes(next);
    if (next !== 'processing') setChatActivity();
  }
  function selectAnswerMode(mode) {
    answerWithText = mode === 'text';
    node('text-mode').checked = answerWithText;
    node('voice-mode').checked = !answerWithText;
    node('preflight').classList.toggle('is-text-mode', answerWithText);
    node('answer-mode-status').textContent = answerWithText ? 'Mode jawaban: Teks' : 'Mode jawaban: Rekam suara';
    node('answer-mode-status').hidden = !active;
  }
  function buttonState(id, pressed, onLabel, offLabel) {
    const button = node(id);
    button.setAttribute('aria-pressed', String(pressed));
    if (onLabel) {
      const label = pressed ? onLabel : offLabel;
      button.setAttribute('aria-label', label);
      button.title = label;
    }
  }
  async function responseError(response, fallback) {
    let detail;
    try {detail = (await response.json()).detail;} catch {}
    if (Array.isArray(detail)) detail = detail.map(item => item.msg).join('\n');
    if (response.status === 401 && available()) location.assign('/login');
    return new Error(typeof detail === 'string' ? detail : fallback);
  }
  async function requestJSON(path, options = {}) {
    const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', ...options});
    if (!response.ok) throw await responseError(response, 'Permintaan belum berhasil. Coba lagi.');
    return response.json();
  }
  const post = (path, options = {}) => requestJSON(path, {method: 'POST', ...options});
  const postData = (path, data, options = {}) => post(path, {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data), ...options});
  function rememberQuestion(interrupted = false, questionId = current?.id) {
    if (questionId) localMarker('setItem', JSON.stringify({question_id: questionId, interrupted}));
  }
  function savedQuestion() {
    try {return JSON.parse(localMarker('getItem'))?.question_id || null;} catch {return null;}
  }
  function showInterviewer(value, roleHint) {
    const panel = state?.panel || [];
    const role = roleHint || (typeof value === 'string' ? value : value?.key) || panel.find(person => person.name === value?.name)?.key ||
      Object.entries({hr: 'Rina', user: 'Andi', manager: 'Hendra'}).find(([, name]) => name === value?.name)?.[0] || state?.interviewer || 'hr';
    const person = typeof value === 'object' && value ? value : panel.find(member => member.key === role) ||
      {name: {hr: 'Rina', user: 'Andi', manager: 'Hendra'}[role] || 'Pewawancara', title: {hr: 'HR Interviewer', user: 'Functional / Technical Lead', manager: 'Hiring Manager'}[role] || 'Interviewer'};
    speakerRole = role; speakerPersona = person;
    node('interviewer-name').textContent = person.name;
    node('interviewer-title').textContent = `${person.title} · AI`;
    node('interviewer-avatar').setAttribute('aria-label', `${person.name}, pewawancara AI`);
    node('interviewer-avatar').style.backgroundImage = `url("/static/images/interviewers/${{hr: 'rina', user: 'andi', manager: 'hendra'}[role] || 'rina'}-sprite.png")`;
    node('panel-members').textContent = '';
    node('panel-members').hidden = panel.length < 2;
    if (panel.length > 1) for (const member of panel) {
      const item = document.createElement('span');
      item.className = `meeting-panel-member panel-member${member.key === role ? ' is-active active' : ''}`;
      item.textContent = member.name;
      if (member.key === role) item.setAttribute('aria-current', 'true');
      node('panel-members').append(item);
    }
  }

  function nearChatBottom() {
    const log = node('chat-log');
    return log.scrollHeight - log.scrollTop - log.clientHeight < 90;
  }
  function scrollChat() {
    node('chat-log').scrollTop = node('chat-log').scrollHeight;
    newMessageCount = 0;
    node('chat-new-messages').hidden = true;
  }
  function setChatActivity(text = '') {
    const visible = !!text && available() && active && uploadBusy && phase === 'processing';
    const label = visible ? text : '';
    if (node('chat-activity-label').textContent !== label) node('chat-activity-label').textContent = label;
    node('chat-activity').hidden = !visible;
  }
  function upsertMessage(key, role, text, detail = '') {
    let message = messages.get(key);
    const follow = !node('chat-panel').hidden && nearChatBottom();
    if (!message) {
      const outer = document.createElement('div');
      outer.className = `chat-message chat-message--${role}`;
      const author = document.createElement('div');
      author.className = 'chat-message-author';
      author.textContent = role === 'candidate' ? 'Anda' : role === 'system' ? 'Sesi' : speakerPersona?.name || state?.persona?.name || 'Pewawancara';
      outer.dataset.continuation = String(lastMessageRole === role && lastMessageAuthor === author.textContent);
      lastMessageRole = role; lastMessageAuthor = author.textContent;
      const body = document.createElement('div');
      body.className = 'chat-message-body';
      const meta = document.createElement('div');
      meta.className = 'chat-message-time';
      outer.append(author, body, meta);
      message = {outer, body, meta};
      messages.set(key, message);
      node('chat-empty').hidden = true;
      node('chat-log').append(outer);
      if (!follow) newMessageCount++;
    }
    message.body.textContent = text || '';
    message.meta.textContent = detail;
    message.meta.hidden = !detail;
    if (follow) scrollChat();
    else if (newMessageCount) {
      node('chat-new-messages').textContent = `${newMessageCount} pesan baru`;
      node('chat-new-messages').hidden = false;
    }
    return message;
  }
  function candidateMessage(questionId, text, detail, answerId = null) {
    const questionKey = `candidate:q:${questionId}`;
    const answerKey = answerId == null ? null : `candidate:a:${answerId}`;
    if (!messages.has(questionKey) && answerKey && messages.has(answerKey)) messages.set(questionKey, messages.get(answerKey));
    const message = upsertMessage(questionKey, 'candidate', text, detail);
    if (answerKey) messages.set(answerKey, message);
    node('transcript').textContent = text || '';
    node('transcript').hidden = false;
  }
  function markCandidate(questionId, detail) {
    const message = messages.get(`candidate:q:${questionId}`);
    if (message) {message.meta.textContent = detail; message.meta.hidden = false;}
  }
  node('chat-log').addEventListener('scroll', () => {if (nearChatBottom()) {newMessageCount = 0; node('chat-new-messages').hidden = true;}});
  node('chat-new-messages').addEventListener('click', scrollChat);
  node('chat-toggle').addEventListener('click', () => {
    const hidden = !node('chat-panel').hidden;
    node('chat-panel').hidden = hidden;
    room.classList.toggle('chat-hidden', hidden);
    node('chat-toggle').setAttribute('aria-expanded', String(!hidden));
    node('chat-toggle').setAttribute('aria-label', hidden ? 'Tampilkan percakapan' : 'Sembunyikan percakapan');
    if (!hidden && !newMessageCount) scrollChat();
  });
  node('chat-toggle').setAttribute('aria-expanded', String(!node('chat-panel').hidden));

  function renderCaptions() {
    node('stage-caption').textContent = captionText;
    node('stage-caption').hidden = !captionsEnabled || !speaking || !captionText;
  }
  node('captions-toggle').addEventListener('click', () => {
    captionsEnabled = !captionsEnabled;
    buttonState('captions-toggle', captionsEnabled, 'Sembunyikan takarir', 'Tampilkan takarir');
    renderCaptions();
  });
  buttonState('captions-toggle', false, 'Sembunyikan takarir', 'Tampilkan takarir');

  function avatarIdle() {node('interviewer-avatar').dataset.frame = 'idle';}
  function stopAvatar() {
    cancelAnimationFrame(avatarFrame);
    clearTimeout(blinkTimer);
    clearTimeout(blinkEndTimer);
    avatarFrame = blinkTimer = blinkEndTimer = null;
    avatarIdle();
  }
  function scheduleBlink() {
    if (!motionEnabled || !available()) return;
    blinkTimer = setTimeout(() => {
      if (!motionEnabled || !available()) return;
      if (!speaking) {
        node('interviewer-avatar').dataset.frame = 'blink';
        blinkEndTimer = setTimeout(() => {if (!speaking) avatarIdle();}, 140);
      }
      scheduleBlink();
    }, 4000 + Math.random() * 2000);
  }
  function animateSpeech() {
    cancelAnimationFrame(avatarFrame);
    if (!motionEnabled || !speaking || !available()) return;
    const values = audioAnalyser ? new Uint8Array(audioAnalyser.fftSize) : null;
    function tick(now) {
      if (!motionEnabled || !speaking || interviewerAudio.paused || interviewerAudio.ended || !available()) {avatarIdle(); return;}
      if (now - lastAvatarUpdate >= 110) {
        lastAvatarUpdate = now;
        let frame;
        if (values && audioContext?.state === 'running') {
          audioAnalyser.getByteTimeDomainData(values);
          let energy = 0;
          for (const value of values) energy += ((value - 128) / 128) ** 2;
          const rms = Math.sqrt(energy / values.length);
          frame = rms > .055 ? 'talk-wide' : rms > .009 ? 'talk-small' : 'idle';
        } else {
          frame = ['talk-small', 'idle', 'talk-small', 'talk-wide'][Math.floor(now / 190) % 4];
        }
        node('interviewer-avatar').dataset.frame = frame;
      }
      avatarFrame = requestAnimationFrame(tick);
    }
    avatarFrame = requestAnimationFrame(tick);
  }
  function setSpeaking(value) {
    speaking = value && available() && !interviewerAudio.paused && !interviewerAudio.ended;
    node('room-stage').dataset.speaking = String(speaking);
    room.classList.toggle('is-speaking', speaking);
    renderCaptions();
    if (speaking) animateSpeech();
    else {cancelAnimationFrame(avatarFrame); avatarFrame = null; avatarIdle();}
  }
  function renderMotion() {
    stopAvatar();
    node('room-stage').dataset.motion = motionEnabled ? 'on' : 'off';
    buttonState('avatar-motion-toggle', motionEnabled, 'Jeda gerakan pewawancara', 'Aktifkan gerakan pewawancara');
    if (motionEnabled && available()) {scheduleBlink(); if (speaking) animateSpeech();}
  }
  node('avatar-motion-toggle').addEventListener('click', () => {motionChosen = true; motionEnabled = !motionEnabled; renderMotion();});
  reducedMotion?.addEventListener?.('change', event => {if (!motionChosen) {motionEnabled = !event.matches; renderMotion();}});
  interviewerAudio.addEventListener('playing', () => {
    setSpeaking(true);
    if (available() && latencyAnswer != null && endOfTurnAt !== null && !sentLatency.has(latencyAnswer)) {
      sentLatency.add(latencyAnswer);
      postData(`${base}/voice-latency`, {answer_id: latencyAnswer, elapsed_ms: Math.min(300000, Math.max(0, Math.round(performance.now() - endOfTurnAt)))}).catch(() => {});
    }
  });
  for (const event of ['pause', 'ended', 'error', 'waiting', 'stalled']) interviewerAudio.addEventListener(event, () => setSpeaking(false));
  renderMotion();
  setSpeaking(false);

  async function ensureAudioContext() {
    const Constructor = window.AudioContext || window.webkitAudioContext;
    if (!Constructor) throw new Error('Browser ini belum mendukung pemeriksaan mikrofon. Gunakan browser terbaru.');
    audioContext ||= new Constructor();
    await audioContext.resume();
    return audioContext;
  }
  function connectInterviewerAudio() {
    if (!audioContext || audioSource) return;
    try {
      audioAnalyser = audioContext.createAnalyser();
      audioAnalyser.fftSize = 256;
      audioSource = audioContext.createMediaElementSource(interviewerAudio);
      audioSource.connect(audioAnalyser);
      audioAnalyser.connect(audioContext.destination);
    } catch {audioAnalyser = null;}
  }
  async function play(url, text) {
    guard();
    if (!url) return;
    const token = lifecycle;
    if (playbackCancel) playbackCancel();
    captionText = text || '';
    node('replay').hidden = true;
    if (audioContext?.state === 'suspended') await audioContext.resume();
    guard(token);
    connectInterviewerAudio();
    await new Promise((resolve, reject) => {
      let settled = false;
      function settle(cause) {
        if (settled) return;
        settled = true;
        interviewerAudio.removeEventListener('ended', ended);
        interviewerAudio.removeEventListener('error', failed);
        if (playbackCancel === cancel) playbackCancel = null;
        playbackStop = null; node('stop-audio').hidden = true;
        interviewerAudio.pause(); interviewerAudio.removeAttribute('src'); interviewerAudio.load();
        setSpeaking(false);
        cause ? reject(cause) : resolve();
      }
      const ended = () => settle();
      const failed = () => settle(new Error('Audio belum dapat diputar. Pilih Lanjutkan audio untuk mencoba lagi.'));
      const cancel = () => {interviewerAudio.pause(); settle(interrupted());};
      playbackCancel = cancel;
      playbackStop = () => {interviewerAudio.pause(); settle();};
      node('stop-audio').hidden = false;
      interviewerAudio.addEventListener('ended', ended);
      interviewerAudio.addEventListener('error', failed);
      interviewerAudio.src = url;
      try {
        Promise.resolve(interviewerAudio.play()).then(() => {
          if (!available() || token !== lifecycle) cancel();
        }).catch(cause => settle(new Error(cause?.name === 'NotAllowedError' ?
          'Browser menjeda audio. Pilih Lanjutkan audio untuk memutarnya.' : 'Audio belum dapat diputar. Pilih Lanjutkan audio untuk mencoba lagi.')));
      } catch {failed();}
    });
    guard(token);
  }
  async function utterance(key, text, url) {
    guard();
    if (text) upsertMessage(key, 'ai', text);
    if (spoken.has(key)) return;
    setPhase('speaking'); status('MENDENGARKAN');
    node('record-controls').hidden = true;
    const token = lifecycle;
    try {await play(url, text);} catch (cause) {
      guard(token);
      if (cause?.name === 'AbortError') throw cause;
      showError('room-error', 'Suara belum tersedia. Percakapan tetap dapat dibaca di chat.');
    }
    guard(token);
    spoken.add(key);
  }
  node('stop-audio').addEventListener('click', () => playbackStop?.());

  function revokePreview() {
    node('answer-preview').pause();
    node('answer-preview').removeAttribute('src');
    node('answer-preview').hidden = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
  function stopStream() {
    deviceGeneration++;
    cancelRealtime(); realtimeVoice?.destroy(); realtimeVoice = null;
    cancelAnimationFrame(meterFrame); meterFrame = null;
    micSource?.disconnect(); micSource = null; micAnalyser = null;
    const previous = stream; stream = null;
    previous?.getTracks().forEach(track => track.stop());
    node('camera').srcObject = null;
    node('preflight-camera').srcObject = null;
    micReady = false; micSamples = 0;
    node('mic-meter').value = 0;
    renderDevices();
  }
  function cleanup() {
    lifecycle++;
    setChatActivity();
    clearInterval(recordingTimer); clearInterval(elapsedTimer); clearInterval(healthTimer);
    clearTimeout(pollTimer);
    recordingTimer = elapsedTimer = healthTimer = pollTimer = null;
    for (const [timer, reject] of waits) {clearTimeout(timer); reject(interrupted());}
    waits.clear();
    pollController?.abort(); healthController?.abort(); uploadController?.abort();
    pollController = healthController = uploadController = null;
    if (recorder) {
      recorder.ondataavailable = recorder.onstop = recorder.onerror = null;
      if (recorder.state !== 'inactive') {try {recorder.stop();} catch {}}
      recorder = null;
    }
    recorded = null;
    pendingText = null;
    playbackCancel?.();
    interviewerAudio.pause(); interviewerAudio.removeAttribute('src'); interviewerAudio.load();
    if (testTone) {testTone.onended = null; try {testTone.stop();} catch {} testTone = null;}
    soundTesting = false; acquiring = false; acquisitionId++;
    node('test-sound').disabled = false; node('devices').disabled = false;
    stopStream(); stopAvatar(); revokePreview();
    node('room-stage').dataset.motion = 'off';
    audioSource?.disconnect(); audioSource = null; audioAnalyser = null;
    audioContext?.close().catch(() => {}); audioContext = null;
    setSpeaking(false);
    pendingFlow = null; flowBusy = false; uploadBusy = false; interruptBusy = false; recoveryBusy = false; interruptionPending = false;
    node('resume-flow').hidden = true; node('retry-upload').hidden = true;
    node('record-controls').hidden = true; node('room-countdown').hidden = true;
    node('text-answer-area').hidden = true; node('use-text').hidden = true; node('stop-audio').hidden = true; node('live-review').hidden = true;
    room.classList.remove('is-recording');
    checkReady();
  }
  function sendClose() {
    let sent = false;
    try {sent = !!navigator.sendBeacon?.(`${base}/close`, new Blob([], {type: 'text/plain'}));} catch {}
    if (!sent) fetch(`${base}/close`, {method: 'POST', credentials: 'same-origin', keepalive: true}).catch(() => {});
  }
  function closeActive(navigate = true) {
    if (!active || closed) return;
    closed = true; active = false;
    localMarker('setItem', 'closed');
    cleanup();
    node('preflight').close(); node('leave-dialog').close();
    status('SESI DITUTUP'); sendClose();
    if (navigate) location.replace('/riwayat');
  }
  function interruptionBeacon(questionId, reason = 'reload') {
    if (!questionId) return;
    rememberQuestion(true, questionId);
    const body = JSON.stringify({question_id: questionId, reason});
    let sent = false;
    try {sent = !!navigator.sendBeacon?.(`${base}/interrupt`, new Blob([body], {type: 'application/json'}));} catch {}
    if (!sent) postData(`${base}/interrupt`, {question_id: questionId, reason}, {keepalive: true}).catch(() => {});
  }
  function stopQuestion() {
    lifecycle++;
    acquisitionId++; acquiring = false;
    cancelRealtime();
    clearInterval(recordingTimer); recordingTimer = null;
    for (const [timer, reject] of waits) {clearTimeout(timer); reject(interrupted());}
    waits.clear();
    uploadController?.abort(); uploadController = null; uploadBusy = false;
    playbackCancel?.();
    if (recorder) {
      recorder.ondataavailable = recorder.onstop = recorder.onerror = null;
      if (recorder.state !== 'inactive') {try {recorder.stop();} catch {}}
      recorder = null;
    }
    recorded = null; pendingText = null; revokePreview();
    flowBusy = false; pendingFlow = null; recoveryBusy = false;
    setPhase('interrupted'); status('PERTANYAAN DIJEDA');
    for (const id of ['record-controls', 'text-answer-area', 'use-text', 'stop-audio', 'retry-upload', 'replay', 'resume-flow', 'room-countdown', 'live-review']) node(id).hidden = true;
    node('answer-timer').textContent = '00:00'; node('interruption').hidden = false;
    node('retry-question').disabled = true; node('skip-question').disabled = true;
    if (current) markCandidate(current.id, 'Terhenti · Belum terkirim');
  }
  async function interruptQuestion(reason = 'reload', questionId = current?.id) {
    if (!available() || !active || !questionId || phase === 'finishing' || interruptBusy) return;
    if (phase !== 'interrupted') stopQuestion();
    interruptBusy = true; interruptionPending = true; rememberQuestion(true, questionId);
    const token = lifecycle;
    node('interruption-status').textContent = 'Menyimpan jeda. Hubungkan kembali internet bila terputus.';
    try {
      const result = await postData(`${base}/interrupt`, {question_id: questionId, reason}); guard(token);
      state = result.state; interruptionPending = false;
      if (result.already_completed) {
        node('interruption').hidden = true;
        markCandidate(questionId, 'Tersimpan');
        pendingFlow = async () => {if (state.current_turn) await presentQuestion(state.current_turn, {restart: true}); else await finish();};
        node('resume-flow').hidden = false;
        status('PERTANYAAN BERIKUTNYA SIAP');
        return;
      }
      recoveryState = state.checkpoint;
      node('interruption-status').textContent = 'Pilih Retry untuk mengulang atau Next untuk melewati.';
      node('retry-question').disabled = !desktopSupported || !recoveryState?.interruption_id;
      node('skip-question').disabled = !desktopSupported || !recoveryState?.interruption_id;
    } catch (cause) {
      if (available() && token === lifecycle) {showError('room-error', cause); node('interruption-status').textContent = 'Hubungkan kembali internet untuk melanjutkan.';}
    } finally {if (token === lifecycle) interruptBusy = false;}
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) return;
    if (active) interruptQuestion('tab_hidden');
    else if (startPending && startRequestSent) startAbandoned = true;
  });
  window.addEventListener('offline', () => interruptQuestion('offline'));
  window.addEventListener('online', () => {if (interruptionPending) interruptQuestion('offline');});
  window.addEventListener('pagehide', () => {
    if (active && !closed && phase !== 'finishing') interruptionBeacon(current?.id);
    else if (startPending && startRequestSent && !closed) {startAbandoned = true; interruptionBeacon(state?.current_turn?.id);}
    disposed = true;
    cleanup();
    active = false;
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    if (closed) {location.replace('/riwayat'); return;}
    disposed = false;
    renderMotion();
    if (!startPending) {ready = false; checkConnection(); poll();}
  });

  function cameraOn() {return !!stream?.getVideoTracks().some(track => track.readyState === 'live' && track.enabled);}
  function micOn() {return !!stream?.getAudioTracks().some(track => track.readyState === 'live' && track.enabled);}
  function preflightVerified() {
    const frames = cameraOn() && node('camera').videoWidth > 0 && node('camera').readyState >= 2;
    const connection = healthy && performance.now() - healthCheckedAt < 30000;
    const devicesVerified = frames && micOn() && micReady && soundTested && node('camera-check').checked && node('speaker-check').checked;
    return desktopSupported && ready && available() && !active && !acquiring && !soundTesting && connection &&
      node('focus-check').checked && (node('text-mode').checked || devicesVerified);
  }
  function checkReady() {
    node('start').disabled = startPending || !preflightVerified();
    node('speaker-check').disabled = !desktopSupported || !soundTested || soundTesting;
    node('devices').disabled = !desktopSupported || acquiring;
    node('test-sound').disabled = !desktopSupported || soundTesting;
    for (const id of ['camera-toggle', 'mic-toggle', 'camera-check', 'focus-check']) node(id).disabled = !desktopSupported;
    node('voice-mode').disabled = node('text-mode').disabled = !desktopSupported || startPending;
  }
  function renderDevices() {
    const video = cameraOn(), mic = micOn();
    buttonState('camera-toggle', video, 'Matikan kamera', 'Aktifkan kamera');
    buttonState('mic-toggle', mic, 'Matikan mikrofon', 'Aktifkan mikrofon');
    node('camera-off-placeholder').hidden = video;
    node('candidate-mic-status').textContent = mic ? 'Mikrofon aktif' : 'Mikrofon nonaktif';
    node('candidate-mic-status').classList.toggle('is-muted', !mic);
    if (phase === 'answer-ready') node('record').disabled = !mic || !active || flowBusy || answerWithText;
    if (!mic) node('mic-status').textContent = 'Aktifkan perangkat';
    checkReady();
  }
  function microphoneMeter(generation) {
    const values = new Uint8Array(micAnalyser.fftSize);
    function tick() {
      if (!available() || generation !== deviceGeneration || !stream || !micAnalyser) return;
      micAnalyser.getByteTimeDomainData(values);
      let energy = 0;
      for (const value of values) energy += ((value - 128) / 128) ** 2;
      const rms = micOn() && audioContext?.state === 'running' ? Math.sqrt(energy / values.length) : 0;
      node('mic-meter').value = Math.min(100, rms * 400);
      if (!micReady && !soundTesting && !speaking && rms > .015) {
        if (++micSamples >= 3) {micReady = true; node('mic-status').textContent = 'Terdeteksi';}
      } else if (!micReady) micSamples = 0;
      checkReady();
      meterFrame = requestAnimationFrame(tick);
    }
    tick();
  }
  function deviceError(cause, withCamera = true) {
    const device = withCamera ? 'kamera atau mikrofon' : 'mikrofon';
    return cause?.name === 'NotAllowedError' ? `Izin ${device} belum diberikan. Izinkan melalui pengaturan browser, lalu coba lagi.` :
      cause?.name === 'NotFoundError' ? `${withCamera ? 'Kamera atau mikrofon' : 'Mikrofon'} tidak ditemukan. Hubungkan perangkat, lalu coba lagi.` :
      cause?.message || 'Perangkat belum dapat diaktifkan. Pastikan tidak sedang dipakai aplikasi lain, lalu coba lagi.';
  }
  async function acquireDevices(withCamera = true) {
    if (!desktopSupported || !available() || (active && !['interrupted', 'answer-ready', 'enabling-microphone'].includes(phase)) || startPending || acquiring) return false;
    acquiring = true; clearError('preflight-error');
    const requestId = ++acquisitionId;
    const token = lifecycle;
    if (withCamera) stopStream();
    const generation = deviceGeneration;
    const valid = () => available() && token === lifecycle && requestId === acquisitionId && generation === deviceGeneration;
    node('devices').disabled = true;
    node('devices').textContent = 'Mengaktifkan perangkat…';
    if (withCamera) node('camera-check').checked = false;
    node('mic-status').textContent = 'Menunggu izin…';
    let acquired = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Gunakan browser terbaru melalui localhost atau HTTPS untuk kamera dan perekaman.');
      const contextPromise = ensureAudioContext();
      contextPromise.catch(() => {});
      // Returning from text only needs a microphone. An existing camera stays attached.
      if (!withCamera && stream?.getAudioTracks().some(track => track.readyState === 'live')) {
        await contextPromise;
        if (!valid()) return false;
        stream.getAudioTracks().forEach(track => {track.enabled = true;});
        if (state?.script.settings?.streaming_voice && !realtimeVoice) await setupRealtime(generation);
        return valid();
      }
      acquired = await navigator.mediaDevices.getUserMedia({video: withCamera ? {width: {ideal: 640}, height: {ideal: 480}, facingMode: 'user'} : false,
        audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
      if (!valid()) {acquired.getTracks().forEach(track => track.stop()); return false;}
      await contextPromise;
      if (!valid()) {acquired.getTracks().forEach(track => track.stop()); return false;}
      const retainedVideo = withCamera ? [] : (stream?.getVideoTracks().filter(track => track.readyState === 'live') || []);
      const previous = stream;
      cancelAnimationFrame(meterFrame); micSource?.disconnect();
      realtimeVoice?.destroy(); realtimeVoice = null;
      stream = retainedVideo.length ? new MediaStream([...retainedVideo, ...acquired.getAudioTracks()]) : acquired;
      previous?.getTracks().filter(track => !retainedVideo.includes(track)).forEach(track => track.stop());
      const attached = stream;
      node('camera').srcObject = stream;
      node('preflight-camera').srcObject = stream;
      if (stream.getVideoTracks().length) await Promise.all([node('camera').play(), node('preflight-camera').play()]);
      if (!valid()) {
        acquired.getTracks().forEach(track => track.stop());
        if (stream === attached) {node('camera').srcObject = node('preflight-camera').srcObject = null;}
        return false;
      }
      micAnalyser = audioContext.createAnalyser(); micAnalyser.fftSize = 256;
      micSource = audioContext.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
      micSource.connect(micAnalyser);
      micReady = false; micSamples = 0;
      node('mic-status').textContent = 'Ucapkan beberapa kata';
      microphoneMeter(generation);
      attached.getTracks().forEach(track => track.addEventListener('ended', () => {
        if (stream !== attached || generation !== deviceGeneration || !available()) return;
        micReady = false; micSamples = 0; renderDevices();
        if (active) {showError('room-error', 'Perangkat terputus. Pertanyaan dijeda.'); interruptQuestion('device_lost');}
        else {
          node('devices').textContent = 'Coba lagi';
          showError('preflight-error', 'Perangkat terputus. Hubungkan kembali lalu ulangi pemeriksaan.');
        }
      }));
      node('devices').textContent = 'Periksa ulang';
      if (state?.script.settings?.streaming_voice) await setupRealtime(generation);
      return valid();
    } catch (cause) {
      acquired?.getTracks().forEach(track => track.stop());
      if (valid()) {
        if (withCamera) stopStream();
        showError(withCamera ? 'preflight-error' : 'room-error', deviceError(cause, withCamera));
        node('devices').textContent = 'Coba lagi';
      }
      return false;
    } finally {
      if (requestId === acquisitionId) {
        acquiring = false;
        if (available()) {node('devices').disabled = false; renderDevices();}
      }
    }
  }
  node('devices').addEventListener('click', () => acquireDevices());
  function cancelRealtime() {
    const attempt = realtimeAttempt;
    realtimeAttempt = null; pendingBargeIn = false;
    clearTimeout(vadTimer); vadTimer = null;
    realtimeVoice?.cancel();
    node('live-review').hidden = true; node('live-transcript').value = '';
    if (attempt) {
      const key = `candidate:q:${attempt.questionId}`;
      const message = messages.get(key);
      if (message) {message.outer.remove(); messages.delete(key); lastMessageRole = lastMessageAuthor = null;}
      node('transcript').textContent = ''; node('transcript').hidden = true;
    }
  }
  function realtimeCurrent(attempt = realtimeAttempt) {
    return !!attempt && available() && active && attempt === realtimeAttempt && attempt.token === lifecycle &&
      attempt.questionId === current?.id && attempt.voice === realtimeVoice;
  }
  function realtimeFailed(cause, attempt) {
    if (!realtimeCurrent(attempt)) return;
    cancelRealtime(); clearInterval(recordingTimer); recordingTimer = null;
    if (cause.transportLost || navigator.onLine === false) {interruptQuestion('offline'); return;}
    node('realtime-mode').checked = false;
    setPhase('answer-ready'); status('GUNAKAN REKAMAN BIASA / TEKS');
    node('record').hidden = false; node('record').disabled = !micOn(); node('record').textContent = 'Mulai rekam suara';
    node('answer-timer').textContent = formatTime(state.answer_seconds);
    renderAnswerMode(); showError('room-error', cause);
  }
  async function setupRealtime(generation) {
    let voice;
    try {
      if (!window.RealtimeVoice) throw new Error('Audio realtime belum tersedia.');
      voice = new window.RealtimeVoice(stream, {
        onTranscript: text => {
          if (!realtimeCurrent() || !['connecting', 'recording', 'transcribing'].includes(phase)) return;
          candidateMessage(current.id, text, 'Transkrip sementara');
        },
        onSpeech: type => {
          if (!realtimeCurrent() || phase !== 'recording') return;
          clearTimeout(vadTimer); vadTimer = null;
          if (type === 'speech_started') status('MENDENGARKAN ANDA');
          else {
            status(node('auto-send').checked ? 'JEDA BICARA · AKAN DIKIRIM' : 'JEDA TERDETEKSI · SILAKAN LANJUT');
            const attempt = realtimeAttempt;
            if (node('auto-send').checked) vadTimer = setTimeout(() => {
              if (realtimeCurrent(attempt) && node('auto-send').checked && !document.hidden) stopRealtime(false, true);
            }, 1800);
          }
        },
        onActivity: () => {
          if (voice !== realtimeVoice || !available() || !active || phase !== 'speaking' || !current || answerWithText ||
            !micOn() || !node('barge-in').checked || !node('realtime-mode').checked || document.hidden) return;
          // Only a question can hand control to the microphone; acknowledgements and closing keep their flow.
          if (!playbackStop || !interviewerAudio.src || !captionText || captionText !== current.question_text) return;
          pendingBargeIn = true; playbackStop();
        },
        onError: cause => {if (voice === realtimeVoice) realtimeFailed(cause, realtimeAttempt);}
      });
      realtimeVoice = voice;
      await voice.initialize();
      if (!available() || generation !== deviceGeneration || realtimeVoice !== voice) {voice.destroy(); return;}
    } catch {
      voice?.destroy();
      if (!available() || generation !== deviceGeneration || (voice && realtimeVoice !== voice)) return;
      realtimeVoice = null; node('realtime-mode').checked = false;
      showError('preflight-error', 'Audio realtime tidak didukung di browser ini. Rekaman biasa dan teks tetap tersedia.');
    }
  }
  node('auto-send').addEventListener('change', () => {if (!node('auto-send').checked) {clearTimeout(vadTimer); vadTimer = null;}});
  for (const mode of ['voice', 'text']) node(`${mode}-mode`).addEventListener('change', () => {
    selectAnswerMode(mode);
    checkReady();
  });
  for (const id of ['camera-check', 'speaker-check', 'focus-check']) node(id).addEventListener('change', checkReady);
  for (const id of ['camera', 'preflight-camera']) for (const event of ['loadeddata', 'loadedmetadata', 'playing', 'resize']) node(id).addEventListener(event, checkReady);
  node('test-sound').addEventListener('click', async () => {
    if (!desktopSupported || !available() || active || startPending || soundTesting) return;
    const token = lifecycle;
    soundTesting = true; soundTested = false;
    node('test-sound').disabled = true; node('speaker-check').checked = false;
    checkReady(); clearError('preflight-error');
    let oscillator = null, gain = null;
    try {
      const context = await ensureAudioContext(); guard(token);
      oscillator = context.createOscillator(); gain = context.createGain();
      oscillator.frequency.value = 523; gain.gain.value = .12;
      oscillator.connect(gain); gain.connect(context.destination);
      testTone = oscillator;
      oscillator.onended = () => {
        oscillator.disconnect(); gain.disconnect();
        if (!available() || token !== lifecycle) return;
        testTone = null; soundTesting = false; soundTested = true;
        node('test-sound').disabled = false;
        node('test-sound').textContent = 'Tes lagi';
        checkReady();
      };
      oscillator.start(); oscillator.stop(context.currentTime + .45);
    } catch (cause) {
      oscillator?.disconnect(); gain?.disconnect();
      if (available() && token === lifecycle) {soundTesting = false; node('test-sound').disabled = false; showError('preflight-error', cause); checkReady();}
    }
  });

  async function checkConnection() {
    if (!available() || active || healthController) return;
    const token = lifecycle;
    const controller = new AbortController(); healthController = controller;
    const timeout = setTimeout(() => controller.abort(), 8000);
    node('connection-status').textContent = 'Memeriksa…';
    node('connection-retry').disabled = true;
    try {
      const data = await requestJSON('/health', {signal: controller.signal}); guard(token);
      if (data.ok !== true || data.db === false || data.redis === false) throw new Error('Koneksi aplikasi belum tersedia.');
      healthy = true; healthCheckedAt = performance.now();
      node('connection-status').textContent = 'Terhubung';
      node('connection-retry').hidden = true;
    } catch {
      if (available() && token === lifecycle) {
        healthy = false;
        node('connection-status').textContent = 'Terputus';
        node('connection-retry').hidden = false;
      }
    } finally {
      clearTimeout(timeout);
      if (healthController === controller) healthController = null;
      if (available() && token === lifecycle) {
        node('connection-retry').disabled = false; checkReady();
        if (!active && !healthTimer) healthTimer = setInterval(() => checkConnection(), 15000);
      }
    }
  }
  node('connection-retry').addEventListener('click', checkConnection);
  function openPreflight() {
    if (!ready || !available() || active || startPending) return;
    node('preflight').hidden = false;
    if (!node('preflight').open) node('preflight').showModal();
    checkReady(); checkConnection();
  }
  node('open-preflight').addEventListener('click', openPreflight);
  node('close-preflight').addEventListener('click', () => {if (!startPending) node('preflight').close();});
  node('preflight').addEventListener('cancel', event => {if (startPending) event.preventDefault();});

  function toggleTrack(kind) {
    if (!desktopSupported || !available()) return;
    const tracks = kind === 'video' ? stream?.getVideoTracks() : stream?.getAudioTracks();
    if (!tracks?.some(track => track.readyState === 'live')) {if (!active) openPreflight(); acquireDevices(); return;}
    const enabled = !tracks.some(track => track.readyState === 'live' && track.enabled);
    tracks.forEach(track => {track.enabled = enabled;});
    if (!enabled && kind === 'audio') {
      if (phase === 'recording') stopRecording();
      if (!active) {micReady = false; micSamples = 0;}
    }
    if (!enabled && kind === 'video' && !active) node('camera-check').checked = false;
    renderDevices();
  }
  node('camera-toggle').addEventListener('click', () => toggleTrack('video'));
  node('mic-toggle').addEventListener('click', () => toggleTrack('audio'));
  function mirror(enabled) {
    for (const id of ['camera', 'preflight-camera']) node(id).classList.toggle('is-mirrored', enabled);
    buttonState('mirror-toggle', enabled, 'Nonaktifkan cermin kamera', 'Cerminkan kamera');
    storage('sessionStorage', 'setItem', 'preptiva-mirror', String(enabled));
  }
  let savedMirror = false;
  try {savedMirror = sessionStorage.getItem('preptiva-mirror') === 'true';} catch {}
  mirror(savedMirror);
  node('mirror-toggle').addEventListener('click', () => mirror(node('mirror-toggle').getAttribute('aria-pressed') !== 'true'));
  async function fullscreen(forceOpen = false) {
    try {
      if (document.fullscreenElement) {if (!forceOpen) await document.exitFullscreen();}
      else await document.documentElement.requestFullscreen();
    } catch {showError(active ? 'room-error' : 'preflight-error', 'Fullscreen belum tersedia. Anda tetap dapat melanjutkan sesi.');}
  }
  node('fullscreen').disabled = !desktopSupported || !document.fullscreenEnabled;
  node('fullscreen-check').disabled = !desktopSupported || !document.fullscreenEnabled;
  node('fullscreen').addEventListener('click', () => fullscreen());
  document.addEventListener('fullscreenchange', () => buttonState('fullscreen', !!document.fullscreenElement, 'Keluar fullscreen', 'Buka fullscreen'));
  buttonState('fullscreen', !!document.fullscreenElement, 'Keluar fullscreen', 'Buka fullscreen');
  document.addEventListener('pointerdown', event => {if (node('room-tools')?.open && !node('room-tools').contains(event.target)) node('room-tools').open = false;});
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && node('room-tools')?.open) {node('room-tools').open = false; node('room-tools').querySelector('summary')?.focus();}
  });

  async function runFlow(flow) {
    if (!available() || !active || flowBusy) return;
    const token = lifecycle;
    flowBusy = true; pendingFlow = flow;
    node('resume-flow').hidden = true; clearError('room-error');
    try {
      await flow();
      if (available() && token === lifecycle) pendingFlow = null;
    } catch (cause) {
      if (available() && active && token === lifecycle && phase !== 'interrupted') {
        setPhase('audio-recovery'); status('PERLU DILANJUTKAN');
        showError('room-error', cause); node('resume-flow').hidden = false;
      }
    } finally {if (token === lifecycle) {flowBusy = false; if (available()) renderDevices();}}
  }
  node('resume-flow').addEventListener('click', () => {
    if (!pendingFlow || flowBusy) return;
    if (audioContext?.state === 'suspended') audioContext.resume().catch(() => {});
    runFlow(pendingFlow);
  });
  function delay(milliseconds) {
    const token = lifecycle;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {waits.delete(timer); try {guard(token); resolve();} catch (cause) {reject(cause);}}, milliseconds);
      waits.set(timer, reject);
    });
  }
  async function countdown() {
    node('room-countdown').hidden = false;
    setPhase('countdown'); status('BERSIAP');
    for (const number of ['3', '2', '1']) {guard(); node('countdown-number').textContent = number; await delay(1000);}
    node('room-countdown').hidden = true;
  }
  function renderAnswerMode() {
    const usable = available() && active && ['answer-ready', 'recorded', 'upload-error'].includes(phase);
    node('record-controls').hidden = !usable || answerWithText;
    node('text-answer-area').hidden = !usable || !answerWithText;
    node('use-text').hidden = !usable || answerWithText;
    node('use-voice').disabled = !usable || acquiring;
    node('send-text').disabled = !usable || !answerWithText || !node('text-answer').value.trim() || node('text-answer').value.length > 8000;
    node('answer-mode-status').hidden = !active;
    if (answerWithText) {
      node('answer-preview').pause(); node('answer-preview').hidden = true;
      node('live-review').hidden = true;
    }
    renderDevices();
  }
  node('text-answer').addEventListener('input', renderAnswerMode);
  node('use-text').addEventListener('click', () => {
    if (!available() || !active || flowBusy || !['answer-ready', 'recorded', 'upload-error'].includes(phase)) return;
    selectAnswerMode('text'); pendingBargeIn = false; pendingText = null;
    node('retry-upload').hidden = true;
    setPhase('answer-ready'); status('GILIRAN ANDA · MODE TEKS');
    renderAnswerMode();
    node('text-answer').focus();
  });
  node('use-voice').addEventListener('click', async () => {
    if (!available() || !active || flowBusy || !answerWithText || !['answer-ready', 'upload-error'].includes(phase)) return;
    const token = lifecycle, questionId = current?.id;
    node('use-voice').disabled = true; node('send-text').disabled = true;
    clearError('room-error'); setPhase('enabling-microphone'); status('MENGAKTIFKAN MIKROFON');
    const enabled = await acquireDevices(false);
    if (!available() || !active || token !== lifecycle || current?.id !== questionId || phase !== 'enabling-microphone') return;
    if (!enabled) {
      setPhase('answer-ready'); status('GILIRAN ANDA · MODE TEKS'); renderAnswerMode();
      return;
    }
    selectAnswerMode('voice'); pendingText = null;
    node('retry-upload').hidden = true;
    node('record').hidden = !!recorded; node('record').textContent = 'Mulai rekam suara';
    node('send').hidden = !recorded; node('send').disabled = false;
    node('retry').hidden = !recorded || retries >= state.retry_limit;
    node('replay').hidden = !!recorded || !current.audio_url;
    node('answer-preview').hidden = !recorded?.blob;
    node('live-review').hidden = !recorded?.capture_token;
    node('answer-timer').textContent = formatTime(state.answer_seconds);
    setPhase(recorded ? 'recorded' : 'answer-ready'); status(recorded ? 'TINJAU JAWABAN' : 'GILIRAN ANDA');
    renderAnswerMode();
  });
  async function presentQuestion(question, {restart = false} = {}) {
    guard();
    if (!question?.id) throw new Error('Pertanyaan berikutnya belum tersedia. Coba lanjutkan lagi.');
    const token = lifecycle;
    if (current?.id !== question.id || restart) {
      cancelRealtime(); pendingBargeIn = false;
      current = question; retries = 0; recorded = null; pendingText = null; revokePreview();
      node('text-answer').value = '';
      node('transcript').textContent = ''; node('transcript').hidden = true;
      node('send').hidden = true; node('retry').hidden = true;
    }
    current = question; rememberQuestion();
    if (restart) spoken.delete(`question:${question.id}`);
    node('interruption').hidden = true; node('text-answer-area').hidden = true; node('use-text').hidden = true;
    showInterviewer(question.persona || question.interviewer || state.persona, question.interviewer);
    const progress = `${question.kind === 'follow_up' ? 'PENGGALIAN LANJUTAN' : 'PERTANYAAN'} ${question.main_order} / ${state.question_count}`;
    node('question-progress').textContent = progress;
    node('chat-progress').textContent = progress;
    node('question-text').textContent = question.question_text;
    await utterance(`question:${question.id}`, question.question_text, question.audio_url);
    guard(token);
    setPhase('answer-ready'); status('GILIRAN ANDA');
    node('record-controls').hidden = false; node('record').hidden = false;
    node('record').textContent = 'Mulai rekam suara'; node('record').disabled = !micOn();
    node('send').hidden = true; node('retry').hidden = true; node('replay').hidden = !question.audio_url;
    node('answer-timer').textContent = formatTime(state.answer_seconds);
    if (!micOn()) selectAnswerMode('text');
    else selectAnswerMode(answerWithText ? 'text' : 'voice');
    renderAnswerMode();
    if (pendingBargeIn && !answerWithText) {pendingBargeIn = false; await startRealtime();}
  }
  node('start').addEventListener('click', async () => {
    checkReady();
    if (node('start').disabled || startPending || active || !available()) return;
    const token = lifecycle;
    startPending = true; startAbandoned = false; startRequestSent = false;
    node('start').disabled = true; node('close-preflight').disabled = true;
    clearError('preflight-error'); clearError('room-error');
    try {
      if (!node('text-mode').checked) await ensureAudioContext();
      guard(token);
      if (node('fullscreen-check').checked && !document.fullscreenElement) await fullscreen(true);
      guard(token);
      if (document.hidden) throw new Error('Kembali ke halaman ini untuk memulai sesi.');
      if (!preflightVerified()) throw new Error('Pemeriksaan perangkat berubah. Periksa kembali kamera, mikrofon, suara, dan koneksi sebelum memulai.');
      startRequestSent = true;
      await post(`${base}/start`, {headers: {'X-Preptiva-Device': desktopSupported ? 'desktop' : 'mobile'}});
      if (closed) {sendClose(); return;}
      if (!available() || token !== lifecycle) {
        interruptionBeacon(state.current_turn?.id);
        return;
      }
      const resuming = state.status === 'running';
      active = true; state.status = 'running'; current = state.current_turn;
      answerWithText = node('text-mode').checked;
      clearInterval(healthTimer); healthTimer = null;
      node('preflight').close(); node('open-preflight').hidden = true;
      sessionStartedAt = performance.now();
      elapsedTimer = setInterval(() => {node('elapsed-time').textContent = formatTime((performance.now() - sessionStartedAt) / 1000);}, 1000);
      if (!current) {await runFlow(finish); return;}
      if (resuming || startAbandoned || document.hidden) {
        const interruptedId = resuming ? savedQuestion() || current.id : current.id;
        await interruptQuestion(document.hidden ? 'tab_hidden' : 'reload', interruptedId);
        return;
      }
      rememberQuestion();
      const begin = async () => {
        if (!spoken.has('countdown')) {await countdown(); spoken.add('countdown');}
        showInterviewer(state.script.intro?.persona || state.persona);
        await utterance('intro', state.script.intro?.text, state.script.intro?.audio_url);
        await presentQuestion(state.current_turn);
      };
      await runFlow(begin);
    } catch (cause) {
      if (available()) {showError('preflight-error', cause); checkReady();}
    } finally {
      startPending = false;
      if (available()) {node('close-preflight').disabled = false; checkReady();}
    }
  });
  node('replay').addEventListener('click', async () => {
    if (!available() || !active || phase !== 'answer-ready' || flowBusy || !current) return;
    flowBusy = true; node('record').disabled = true; node('replay').hidden = true;
    try {await play(current.audio_url, current.question_text);} catch {if (available()) showError('room-error', 'Audio belum dapat diputar. Coba putar ulang pertanyaan.');}
    finally {flowBusy = false; if (available() && active && phase === 'answer-ready') {node('replay').hidden = !current.audio_url; renderAnswerMode();}}
  });

  function stopRecording(timedOut = false) {
    if (realtimeAttempt) {stopRealtime(timedOut); return;}
    if (!recorder || recorder.state !== 'recording') return;
    endOfTurnAt = performance.now();
    clearInterval(recordingTimer); recordingTimer = null;
    recorder.timedOut = timedOut;
    recorder.stop();
    node('record').hidden = true;
  }
  node('record').addEventListener('click', () => {
    if (!available() || !active || flowBusy) return;
    if (phase === 'recording') {stopRecording(); return;}
    if (phase !== 'answer-ready' || !current || !micOn() || answerWithText) return;
    if (node('realtime-mode').checked && realtimeVoice) {startRealtime(); return;}
    const token = lifecycle;
    const questionId = current.id;
    let capture;
    try {
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      capture = new MediaRecorder(new MediaStream(stream.getAudioTracks()), {...(mime ? {mimeType: mime} : {}), audioBitsPerSecond: 64000});
      const parts = [];
      recorder = capture; recordingStart = performance.now();
      capture.ondataavailable = event => {if (event.data.size && available() && token === lifecycle) parts.push(event.data);};
      capture.onstop = () => {
        if (!available() || !active || token !== lifecycle || current?.id !== questionId || recorder !== capture) return;
        clearInterval(recordingTimer); recordingTimer = null;
        const blob = new Blob(parts, {type: capture.mimeType});
        if (!blob.size) {setPhase('answer-ready'); node('record').hidden = false; node('record').textContent = 'Mulai rekam suara'; renderDevices(); showError('room-error', 'Audio belum terekam. Coba mulai jawab lagi.'); return;}
        recorded = {blob, questionId, duration: Math.max(100, Math.round(performance.now() - recordingStart)), timedOut: !!capture.timedOut};
        recorder = null; revokePreview();
        previewUrl = URL.createObjectURL(blob); node('answer-preview').src = previewUrl; node('answer-preview').hidden = false;
        setPhase('recorded'); status('TINJAU JAWABAN');
        node('record').hidden = true; node('send').hidden = false; node('send').disabled = false;
        node('retry').hidden = retries >= state.retry_limit; node('replay').hidden = true;
        renderAnswerMode();
      };
      capture.onerror = () => {if (available() && token === lifecycle) {showError('room-error', 'Perekaman terhenti. Tinjau audio sebelum mengirim.'); stopRecording();}};
      capture.start(500);
      setPhase('recording'); status('MEREKAM'); clearError('room-error');
      node('use-text').hidden = true;
      node('record').textContent = 'Selesai merekam'; node('replay').hidden = true;
      recordingTimer = setInterval(() => {
        const remaining = Math.max(0, state.answer_seconds - Math.floor((performance.now() - recordingStart) / 1000));
        node('answer-timer').textContent = formatTime(remaining);
        if (!remaining) stopRecording(true);
      }, 200);
    } catch (cause) {
      if (capture && capture.state !== 'inactive') {try {capture.stop();} catch {}}
      recorder = null; showError('room-error', cause);
    }
  });
  async function startRealtime() {
    if (!available() || !active || !current || !micOn() || answerWithText || !realtimeVoice || realtimeAttempt || phase !== 'answer-ready') return;
    const attempt = {token: lifecycle, questionId: current.id, voice: realtimeVoice};
    realtimeAttempt = attempt; recorded = null; recordingStart = performance.now();
    node('live-review').hidden = true; node('transcript').textContent = ''; node('transcript').hidden = true;
    node('record-controls').hidden = false; node('record').hidden = false; node('record').disabled = true;
    for (const id of ['send', 'retry', 'replay', 'use-text']) node(id).hidden = true;
    clearError('room-error'); setPhase('connecting'); status('MENGHUBUNGKAN MIKROFON');
    try {
      await attempt.voice.start(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${base}/voice/${encodeURIComponent(attempt.questionId)}`);
      if (!realtimeCurrent(attempt)) return;
      setPhase('recording'); status('MENDENGARKAN ANDA');
      node('record').disabled = false; node('record').textContent = 'Selesai bicara';
      recordingTimer = setInterval(() => {
        if (!realtimeCurrent(attempt)) return;
        const remaining = Math.max(0, state.answer_seconds - Math.floor((performance.now() - recordingStart) / 1000));
        node('answer-timer').textContent = formatTime(remaining);
        if (!remaining) stopRealtime(true);
      }, 200);
    } catch (cause) {if (cause.name !== 'AbortError') realtimeFailed(cause, attempt);}
  }
  async function stopRealtime(timedOut = false, autoSend = false) {
    const attempt = realtimeAttempt;
    if (!realtimeCurrent(attempt) || !['recording', 'connecting'].includes(phase)) return;
    clearInterval(recordingTimer); recordingTimer = null; clearTimeout(vadTimer); vadTimer = null;
    endOfTurnAt = performance.now();
    node('record').hidden = true; setPhase('transcribing'); status('MENUNTASKAN TRANSKRIP');
    try {
      const result = await attempt.voice.finish();
      if (!realtimeCurrent(attempt)) return;
      realtimeAttempt = null;
      recorded = {capture_token: result.capture_token, transcript: result.transcript, duration: result.duration_ms, timedOut, questionId: attempt.questionId};
      candidateMessage(attempt.questionId, result.transcript, 'Belum terkirim');
      node('live-transcript').value = result.transcript; node('live-review').hidden = false;
      setPhase('recorded'); status('TINJAU TRANSKRIP');
      node('send').hidden = false; node('send').disabled = false; node('retry').hidden = retries >= state.retry_limit;
      node('use-text').hidden = false;
      if (autoSend && node('auto-send').checked && !document.hidden) await upload();
    } catch (cause) {if (cause.name !== 'AbortError') realtimeFailed(cause, attempt);}
  }
  node('retry').addEventListener('click', () => {
    if (!available() || !active || retries >= state.retry_limit || phase !== 'recorded' || uploadBusy) return;
    retries++; cancelRealtime(); recorded = null; revokePreview(); setPhase('answer-ready'); status('GILIRAN ANDA');
    node('record').hidden = false; node('record').textContent = 'Mulai rekam suara';
    node('send').hidden = true; node('retry').hidden = true; node('replay').hidden = false;
    node('answer-timer').textContent = formatTime(state.answer_seconds); renderAnswerMode();
  });

  async function navigateResults() {
    active = false; closed = true; localMarker('removeItem'); cleanup();
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
    if (!disposed) location.replace(`/sesi/${encodeURIComponent(sid)}/hasil`);
  }
  async function finish() {
    guard(); setPhase('finishing'); status('MENILAI');
    const token = lifecycle;
    try {await post(`${base}/finish`); guard(token);} catch (cause) {
      guard(token);
      const latest = await requestJSON(`${base}/state`).catch(() => null); guard(token);
      if (!['done', 'scoring', 'evaluation_failed'].includes(latest?.status)) throw cause;
    }
    await navigateResults();
  }
  async function recoverQuestion(action) {
    if (!available() || !active || !desktopSupported || recoveryBusy || phase !== 'interrupted' || !recoveryState?.interruption_id) return;
    recoveryBusy = true;
    const token = lifecycle;
    const saved = {...recoveryState};
    node('retry-question').disabled = true; node('skip-question').disabled = true;
    setPhase('recovering'); clearError('room-error');
    try {
      const result = await postData(`${base}/recover`, {question_id: saved.question_id, interruption_id: saved.interruption_id, action}); guard(token);
      recoveryState = null; interruptionPending = false;
      node('interruption').hidden = true;
      if (action === 'retry') {state = result; await runFlow(() => presentQuestion(state.current_turn, {restart: true}));}
      else await handleResult(result, saved.question_id);
    } catch (cause) {
      if (available() && token === lifecycle) {
        setPhase('interrupted'); showError('room-error', cause);
        node('interruption').hidden = false;
        node('retry-question').disabled = false; node('skip-question').disabled = false;
      }
    } finally {if (token === lifecycle) recoveryBusy = false;}
  }
  node('retry-question').addEventListener('click', () => recoverQuestion('retry'));
  node('skip-question').addEventListener('click', () => recoverQuestion('next'));
  async function handleResult(result, questionId) {
    guard();
    latencyAnswer = result.answer_id ?? null;
    node('retry-upload').hidden = true;
    if (result.skipped) {
      markCandidate(questionId, 'Dilewati');
      upsertMessage(`skipped:${questionId}`, 'system', 'Pertanyaan dilewati.');
    } else candidateMessage(questionId, result.transcript || node('transcript').textContent, 'Terkirim', result.answer_id);
    recorded = null; pendingText = null; revokePreview(); node('live-review').hidden = true;
    const key = result.answer_id == null ? `question:${questionId}` : `answer:${result.answer_id}`;
    if (!resultFlows.has(key)) {
      resultFlows.set(key, async () => {
        if (result.follow_up_question) {
          // A follow-up is the response itself; both URLs point at the same utterance.
          await presentQuestion(result.follow_up_question);
          return;
        }
        showInterviewer(result.response_interviewer || current?.persona || current?.interviewer || state.persona);
        if (!result.skipped) await utterance(`response:${key}`, result.response_text, result.response_audio_url);
        if (result.is_last) {
          const closing = result.closing || state.script.closing;
          showInterviewer(closing?.persona || speakerPersona, closing?.persona ? undefined : speakerRole);
          await utterance('closing', closing?.text, closing?.audio_url);
          await finish();
        } else await presentQuestion(result.next_question);
      });
    }
    await runFlow(resultFlows.get(key));
  }
  async function readAnswer(response, questionId, token) {
    if (!response.body?.getReader) return response.json();
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '', result = null;
    function consume(line) {
      if (!line.trim()) return;
      guard(token);
      const event = JSON.parse(line);
      if (event.type === 'transcript') {
        candidateMessage(questionId, event.transcript, '');
        if (!result) setChatActivity(`${speakerPersona?.name || state.persona.name} merespons…`);
      } else if (event.type === 'error') {
        setChatActivity();
        throw new Error(event.message || 'Pemrosesan gagal. Kirim ulang jawaban yang sama.');
      } else if (event.type === 'result') {result = event; setChatActivity();}
    }
    try {
      while (true) {
        const {value, done} = await reader.read(); guard(token);
        pending += decoder.decode(value || new Uint8Array(), {stream: !done});
        const lines = pending.split('\n'); pending = lines.pop();
        for (const line of lines) consume(line);
        if (done) {consume(pending); break;}
      }
    } catch (cause) {await reader.cancel().catch(() => {}); throw cause;}
    finally {reader.releaseLock();}
    if (!result) {const cause = new Error('Koneksi terputus. Pertanyaan dijeda.'); cause.name = 'NetworkError'; throw cause;}
    return result;
  }
  async function upload(textAnswer = null) {
    const text = typeof textAnswer === 'string' ? textAnswer.trim() : pendingText?.text;
    const textSubmission = text != null;
    if (!available() || !active || uploadBusy || !current || phase === 'interrupted') return;
    if (textSubmission ? !text || text.length > 8000 || !['answer-ready', 'upload-error'].includes(phase) :
      !recorded || recorded.questionId !== current.id || !['recorded', 'upload-error'].includes(phase)) return;
    uploadBusy = true;
    const answer = recorded, questionId = current.id, token = lifecycle;
    if (textSubmission) pendingText = {text, questionId};
    const controller = new AbortController(); uploadController = controller;
    node('send').hidden = true; node('retry').hidden = true; node('retry-upload').hidden = true;
    node('answer-preview').pause(); node('answer-preview').hidden = true; clearError('room-error');
    node('text-answer-area').hidden = true; node('use-text').hidden = true; node('send-text').disabled = true;
    node('live-review').hidden = true;
    setPhase('processing'); status('MEMPROSES');
    setChatActivity('Memproses jawaban…');
    const candidateKey = `candidate:q:${questionId}`;
    if (textSubmission) {endOfTurnAt = performance.now(); candidateMessage(questionId, text, 'Memproses…');}
    else if (answer.capture_token) candidateMessage(questionId, node('live-transcript').value.trim() || answer.transcript, 'Memproses…');
    else if (!messages.has(candidateKey)) upsertMessage(candidateKey, 'candidate', 'Jawaban suara', 'Memproses transkrip…');
    else markCandidate(questionId, 'Memproses ulang…');
    const form = new FormData();
    form.append('question_id', String(questionId)); form.append('retry_count', String(retries));
    if (textSubmission) {form.append('text_answer', text); form.append('duration_ms', '100');}
    else if (answer.capture_token) {
      form.append('capture_token', answer.capture_token); form.append('duration_ms', String(answer.duration)); form.append('timed_out', String(answer.timedOut));
      const corrected = node('live-transcript').value.trim();
      if (corrected && corrected !== answer.transcript) form.append('corrected_transcript', corrected);
    }
    else {
      const extension = answer.blob.type.includes('mp4') ? 'mp4' : answer.blob.type.includes('ogg') ? 'ogg' : 'webm';
      form.append('audio', answer.blob, `answer.${extension}`); form.append('duration_ms', String(answer.duration)); form.append('timed_out', String(answer.timedOut));
    }
    let result;
    try {
      const response = await fetch(`${base}/answers?stream=true`, {method: 'POST', credentials: 'same-origin', body: form, signal: controller.signal});
      guard(token);
      if (!response.ok) throw await responseError(response, 'Jawaban belum dapat dikirim. Coba kirim ulang.');
      result = await readAnswer(response, questionId, token); guard(token);
    } catch (cause) {
      if (available() && token === lifecycle) {
        if (cause instanceof TypeError || cause.name === 'NetworkError' || (typeof navigator.onLine === 'boolean' && !navigator.onLine)) {
          await interruptQuestion('offline'); return;
        }
        setPhase('upload-error'); status('PERLU DIKIRIM ULANG'); showError('room-error', cause);
        markCandidate(questionId, 'Belum terkonfirmasi');
        node('retry-upload').hidden = false;
        renderAnswerMode();
      }
    } finally {
      if (uploadController === controller) {uploadBusy = false; uploadController = null; setChatActivity();}
    }
    if (result && available() && token === lifecycle) await handleResult(result, questionId);
  }
  node('send').addEventListener('click', () => upload());
  node('retry-upload').addEventListener('click', () => upload());
  node('send-text').addEventListener('click', () => {if (!node('send-text').disabled) upload(node('text-answer').value);});

  node('leave-room').addEventListener('click', () => {if (available() && !node('leave-dialog').open) node('leave-dialog').showModal();});
  node('cancel-leave').addEventListener('click', () => {if (!leavePending) node('leave-dialog').close();});
  node('leave-dialog').addEventListener('cancel', event => {if (leavePending) event.preventDefault();});
  node('confirm-leave').addEventListener('click', async () => {
    if (leavePending || disposed) return;
    leavePending = true; node('confirm-leave').disabled = true; node('cancel-leave').disabled = true;
    closed = true; active = false; localMarker('setItem', 'closed'); cleanup(); status('SESI DITUTUP');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {await post(`${base}/close`, {signal: controller.signal, keepalive: true});} catch {sendClose();}
    finally {
      clearTimeout(timeout);
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
      if (!disposed) location.replace('/riwayat');
    }
  });

  function renderSession() {
    node('realtime-mode').disabled = !desktopSupported || !state.script.settings?.streaming_voice;
    if (node('realtime-mode').disabled) node('realtime-mode').checked = false;
    node('auto-send').disabled = node('barge-in').disabled = node('realtime-mode').disabled;
    node('room-title').textContent = `Latihan ${state.job_role}`;
    node('room-subtitle').textContent = `${state.level} · ${state.question_count} pertanyaan · ${state.answer_seconds} detik per jawaban`;
    if ((state.panel || []).length > 1) node('room-subtitle').textContent += ` · Panel ${state.panel.length}`;
    showInterviewer(state.current_turn?.persona || state.persona, state.current_turn?.interviewer || state.interviewer);
    node('participant-count').textContent = `${(state.panel?.length || 1) + 1} peserta`;
  }
  function terminal(cause) {
    ready = false; active = false; closed = true; cleanup();
    node('preflight').close(); node('open-preflight').hidden = true;
    status('SESI DITUTUP'); showError('room-error', cause);
  }
  async function poll() {
    if (!available() || active || pollController) return;
    const token = lifecycle;
    const controller = new AbortController(); pollController = controller;
    try {
      const fetched = await requestJSON(`${base}/state`, {signal: controller.signal}); guard(token);
      state = fetched;
      if (state.status === 'failed') {localMarker('removeItem'); terminal(state.error || 'Sesi telah ditutup. Buat latihan baru dari menu Simulasi baru.'); return;}
      if (['done', 'scoring', 'evaluation_failed'].includes(state.status)) {
        localMarker('removeItem'); closed = true; cleanup(); location.replace(`/sesi/${encodeURIComponent(sid)}/hasil`); return;
      }
      renderSession();
      if (state.status === 'preparing') {status('MENYIAPKAN RUANG'); pollTimer = setTimeout(poll, 1500); return;}
      if (!['ready', 'running'].includes(state.status)) throw new Error('Status sesi belum dikenali. Coba muat ulang halaman.');
      ready = true; setPhase('ready'); status(desktopSupported ? 'SIAP DIMULAI' : 'WAJIB PC / LAPTOP');
      node('question-progress').textContent = 'RUANG ANDA SUDAH SIAP';
      node('chat-progress').textContent = `${state.question_count} pertanyaan`;
      node('question-text').textContent = 'Periksa kamera, mikrofon, dan suara sebelum memulai percakapan.';
      node('open-preflight').disabled = false;
      node('open-preflight').hidden = false;
      node('start').textContent = state.status === 'running' ? 'Lanjutkan sesi' : 'Mulai wawancara';
      checkReady();
      if (!openedPreflight || state.status === 'running') {openedPreflight = true; openPreflight();}
      else checkConnection();
    } catch (cause) {
      if (available() && token === lifecycle) {showError('room-error', cause); status('KONEKSI TERPUTUS'); pollTimer = setTimeout(poll, 3000);}
    } finally {if (pollController === controller) pollController = null;}
  }
  node('elapsed-time').textContent = '00:00';
  setChatActivity();
  node('chat-new-messages').hidden = true;
  node('open-preflight').disabled = true;
  node('record-controls').hidden = true;
  node('answer-preview').hidden = true;
  node('retry-upload').hidden = true;
  node('resume-flow').hidden = true;
  node('room-countdown').hidden = true;
  for (const id of ['interruption', 'text-answer-area', 'use-text', 'stop-audio', 'live-review']) node(id).hidden = true;
  node('device-status').textContent = desktopSupported ? 'PC / laptop terdeteksi' : 'HP / tablet tidak didukung';
  node('device-requirement').hidden = desktopSupported;
  node('preflight').classList.toggle('is-unsupported-device', !desktopSupported);
  if (!desktopSupported) {
    node('preflight-title').textContent = 'Gunakan PC atau laptop';
    node('preflight-description').textContent = 'HP dan tablet tidak didukung untuk wawancara.';
    node('verification-status').textContent = 'Buka sesi ini melalui PC atau laptop.';
    node('open-preflight').textContent = 'Wajib PC / laptop';
    node('start').textContent = 'Gunakan PC atau laptop';
  }
  renderDevices();
  poll();
})();
