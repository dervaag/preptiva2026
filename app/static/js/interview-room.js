'use strict';
(() => {
  const sid = document.body.dataset.sid;
  const base = `/api/sessions/${sid}`;
  const marker = `preptiva-active-${sid}`;
  let state, current, stream, context, analyser, meterFrame, recorder, recorded, mime, recordingStart, timer;
  let active = false, closed = false, ready = false, cameraReady = false, micReady = false, soundTested = false;
  let retries = 0, phase = 'preparing', audio = null, uploadController = null, pendingFlow = null;
  const setStatus = text => {$('#room-status').textContent = text;};
  const error = e => showError('#room-error', e);
  function setPhase(next) {phase = next;}
  function showInterviewer(persona) {
    if (!persona) return;
    $('#interviewer-name').textContent = persona.name;
    $('#interviewer-title').textContent = persona.title;
    $('#interviewer-initial').textContent = persona.name[0];
    if ($('#panel-members')) $('#panel-members').innerHTML = (state.panel || []).length > 1
      ? state.panel.map(p => `<span class="panel-member ${p.name === persona.name ? 'active' : ''}" ${p.name === persona.name ? 'aria-current="true"' : ''}>${esc(p.name)} · ${esc(p.key.toUpperCase())}</span>`).join('') : '';
  }
  function stopDevices() {
    clearInterval(timer); cancelAnimationFrame(meterFrame);
    if (recorder?.state === 'recording') {recorder.onstop = null; recorder.stop();}
    stream?.getTracks().forEach(track => track.stop());
    context?.close().catch(() => {});
  }
  function closeSession() {
    if (!active || closed) return;
    closed = true; active = false; audio?.pause(); uploadController?.abort(); stopDevices();
    localStorage.setItem(marker, 'closed');
    if (!navigator.sendBeacon(`${base}/close`, new Blob([], {type:'text/plain'}))) {
      fetch(`${base}/close`, {method:'POST', credentials:'same-origin', keepalive:true}).catch(() => {});
    }
    location.replace('/riwayat');
  }
  document.addEventListener('visibilitychange', () => {if (document.hidden) closeSession();});
  window.addEventListener('pagehide', closeSession);
  function checkReady() {
    cameraReady = !!stream?.getVideoTracks().some(t => t.readyState === 'live') && $('#camera').videoWidth > 0;
    const audioReady = !!stream?.getAudioTracks().some(t => t.readyState === 'live');
    $('#start').disabled = !(ready && cameraReady && audioReady && micReady && soundTested && $('#camera-check').checked && $('#speaker-check').checked && $('#focus-check').checked);
  }
  $('#camera-check').addEventListener('change', checkReady);
  $('#speaker-check').addEventListener('change', checkReady);
  $('#focus-check').addEventListener('change', checkReady);
  $('#camera').addEventListener('loadeddata', checkReady);
  $('#mirror').checked = sessionStorage.getItem('preptiva-mirror') === 'true';
  function mirror() {$('#camera').classList.toggle('mirror', $('#mirror').checked); sessionStorage.setItem('preptiva-mirror', $('#mirror').checked);}
  $('#mirror').addEventListener('change', mirror); mirror();
  async function fullscreen() {
    try {if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen();}
    catch {toast('Fullscreen tidak tersedia. Anda tetap dapat melanjutkan sesi.');}
  }
  $('#fullscreen').addEventListener('click', fullscreen);
  $('#devices').addEventListener('click', async () => {
    $('#devices').disabled = true; $('#room-error').hidden = true;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Browser ini memerlukan dukungan kamera dan MediaRecorder. Gunakan browser terbaru melalui localhost atau HTTPS.');
      stream?.getTracks().forEach(t => t.stop());
      stream = await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480}},audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
      $('#camera').srcObject = stream; await $('#camera').play();
      context ||= new (window.AudioContext || window.webkitAudioContext)(); await context.resume();
      analyser = context.createAnalyser(); analyser.fftSize = 256;
      context.createMediaStreamSource(new MediaStream(stream.getAudioTracks())).connect(analyser);
      const values = new Uint8Array(analyser.fftSize);
      function meter() {
        analyser.getByteTimeDomainData(values);
        const rms = Math.sqrt(values.reduce((s,v) => s + ((v-128)/128)**2, 0) / values.length);
        $('#mic-meter').value = Math.min(100,rms*400);
        if (rms > .015 && !audio && phase !== 'testing-sound') {micReady = true; $('#mic-status').textContent = '✓ Sinyal mikrofon terdeteksi';}
        checkReady(); meterFrame = requestAnimationFrame(meter);
      }
      cancelAnimationFrame(meterFrame); meter(); $('#devices').textContent = '✓ Perangkat aktif';
      stream.getTracks().forEach(t => t.addEventListener('ended', () => {checkReady(); if (active) {error('Perangkat terputus. Sesi ditutup.'); closeSession();}}));
    } catch(e) {error(e); $('#devices').disabled = false;}
  });
  $('#test-sound').addEventListener('click', async () => {
    try {
      context ||= new (window.AudioContext || window.webkitAudioContext)(); await context.resume();
      setPhase('testing-sound');
      const oscillator = context.createOscillator(), gain = context.createGain();
      oscillator.frequency.value = 523; gain.gain.value = .12;
      oscillator.connect(gain).connect(context.destination); oscillator.start(); oscillator.stop(context.currentTime + .45);
      oscillator.onended = () => {soundTested = true; setPhase('ready'); checkReady();};
    } catch(e) {error(e);}
  });
  async function play(url) {
    if (!url || closed) return;
    const player = new Audio(url); audio = player; $('#sound-bars').classList.add('playing');
    $('#replay').hidden = true;
    try {
      await new Promise((resolve,reject) => {
        player.onended = resolve; player.onerror = () => reject(new Error('Audio tidak dapat diputar. Coba putar ulang.'));
        player.play().catch(reject);
      });
    } finally {if (audio === player) audio = null; $('#sound-bars').classList.remove('playing');}
  }
  function recoverable(fn) {
    pendingFlow = fn; $('#resume-flow').hidden = false;
    $('#resume-flow').onclick = async () => {
      $('#resume-flow').hidden = true; $('#room-error').hidden = true;
      try {await pendingFlow();} catch(e) {error(e); $('#resume-flow').hidden = false;}
    };
  }
  async function presentQuestion(question) {
    if (closed) return;
    current = question; retries = 0; recorded = null;
    showInterviewer(question.persona || state.persona);
    $('#transcript').hidden = true; $('#record-controls').hidden = true; $('#answer-preview').hidden = true;
    $('#question-progress').textContent = `${question.kind === 'follow_up' ? 'PENGGALIAN LANJUTAN' : 'PERTANYAAN'} ${question.main_order} / ${state.question_count}`;
    $('#question-text').textContent = question.question_text;
    setStatus('MENDENGARKAN'); setPhase('speaking');
    const finishPresentation = async () => {
      await play(question.audio_url); if (closed) return;
      setPhase('answer-ready'); setStatus('GILIRAN ANDA');
      $('#record-controls').hidden = false; $('#record').hidden = false; $('#record').disabled = false; $('#record').textContent = '● Mulai jawab';
      $('#send').hidden = true; $('#retry').hidden = true;
      $('#answer-timer').textContent = formatTime(state.answer_seconds);
      $('#replay').hidden = false;
    };
    try {await finishPresentation();} catch(e) {error(e); recoverable(finishPresentation);}
  }
  $('#replay').addEventListener('click', async () => {
    if (phase !== 'answer-ready') return;
    $('#record').disabled = true;
    try {await play(current.audio_url);} catch(e) {error(e);}
    finally {$('#record').disabled = false; $('#replay').hidden = false;}
  });
  function formatTime(seconds) {return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
  $('#start').addEventListener('click', async () => {
    $('#start').disabled = true; $('#room-error').hidden = true;
    try {
      if ($('#fullscreen-check').checked && !document.fullscreenElement) await fullscreen();
      await postJSON(`${base}/start`); active = true; localStorage.setItem(marker, 'active');
      $('#preflight').hidden = true;
      const begin = async () => {await play(state.script.intro.audio_url); await presentQuestion(state.current_turn);};
      try {await begin();} catch(e) {error(e); recoverable(begin);}
    } catch(e) {error(e); checkReady();}
  });
  function stopRecording(timedOut = false) {
    if (recorder?.state !== 'recording') return;
    clearInterval(timer); recorder.timedOut = timedOut; recorder.stop();
    $('#record').hidden = true;
  }
  $('#record').addEventListener('click', () => {
    if (phase === 'recording') {stopRecording(); return;}
    if (phase !== 'answer-ready') return;
    try {
      mime = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(t => MediaRecorder.isTypeSupported(t));
      recorder = new MediaRecorder(new MediaStream(stream.getAudioTracks()), {...(mime ? {mimeType:mime} : {}),audioBitsPerSecond:64000});
      const parts = []; recordingStart = performance.now();
      recorder.ondataavailable = event => {if (event.data.size) parts.push(event.data);};
      recorder.onstop = () => {
        const blob = new Blob(parts, {type:recorder.mimeType});
        recorded = {blob, duration:Math.max(100,Math.round(performance.now()-recordingStart)), timedOut:!!recorder.timedOut};
        const preview = $('#answer-preview'); if (preview.src) URL.revokeObjectURL(preview.src);
        preview.src = URL.createObjectURL(blob); preview.hidden = false;
        setPhase('recorded'); setStatus('TINJAU JAWABAN'); $('#send').hidden = false;
        $('#retry').hidden = retries >= state.retry_limit;
      };
      recorder.start(500); setPhase('recording'); setStatus('MEREKAM');
      $('#record').textContent = '■ Selesai merekam'; $('#replay').hidden = true;
      timer = setInterval(() => {
        const remaining = Math.max(0,state.answer_seconds-Math.floor((performance.now()-recordingStart)/1000));
        $('#answer-timer').textContent = formatTime(remaining); if (!remaining) stopRecording(true);
      },200);
    } catch(e) {error(e);}
  });
  $('#retry').addEventListener('click', () => {
    if (retries >= state.retry_limit || phase !== 'recorded') return;
    retries++; recorded = null; setPhase('answer-ready');
    $('#record').hidden = false; $('#record').textContent = '● Mulai jawab';
    $('#send').hidden = true; $('#retry').hidden = true; $('#answer-preview').hidden = true; $('#answer-preview').pause();
    $('#answer-timer').textContent = formatTime(state.answer_seconds); $('#replay').hidden = false;
  });
  async function finish() {
    if (closed) return;
    setStatus('MENILAI'); setPhase('finishing');
    await postJSON(`${base}/finish`);
    active = false; localStorage.removeItem(marker); stopDevices();
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
    location.replace(`/sesi/${sid}/hasil`);
  }
  async function handleResult(result) {
    $('#retry-upload').hidden = true;
    $('#transcript').textContent = result.transcript; $('#transcript').hidden = false;
    const advance = async () => {
      setStatus('MENDENGARKAN'); await play(result.response_audio_url);
      if (result.is_last) {showInterviewer(result.closing.persona); await play(result.closing.audio_url); await finish();}
      else await presentQuestion(result.follow_up_question || result.next_question);
    };
    try {await advance();} catch(e) {error(e); recoverable(advance);}
  }
  async function upload() {
    if (!recorded || closed) return;
    $('#send').hidden = true; $('#retry').hidden = true; $('#retry-upload').hidden = true;
    $('#answer-preview').pause(); $('#answer-preview').hidden = true; $('#room-error').hidden = true;
    setPhase('processing'); setStatus('MEMPROSES');
    const form = new FormData();
    const extension = recorded.blob.type.includes('mp4') ? 'mp4' : recorded.blob.type.includes('ogg') ? 'ogg' : 'webm';
    form.append('question_id', current.id); form.append('audio', recorded.blob, `answer.${extension}`);
    form.append('duration_ms', recorded.duration); form.append('retry_count', retries); form.append('timed_out', recorded.timedOut);
    uploadController = new AbortController();
    try {
      const response = await fetch(`${base}/answers?stream=true`, {method:'POST', body:form, signal:uploadController.signal});
      if (!response.ok) {const err = await response.json(); throw new Error(typeof err.detail === 'string' ? err.detail : 'Jawaban tidak dapat dikirim.');}
      const reader = response.body.getReader(), decoder = new TextDecoder(); let pending = '', result = null;
      function consume(line) {
        if (!line.trim()) return;
        const event = JSON.parse(line);
        if (event.type === 'transcript') {$('#transcript').hidden = false; $('#transcript').textContent = event.transcript;}
        if (event.type === 'error') throw new Error(event.message);
        if (event.type === 'result') result = event;
      }
      while (true) {
        const {value,done} = await reader.read();
        pending += decoder.decode(value || new Uint8Array(), {stream:!done});
        const lines = pending.split('\n'); pending = lines.pop(); lines.forEach(consume);
        if (done) {consume(pending); break;}
      }
      if (!result) throw new Error('Koneksi terputus. Kirim ulang jawaban yang sama.');
      await handleResult(result);
    } catch(e) {if (!closed) {error(e); $('#retry-upload').hidden = false; setStatus('PERLU DIKIRIM ULANG');}}
  }
  $('#send').addEventListener('click', upload); $('#retry-upload').addEventListener('click', upload);
  async function poll() {
    try {
      state = await api(`${base}/state`);
      if (state.status === 'failed') {setStatus('SESI DITUTUP'); $('#preflight').hidden = true; throw new Error(state.error);}
      if (state.status === 'done' || state.status === 'scoring') {localStorage.removeItem(marker); location.replace(`/sesi/${sid}/hasil`);return;}
      if (localStorage.getItem(marker)) {
        await postJSON(`${base}/close`); localStorage.removeItem(marker);
        $('#preflight').hidden = true; setStatus('SESI DITUTUP'); throw new Error('Sesi sebelumnya telah ditinggalkan. Buat latihan baru dari menu Simulasi baru.');
      }
      if (state.status === 'running') {await postJSON(`${base}/close`); throw new Error('Sesi aktif tidak dapat dibuka ulang. Silakan buat latihan baru.');}
      $('#room-title').textContent = `Latihan ${state.job_role}`;
      $('#room-subtitle').textContent = `${state.question_count} pertanyaan · ${state.answer_seconds} detik per jawaban · ${(state.panel || []).length > 1 ? 'Panel ' + state.panel.length + ' interviewer' : state.persona.title}`;
      showInterviewer(state.persona);
      $('#interviewer-name').textContent = state.persona.name; $('#interviewer-title').textContent = state.persona.title;
      $('#interviewer-initial').textContent = state.persona.name[0];
      if (state.status === 'preparing') {setTimeout(poll,1500);return;}
      ready = true; setPhase('ready'); setStatus('SIAP DIMULAI');
      $('#question-progress').textContent = 'RUANG ANDA SUDAH SIAP';
      $('#question-text').textContent = 'Pastikan perangkat Anda siap, lalu mulai percakapan. Tidak perlu sempurna — ini ruang untuk berlatih.';
      checkReady();
    } catch(e) {error(e);}
  }
  poll();
})();
