'use strict';
(() => {
  const sid = document.body.dataset.sid;
  const base = `/api/sessions/${sid}`;
  const marker = `preptiva-active-${sid}`;
  let state, current, stream, context, analyser, meterFrame, recorder, recorded, mime, recordingStart, timer;
  let active = false, closed = false, ready = false, cameraReady = false, micReady = false, soundTested = false;
  let retries = 0, phase = 'preparing', audio = null, uploadController = null, pendingFlow = null;
  let stopAudio = null, interruptionPending = false, recoveryState = null;
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
    closed = true; active = false; stopAudio?.(); uploadController?.abort(); stopDevices();
    localStorage.setItem(marker, 'closed');
    if (!navigator.sendBeacon(`${base}/close`, new Blob([], {type:'text/plain'}))) {
      fetch(`${base}/close`, {method:'POST', credentials:'same-origin', keepalive:true}).catch(() => {});
    }
    location.replace('/riwayat');
  }
  function stopQuestion() {
    setPhase('interrupted'); clearInterval(timer); stopAudio?.(); uploadController?.abort();
    if (recorder?.state === 'recording') {recorder.onstop = null; recorder.stop();}
    recorded = null; $('#answer-preview').pause(); $('#answer-preview').hidden = true;
    $('#record-controls').hidden = true; $('#text-answer-area').hidden = true; $('#use-text').hidden = true;
    $('#send').hidden = true; $('#retry-upload').hidden = true; $('#replay').hidden = true; $('#resume-flow').hidden = true;
    $('#answer-timer').textContent = '00:00'; $('#interruption').hidden = false;
    $('#retry-question').disabled = true; $('#skip-question').disabled = true;
    setStatus('PERTANYAAN TERHENTI');
  }
  async function interruptQuestion(reason = 'reload') {
    if (!active || closed || !current || phase === 'finishing') return;
    stopQuestion(); interruptionPending = true;
    localStorage.setItem(marker, JSON.stringify({question_id:current.id, interrupted:true}));
    $('#interruption-status').textContent = 'Menyimpan status; sambungkan kembali internet untuk melanjutkan.';
    try {
      const result = await postJSON(`${base}/interrupt`, {question_id:current.id, reason});
      state = result.state; interruptionPending = false;
      if (result.already_completed) {
        $('#interruption').hidden = true;
        recoverable(async () => {current = state.current_turn; if (current) await presentQuestion(current); else await finish();});
        $('#interruption-status').textContent = '';
        $('#question-text').textContent = 'Jawaban sebelumnya sudah tersimpan. Klik Lanjutkan untuk pertanyaan berikutnya.';
        return;
      }
      recoveryState = state.checkpoint;
      $('#interruption-status').textContent = 'Pertanyaan dihentikan. Pilih langkah berikutnya.';
      $('#retry-question').disabled = false; $('#skip-question').disabled = false;
    } catch(e) {error(e);}
  }
  document.addEventListener('visibilitychange', () => {if (document.hidden) interruptQuestion('tab_hidden');});
  window.addEventListener('offline', () => interruptQuestion('offline'));
  window.addEventListener('online', () => {if (interruptionPending) interruptQuestion('offline');});
  window.addEventListener('pagehide', () => {
    if (!active || !current || closed) return;
    stopQuestion();
    localStorage.setItem(marker, JSON.stringify({question_id:current.id, interrupted:true}));
    navigator.sendBeacon(`${base}/interrupt`, new Blob([JSON.stringify({question_id:current.id, reason:'reload'})], {type:'application/json'}));
  });
  $('#end-session').addEventListener('click', closeSession);
  async function recoverQuestion(action) {
    if (!recoveryState?.interruption_id) return;
    $('#retry-question').disabled = true; $('#skip-question').disabled = true;
    try {
      const result = await postJSON(`${base}/recover`, {question_id:recoveryState.question_id,
        interruption_id:recoveryState.interruption_id, action});
      $('#interruption').hidden = true; $('#room-error').hidden = true;
      setPhase('recovering');
      if (action === 'retry') {state = result; await presentQuestion(state.current_turn);}
      else await handleResult(result);
    } catch(e) {error(e); $('#retry-question').disabled = false; $('#skip-question').disabled = false;}
  }
  $('#retry-question').addEventListener('click', () => recoverQuestion('retry'));
  $('#skip-question').addEventListener('click', () => recoverQuestion('next'));
  function checkReady() {
    cameraReady = !!stream?.getVideoTracks().some(t => t.readyState === 'live') && $('#camera').videoWidth > 0;
    const audioReady = !!stream?.getAudioTracks().some(t => t.readyState === 'live');
    $('#start').disabled = !(ready && $('#focus-check').checked && ($('#text-mode').checked ||
      (cameraReady && audioReady && micReady && soundTested && $('#camera-check').checked && $('#speaker-check').checked)));
  }
  $('#text-mode').addEventListener('change', checkReady);
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
      stream.getTracks().forEach(t => t.addEventListener('ended', () => {checkReady(); if (active) interruptQuestion('device_lost');}));
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
    $('#stop-audio').hidden = false;
    $('#replay').hidden = true;
    try {
      await new Promise((resolve,reject) => {
        stopAudio = () => {player.pause(); resolve();};
        player.onended = resolve; player.onerror = () => reject(new Error('Audio tidak dapat diputar. Coba putar ulang.'));
        player.play().catch(reject);
      });
    } finally {if (audio === player) audio = null; stopAudio = null; $('#stop-audio').hidden = true; $('#sound-bars').classList.remove('playing');}
  }
  $('#stop-audio').addEventListener('click', () => stopAudio?.());
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
    localStorage.setItem(marker, JSON.stringify({question_id:current.id}));
    $('#text-answer').value = ''; $('#text-answer-area').hidden = true; $('#interruption').hidden = true;
    $('#interviewer-response').hidden = true;
    showInterviewer(question.persona || state.persona);
    $('#transcript').hidden = true; $('#record-controls').hidden = true; $('#answer-preview').hidden = true;
    $('#question-progress').textContent = `${question.kind === 'follow_up' ? 'PENGGALIAN LANJUTAN' : 'PERTANYAAN'} ${question.main_order} / ${state.question_count}`;
    $('#question-text').textContent = question.question_text;
    setStatus('MENDENGARKAN'); setPhase('speaking');
    const finishPresentation = async () => {
      try {await play(question.audio_url);} catch(e) {error('Suara tidak tersedia. Anda dapat membaca pertanyaan dan melanjutkan.');}
      if (closed || phase === 'interrupted') return;
      setPhase('answer-ready'); setStatus('GILIRAN ANDA');
      $('#record-controls').hidden = false; $('#record').hidden = false; $('#record').disabled = false; $('#record').textContent = '● Mulai jawab';
      $('#send').hidden = true; $('#retry').hidden = true;
      $('#answer-timer').textContent = formatTime(state.answer_seconds);
      $('#replay').hidden = false;
      $('#use-text').hidden = false;
      if ($('#text-mode').checked) useText();
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
      const resuming = state.status === 'running';
      await postJSON(`${base}/start`); active = true;
      $('#preflight').hidden = true;
      current = state.current_turn;
      if (!current) {await finish(); return;}
      if (resuming) {
        let saved; try {saved = JSON.parse(localStorage.getItem(marker));} catch {}
        if (saved?.question_id) current = {...current, id:saved.question_id};
        await interruptQuestion('reload'); return;
      }
      localStorage.setItem(marker, JSON.stringify({question_id:current.id}));
      const begin = async () => {
        try {await play(state.script.intro.audio_url);} catch {error('Suara tidak tersedia. Pertanyaan tetap dapat dibaca.');}
        if (phase !== 'interrupted') await presentQuestion(state.current_turn);
      };
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
      $('#interviewer-response').textContent = result.response_text; $('#interviewer-response').hidden = false;
      setStatus('MENDENGARKAN'); try {await play(result.response_audio_url);} catch {error('Suara tidak tersedia; tanggapan ditampilkan sebagai teks.');}
      if (phase === 'interrupted' || closed) return;
      if (result.is_last) {showInterviewer(result.closing.persona); try {await play(result.closing.audio_url);} catch {} if (phase !== 'interrupted') await finish();}
      else await presentQuestion(result.follow_up_question || result.next_question);
    };
    try {await advance();} catch(e) {error(e); recoverable(advance);}
  }
  async function upload(textAnswer = null) {
    if ((!recorded && textAnswer === null) || closed || phase === 'interrupted') return;
    $('#send').hidden = true; $('#retry').hidden = true; $('#retry-upload').hidden = true;
    $('#answer-preview').pause(); $('#answer-preview').hidden = true; $('#room-error').hidden = true;
    setPhase('processing'); setStatus('MEMPROSES');
    const form = new FormData();
    form.append('question_id', current.id);
    if (textAnswer !== null) {form.append('text_answer', textAnswer); form.append('duration_ms', 100);}
    else {
      const extension = recorded.blob.type.includes('mp4') ? 'mp4' : recorded.blob.type.includes('ogg') ? 'ogg' : 'webm';
      form.append('audio', recorded.blob, `answer.${extension}`); form.append('duration_ms', recorded.duration);
      form.append('timed_out', recorded.timedOut);
    }
    form.append('retry_count', retries); $('#text-answer-area').hidden = true; $('#use-text').hidden = true;
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
      if (!result) {await interruptQuestion('offline'); return;}
      await handleResult(result);
    } catch(e) {if (!closed && phase !== 'interrupted') {
      if (e instanceof TypeError) {await interruptQuestion('offline'); return;}
      error(e); $('#retry-upload').hidden = textAnswer !== null; $('#use-text').hidden = false;
      if (textAnswer !== null) $('#text-answer-area').hidden = false;
      setStatus('PERLU DIKIRIM ULANG');
    }}
  }
  function useText() {
    if (phase === 'recording' || phase === 'interrupted') return;
    $('#record-controls').hidden = true; $('#text-answer-area').hidden = false; $('#use-text').hidden = true;
    setPhase('answer-ready'); $('#text-answer').focus();
  }
  $('#use-text').addEventListener('click', useText);
  $('#send-text').addEventListener('click', () => {const text = $('#text-answer').value.trim(); if (text) upload(text);});
  $('#send').addEventListener('click', () => upload()); $('#retry-upload').addEventListener('click', () => upload());
  async function poll() {
    try {
      state = await api(`${base}/state`);
      if (state.status === 'failed') {setStatus('SESI DITUTUP'); $('#preflight').hidden = true; throw new Error(state.error);}
      if (['done', 'scoring', 'evaluation_failed'].includes(state.status)) {localStorage.removeItem(marker); location.replace(`/sesi/${sid}/hasil`);return;}
      $('#room-title').textContent = `Latihan ${state.job_role}`;
      $('#room-subtitle').textContent = `${state.question_count} pertanyaan · ${state.answer_seconds} detik per jawaban · ${(state.panel || []).length > 1 ? 'Panel ' + state.panel.length + ' interviewer' : state.persona.title}`;
      showInterviewer(state.persona);
      $('#interviewer-name').textContent = state.persona.name; $('#interviewer-title').textContent = state.persona.title;
      $('#interviewer-initial').textContent = state.persona.name[0];
      if (state.status === 'preparing') {setTimeout(poll,1500);return;}
      ready = true; setPhase('ready'); setStatus('SIAP DIMULAI');
      if (state.status === 'running') $('#start').textContent = 'Buka sesi tersimpan ↗';
      $('#question-progress').textContent = 'RUANG ANDA SUDAH SIAP';
      $('#question-text').textContent = 'Pastikan perangkat Anda siap, lalu mulai percakapan. Tidak perlu sempurna — ini ruang untuk berlatih.';
      checkReady();
    } catch(e) {error(e);}
  }
  poll();
})();
