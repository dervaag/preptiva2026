const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const sourcePath = process.argv[2];
const source = fs.readFileSync(sourcePath, 'utf8');
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };

function fixture(options = {}) {
  let now = 0, nextTimer = 1;
  const timers = new Map(), calls = [], plays = [], navigations = [], captures = [], nodes = new Map();
  class Element extends EventTarget {
    constructor(id = '') {
      super(); this.id = id; this.hidden = false; this.disabled = false; this.checked = false;
      this.dataset = {}; this.style = {}; this.children = []; this.attributes = new Map(); this.textContent = ''; this.value = '';
      this.videoWidth = 640; this.videoHeight = 480; this.readyState = 4; this.paused = true; this.ended = false;
      this.scrollTop = 0; this.scrollHeight = 500; this.clientHeight = 500; this.open = false; this.src = '';
      const classes = new Set();
      this.classList = {add: (...items) => items.forEach(item => classes.add(item)), remove: (...items) => items.forEach(item => classes.delete(item)),
        toggle: (item, enabled = !classes.has(item)) => enabled ? (classes.add(item), true) : (classes.delete(item), false), contains: item => classes.has(item)};
    }
    set className(value) {this._className = value;}
    get className() {return this._className || '';}
    setAttribute(name, value) {this.attributes.set(name, String(value));}
    getAttribute(name) {return this.attributes.get(name) ?? null;}
    removeAttribute(name) {this.attributes.delete(name);}
    append(...children) {this.children.push(...children);}
    appendChild(child) {this.children.push(child); return child;}
    remove() {this.hidden = true;}
    showModal() {this.open = true; this.hidden = false;}
    close() {this.open = false; this.dispatchEvent(new Event('close'));}
    focus() {}
    scrollTo({top}) {this.scrollTop = top;}
    load() {}
    pause() {this.paused = true; this.dispatchEvent(new Event('pause'));}
    async play() {
      this.paused = false; this.ended = false;
      if (this.id.includes('camera')) {this.dispatchEvent(new Event('loadeddata')); return;}
      plays.push(this.src);
      this.dispatchEvent(new Event('play')); this.dispatchEvent(new Event('playing'));
      if (options.failAudio?.(this.src, plays)) throw new Error('audio unavailable');
      if (!options.holdAudio?.(this.src)) queueMicrotask(() => {this.paused = true; this.ended = true; this.dispatchEvent(new Event('ended')); this.onended?.();});
    }
    click() {if (!this.disabled) this.dispatchEvent(new Event('click'));}
  }
  const ids = ['meeting-room','room-stage','interviewer-avatar','interviewer-name','interviewer-title','room-title','room-subtitle','room-status','chat-progress','elapsed-time',
    'stage-caption','camera','preflight-camera','camera-off-placeholder','candidate-mic-status','interviewer-audio','preflight','open-preflight','close-preflight','devices','camera-check',
    'test-sound','speaker-check','mic-meter','mic-status','focus-check','fullscreen-check','start','connection-status','connection-retry','preflight-error','room-error','room-countdown',
    'countdown-number','chat-log','chat-empty','chat-new-messages','chat-panel','record-controls','answer-timer','record','send','retry','replay','answer-preview','retry-upload','resume-flow',
    'question-progress','question-text','transcript','camera-toggle','mic-toggle','mirror-toggle','captions-toggle','chat-toggle','avatar-motion-toggle','fullscreen','leave-room','leave-dialog',
    'cancel-leave','confirm-leave','mirror','sound-bars','interviewer-initial','device-status','device-requirement','preflight-description','preflight-title','verification-status','preflight-body','chat-activity','chat-activity-label',
    'panel-members','participant-count','voice-mode','text-mode','use-text','use-voice','answer-mode-status','text-answer-area','text-answer','send-text','stop-audio','interruption','interruption-status','retry-question','skip-question',
    'realtime-mode','auto-send','barge-in','live-review','live-transcript'];
  ids.forEach(id => nodes.set(id, new Element(id)));
  ['preflight','room-countdown','record-controls','send','retry','retry-upload','resume-flow','answer-preview','stage-caption','preflight-error','room-error'].forEach(id => nodes.get(id).hidden = true);
  nodes.get('start').disabled = true; nodes.get('speaker-check').disabled = true;
  nodes.get('voice-mode').checked = true;
  nodes.get('realtime-mode').checked = true; nodes.get('live-review').hidden = true;
  const document = new EventTarget(); document.body = {dataset:{sid:'fixture-session'}};
  document.hidden = false; document.visibilityState = 'visible'; document.fullscreenEnabled = false;
  document.querySelector = selector => nodes.get(selector.slice(1)); document.getElementById = id => nodes.get(id);
  document.createElement = () => new Element(); document.documentElement = new Element();
  document.exitFullscreen = async () => {document.fullscreenElement = null;};
  const window = new EventTarget();
  const setTimeoutFake = (fn, delay = 0) => {const id = nextTimer++; timers.set(id, {fn, due:now + delay}); return id;};
  const setIntervalFake = (fn, delay) => {const id = nextTimer++; timers.set(id, {fn, due:now + delay, delay}); return id;};
  async function advance(ms) {
    const until = now + ms;
    for (;;) {
      let candidate;
      for (const [id, timer] of timers) if (timer.due <= until && (!candidate || timer.due < candidate[1].due)) candidate = [id, timer];
      if (!candidate) break;
      const [id, timer] = candidate; now = timer.due;
      if (timer.delay) timer.due += timer.delay; else timers.delete(id);
      timer.fn(now); await flush();
    }
    now = until; await flush();
  }
  class Track extends EventTarget {constructor(kind) {super(); this.kind = kind; this.enabled = true; this.readyState = 'live';} stop() {this.readyState = 'ended';}}
  const tracks = [new Track('video'), new Track('audio')];
  class MediaStreamFake {constructor(items = tracks) {this.tracks = items;} getTracks() {return this.tracks;} getAudioTracks() {return this.tracks.filter(t => t.kind === 'audio');} getVideoTracks() {return this.tracks.filter(t => t.kind === 'video');}}
  class AudioContextFake {
    constructor() {this.state = 'running'; this.currentTime = 0; this.destination = {};}
    resume() {this.state = 'running'; return options.resume ? options.resume() : Promise.resolve();}
    close() {this.state = 'closed'; return Promise.resolve();}
    createAnalyser() {return {fftSize:256, connect(){}, disconnect(){}, getByteTimeDomainData(values) {values.fill(148);}};}
    createMediaStreamSource() {return {connect(){}, disconnect(){}};}
    createMediaElementSource() {return {connect(){}, disconnect(){}};}
    createGain() {return {gain:{value:0}, connect(){return this;}, disconnect(){}};}
    createOscillator() {return {frequency:{value:0}, connect(){return this;}, disconnect(){}, start(){}, stop(){setTimeoutFake(() => this.onended?.(),450);}};}
  }
  class MediaRecorderFake extends EventTarget {
    static isTypeSupported() {return true;}
    constructor() {super(); this.state = 'inactive'; this.mimeType = 'audio/webm;codecs=opus';}
    start() {this.state = 'recording'; captures.push(this);}
    stop() {this.state = 'inactive'; this.ondataavailable?.({data:new Blob(['audio'],{type:this.mimeType})}); queueMicrotask(() => this.onstop?.());}
  }
  const voices = [];
  class RealtimeVoiceFake {
    constructor(stream, callbacks) {this.callbacks = callbacks; this.cancelled = 0; this.destroyed = false; voices.push(this);}
    async initialize() {}
    start(url) {this.url = url; return options.realtimeStart?.(this) || Promise.resolve();}
    finish() {return options.realtimeFinish?.(this) || Promise.resolve({capture_token:'capture-1',transcript:'Transkrip realtime.',duration_ms:1200});}
    cancel() {this.cancelled++;}
    destroy() {this.destroyed = true; this.cancel();}
  }
  const state = {session_id:'fixture-session',status:'ready',interviewer:'hr',persona:{name:'Rina',title:'HR Interviewer'},job_role:'Engineer',level:'junior',question_count:3,answer_seconds:60,retry_limit:2,max_followups:2,
    script:{intro:{text:'Selamat datang.',audio_url:'/intro.mp3'},closing:{text:'Selesai.',audio_url:'/closing.mp3'},fillers:[],settings:{language:'id'}},
    questions:[],answered_mains:0,current_turn:{id:1,kind:'main',main_order:1,slot:'opening',category:'opening',question_text:'Ceritakan pengalaman Anda.',audio_url:'/question.mp3'}};
  Object.assign(state, options.state);
  const result = {type:'result',answer_id:11,transcript:'Pengalaman saya.',action:'follow_up',response_text:'Apa kontribusi Anda?',response_audio_url:'/follow.mp3',follow_up_question:{id:2,kind:'follow_up',main_order:1,slot:'opening',category:'opening',question_text:'Apa kontribusi Anda?',audio_url:'/follow.mp3'},next_question:null,is_last:false,closing:null,...options.result};
  let uploads = 0;
  async function fetchFake(url, init = {}) {
    calls.push([url, init]);
    if (url.endsWith('/state')) return options.fetchState ? options.fetchState(init.signal, state) : new Response(JSON.stringify(state));
    if (url === '/health') return new Response(JSON.stringify(options.health || {ok:true,db:true,redis:true}));
    if (url.endsWith('/interrupt')) {
      const payload=JSON.parse(init.body);state.status='running';
      if(result.follow_up_question?.id===payload.question_id)state.current_turn=result.follow_up_question;
      if(result.next_question?.id===payload.question_id)state.current_turn=result.next_question;
      state.checkpoint={phase:'interrupted',question_id:payload.question_id,interruption_id:'interrupt-1',remaining_seconds:0};
      return new Response(JSON.stringify({already_completed:false,state}));
    }
    if (url.endsWith('/recover')) {
      const payload=JSON.parse(init.body);state.checkpoint={phase:'question_ready',question_id:payload.question_id,remaining_seconds:state.answer_seconds};
      if(options.recoveryResponse)return options.recoveryResponse(payload,state);
      return new Response(JSON.stringify(payload.action==='retry'?state:{...result,skipped:true,transcript:'',response_audio_url:null}));
    }
    if (url.includes('/answers')) {
      uploads++;
      if (options.answerResponse) return options.answerResponse(uploads, result, init.signal);
      const events = options.answerEvents ? options.answerEvents(uploads, result) : [{type:'transcript',transcript:'Pengalaman saya.'},result];
      return new Response(events.map(event => JSON.stringify(event)).join('\n')+'\n', {headers:{'Content-Type':'application/x-ndjson'}});
    }
    return new Response(JSON.stringify({status:url.endsWith('/start')?'running':'ok'}));
  }
  const local = new Map(Object.entries(options.storage || {})), session = new Map();
  const storage = map => ({getItem:key=>map.get(key)??null,setItem:(key,value)=>map.set(key,String(value)),removeItem:key=>map.delete(key)});
  const location = {protocol:'http:',host:'fixture.local',replace:url=>navigations.push(url),assign:url=>navigations.push(url)};
  const navigator = {userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',platform:'Win32',maxTouchPoints:0,...options.device,mediaDevices:{getUserMedia:constraints => {
    const acquired = new MediaStreamFake(tracks.filter(track => constraints.video !== false || track.kind !== 'video'));
    return options.getUserMedia ? options.getUserMedia(acquired, constraints) : Promise.resolve(acquired);
  }},sendBeacon:(url,body)=>{calls.push([url,{method:'BEACON',body}]); return true;}};
  const context = {console,document,window,navigator,location,localStorage:storage(local),sessionStorage:storage(session),performance:{now:()=>now},
    setTimeout:setTimeoutFake,clearTimeout:id=>timers.delete(id),setInterval:setIntervalFake,clearInterval:id=>timers.delete(id),
    requestAnimationFrame:fn=>setTimeoutFake(fn,16),cancelAnimationFrame:id=>timers.delete(id),
    MediaStream:MediaStreamFake,MediaRecorder:MediaRecorderFake,AudioContext:AudioContextFake,Audio:class extends Element {constructor(url){super();this.src=url;}},
    matchMedia:()=>({matches:!!options.reducedMotion,addEventListener(){}}),fetch:fetchFake,AbortController,DOMException,Blob,FormData,Response,TextDecoder,Uint8Array,URL:Object.assign(URL,{createObjectURL:()=>`blob:fixture-${now}`,revokeObjectURL(){}}),
    $:selector=>document.querySelector(selector),api:async url=>(await fetchFake(url)).json(),postJSON:async url=>(await fetchFake(url,{method:'POST'})).json(),
    showError:(selector,error)=>{const node=document.querySelector(selector);node.textContent=error.message||error;node.hidden=false;},toast(){}};
  Object.assign(window,{AudioContext:AudioContextFake,MediaRecorder:MediaRecorderFake,RealtimeVoice:RealtimeVoiceFake,matchMedia:context.matchMedia});
  vm.runInNewContext(source, context, {filename:sourcePath});
  return {nodes,calls,plays,document,window,tracks,navigations,voices,captures,advance,flush,local,get uploads(){return uploads;}};
}

async function verify(f) {
  f.nodes.get('devices').click(); await flush(); await f.advance(32);
  f.nodes.get('test-sound').click(); await flush(); await f.advance(500);
  for (const id of ['camera-check','speaker-check','focus-check']) {f.nodes.get(id).checked = true;f.nodes.get(id).dispatchEvent(new Event('change'));}
  await flush(); assert.equal(f.nodes.get('start').disabled, false, 'verified devices must enable start');
}
async function start(f) {await verify(f);f.nodes.get('start').click();await flush();await f.advance(3100);}
async function answer(f) {f.nodes.get('record').click();await f.advance(1000);f.nodes.get('record').click();await flush();f.nodes.get('send').click();await flush();}
async function startText(f) {
  await flush();
  f.nodes.get('text-mode').checked = true; f.nodes.get('text-mode').dispatchEvent(new Event('change'));
  f.nodes.get('focus-check').checked = true; f.nodes.get('focus-check').dispatchEvent(new Event('change'));
  f.nodes.get('start').click(); await flush(); await f.advance(3100);
}

(async () => {
  const ready = fixture(); await flush();
  assert.equal(ready.nodes.get('preflight').open,true,`ready state must open native preflight automatically: ${ready.nodes.get('room-error').textContent}`);
  assert.equal(ready.calls.some(([url]) => url.endsWith('/start')),false,'ready state must never auto-start');
  ready.document.hidden=true;ready.document.dispatchEvent(new Event('visibilitychange'));await flush();
  assert.equal(ready.calls.some(([url]) => url.endsWith('/close')),false,'hidden ready session must remain ready');
  console.log('PASS ready state opens preflight without starting or closing');

  for (const device of [
    {userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)',platform:'iPhone'},
    {userAgent:'Mozilla/5.0 (Linux; Android 15; Tablet)',platform:'Linux armv8l'},
    {userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)',platform:'MacIntel',maxTouchPoints:5},
    {userAgent:'Desktop mode',userAgentData:{mobile:true}},
  ]) {
    let requested = 0;
    const mobile = fixture({device,getUserMedia:stream => {requested++;return Promise.resolve(stream);}}); await flush();
    assert.equal(mobile.nodes.get('devices').disabled, true, 'mobile devices must not request camera or microphone');
    assert.equal(mobile.nodes.get('start').disabled, true, 'mobile devices cannot start a session');
    assert.equal(mobile.nodes.get('device-requirement').hidden, false);
    mobile.nodes.get('text-mode').checked=true;mobile.nodes.get('text-mode').dispatchEvent(new Event('change'));
    assert.equal(mobile.nodes.get('start').disabled,true,'text mode must preserve the mandatory desktop gate');
    mobile.nodes.get('devices').click();mobile.nodes.get('start').click();await flush();
    assert.equal(requested, 0);
    assert.equal(mobile.calls.some(([url]) => url.endsWith('/start')), false);
  }
  const touchLaptop = fixture({device:{maxTouchPoints:10}}); await flush();await verify(touchLaptop);
  console.log('PASS phones and tablets are blocked while touch Windows laptops remain supported');

  const late = fixture({getUserMedia:stream=>new Promise(resolve=>{late.resolveMedia=()=>resolve(stream);})});await flush();
  late.nodes.get('devices').click();await flush();late.window.dispatchEvent(new Event('pagehide'));late.resolveMedia();await flush();
  assert(late.tracks.every(track=>track.readyState==='ended'),'late permission result must stop all tracks');
  assert.equal(late.nodes.get('camera').srcObject,null,'late stream must not attach to video');
  console.log('PASS late permissions cannot resurrect devices');

  const running = fixture();await flush();await verify(running);
  running.nodes.get('start').click();running.nodes.get('start').click();await flush();
  assert.equal(running.calls.filter(([url])=>url.endsWith('/start')).length,1,'double click must send one start');
  assert.equal(running.nodes.get('countdown-number').textContent,'3');assert.equal(running.plays.length,0,'intro must wait for countdown');
  await running.advance(3100);assert.equal(running.nodes.get('record-controls').hidden,false);
  await answer(running);
  assert.equal(running.plays.filter(url=>url==='/follow.mp3').length,1,'follow-up response and question share one playback');
  const bodies=running.nodes.get('chat-log').children.flatMap(child=>child.children.filter(item=>item.className==='chat-message-body').map(item=>item.textContent));
  assert.equal(bodies.filter(text=>text==='Apa kontribusi Anda?').length,1,'follow-up must have one chat bubble');
  assert.equal(bodies.filter(text=>text==='Pengalaman saya.').length,1,'transcript and final result must have one candidate bubble');
  running.document.hidden=true;running.document.dispatchEvent(new Event('visibilitychange'));await flush();
  assert.equal(running.calls.filter(([url])=>url.endsWith('/interrupt')).length,1,'active hidden session must save one interruption');
  assert.equal(running.calls.filter(([url])=>url.endsWith('/close')).length,0,'tab hiding must not end the session');
  assert.equal(running.nodes.get('interruption').hidden,false);
  running.document.hidden=false;running.nodes.get('retry-question').click();await flush();
  assert.equal(running.calls.filter(([url])=>url.endsWith('/recover')).length,1);
  assert.equal(running.nodes.get('answer-timer').textContent,'01:00');
  console.log('PASS countdown, single start, follow-up deduplication, and interruption retry');

  const interrupted = fixture({answerEvents:(attempt,result)=>attempt===1?[{type:'transcript',transcript:'Pengalaman saya.'},{type:'error',message:'Pemrosesan gagal.'}]:[{type:'transcript',transcript:'Pengalaman saya.'},result]});
  await flush();await start(interrupted);await answer(interrupted);
  assert.equal(interrupted.nodes.get('retry-upload').hidden,false,'stream error must expose resubmission');
  interrupted.nodes.get('retry-upload').click();await flush();
  const candidate=interrupted.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--candidate');
  assert.equal(candidate.length,1,'resubmitting same question must update one transcript');
  assert.equal(interrupted.uploads,2);
  console.log('PASS NDJSON error preserves idempotent resubmission');

  let activityStream, activityResult;
  const activity=fixture({answerResponse:(attempt,result)=>{
    activityResult=result;
    return new Response(new ReadableStream({start(controller){activityStream=controller;}}));
  }});
  const emitActivity = event => activityStream.enqueue(new TextEncoder().encode(JSON.stringify(event)+'\n'));
  await flush();await start(activity);
  assert.equal(activity.nodes.get('chat-activity').hidden,true,'chat activity must stay hidden before a submission');
  const opening=activity.nodes.get('chat-log').children;
  assert.equal(opening[0].dataset.continuation,'false','first interviewer message starts a group');
  assert.equal(opening[1].dataset.continuation,'true','consecutive interviewer messages continue the group');
  assert.equal(opening[1].children[0].textContent,'Rina','grouped messages retain their accessible author');
  await answer(activity);
  assert.equal(activity.nodes.get('chat-activity').hidden,false,'actual pending upload shows activity');
  assert.equal(activity.nodes.get('chat-activity-label').textContent,'Memproses jawaban…');
  const pendingCandidate=activity.nodes.get('chat-log').children.find(child=>child.className==='chat-message chat-message--candidate');
  assert(pendingCandidate,'a real audio submission immediately adds its candidate bubble');
  assert.equal(pendingCandidate.children[1].textContent,'Jawaban suara');
  assert.equal(pendingCandidate.children[2].textContent,'Memproses transkrip…');
  emitActivity({type:'transcript',transcript:'Pengalaman saya.'});await flush();
  assert.equal(activity.nodes.get('chat-activity-label').textContent,'Rina merespons…','received transcript advances real response activity');
  const streamedCandidate=activity.nodes.get('chat-log').children.find(child=>child.className==='chat-message chat-message--candidate');
  assert.equal(streamedCandidate,pendingCandidate,'transcript updates the voice bubble without replaying its entry');
  assert.equal(streamedCandidate.children[1].textContent,'Pengalaman saya.');
  assert.equal(streamedCandidate.children[2].hidden,true,'actual response activity avoids repeated transcript status copy');
  assert.equal(streamedCandidate.dataset.continuation,'false','a candidate reply starts a new role group');
  emitActivity({type:'transcript',transcript:'Pengalaman saya.'});await flush();
  assert.equal(activity.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--candidate').length,1,'stream updates reuse one candidate element');
  assert.equal(activity.nodes.get('chat-log').children.includes(streamedCandidate),true,'stream updates retain the original message node');
  emitActivity(activityResult);await flush();
  assert.equal(activity.nodes.get('chat-activity').hidden,true,'result arrival clears activity before stream EOF');
  activityStream.close();await flush();
  assert.equal(activity.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--candidate').length,1,'final result reuses the transcript node');
  assert.equal(streamedCandidate.dataset.continuation,'false','result updates do not reapply grouping or entry state');
  console.log('PASS real chat activity and grouped transcript updates remain idempotent');

  let retryStream, retryResult;
  const retryActivity=fixture({answerResponse:(attempt,result)=>{
    retryResult=result;
    return new Response(new ReadableStream({start(controller){retryStream=controller;}}));
  }});
  await flush();await start(retryActivity);await answer(retryActivity);
  retryStream.enqueue(new TextEncoder().encode(JSON.stringify({type:'transcript',transcript:'Jawaban tetap tersimpan.'})+'\n'));await flush();
  retryStream.enqueue(new TextEncoder().encode(JSON.stringify({type:'error',message:'Pemrosesan gagal.'})+'\n'));await flush();
  assert.equal(retryActivity.nodes.get('chat-activity').hidden,true,'stream errors clear activity');
  const retryCandidate=retryActivity.nodes.get('chat-log').children.find(child=>child.className==='chat-message chat-message--candidate');
  assert.match(retryCandidate.children[2].textContent,/belum terkonfirmasi/i,'failed processing must not claim successful delivery');
  retryActivity.nodes.get('retry-upload').click();await flush();
  assert.equal(retryActivity.nodes.get('chat-activity').hidden,false,'resubmission shows only its current processing state');
  assert.equal(retryActivity.nodes.get('chat-activity-label').textContent,'Memproses jawaban…','retry clears the previous response stage');
  assert.equal(retryCandidate.children[1].textContent,'Jawaban tetap tersimpan.','retry preserves the real transcript instead of replacing it with voice placeholder text');
  assert.equal(retryActivity.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--candidate').length,1,'retry preserves the same candidate bubble');
  retryActivity.document.hidden=true;retryActivity.document.dispatchEvent(new Event('visibilitychange'));await flush();
  assert.equal(retryActivity.nodes.get('chat-activity').hidden,true,'closing an active session clears pending activity');
  retryStream.enqueue(new TextEncoder().encode(JSON.stringify(retryResult)+'\n'));await flush();
  assert.equal(retryActivity.nodes.get('chat-activity').hidden,true,'late stream data cannot resurrect activity');
  console.log('PASS chat activity clears on error, retry, close, and late stream completion');

  const muted=fixture();await flush();await start(muted);muted.nodes.get('record').click();await muted.advance(1000);muted.nodes.get('mic-toggle').click();await flush();
  assert.equal(muted.nodes.get('answer-preview').hidden,false,'muting during recording must allow review');
  assert.equal(muted.uploads,0,'muting never submits audio');
  muted.nodes.get('retry').click();await flush();assert.equal(muted.nodes.get('record').disabled,true,'muted microphone must block recording');
  muted.nodes.get('mic-toggle').click();assert.equal(muted.nodes.get('record').disabled,false);
  console.log('PASS microphone mute stops recording and blocks new capture');

  const recovery=fixture({result:{action:'next',response_text:'Terima kasih.',response_audio_url:'/ack.mp3',follow_up_question:null,next_question:{id:3,kind:'main',main_order:2,question_text:'Bagaimana Anda bekerja?',audio_url:'/next.mp3'}},
    failAudio:(url,plays)=>url==='/next.mp3'&&plays.filter(item=>item===url).length===1});
  await flush();await start(recovery);await answer(recovery);
  assert.equal(recovery.nodes.get('record-controls').hidden,false,'optional audio failure must keep the question answerable');
  recovery.nodes.get('replay').click();await flush();
  assert.equal(recovery.plays.filter(url=>url==='/ack.mp3').length,1,'recovery must not replay completed acknowledgement');
  assert.equal(recovery.plays.filter(url=>url==='/next.mp3').length,2);
  assert.equal(recovery.nodes.get('record-controls').hidden,false);
  console.log('PASS optional audio failure retains answer controls without repeating acknowledgements');

  const duringCountdown=fixture();await flush();await verify(duringCountdown);duringCountdown.nodes.get('start').click();await flush();
  duringCountdown.document.hidden=true;duringCountdown.document.dispatchEvent(new Event('visibilitychange'));await duringCountdown.advance(4000);
  assert.equal(duringCountdown.plays.length,0,'hidden countdown must never start intro audio');
  assert.equal(duringCountdown.calls.filter(([url])=>url.endsWith('/interrupt')).length,1);
  assert.equal(duringCountdown.calls.filter(([url])=>url.endsWith('/close')).length,0);
  console.log('PASS hidden countdown pauses before intro without ending the session');

  const final=fixture({result:{action:'next',response_text:'Terima kasih.',response_audio_url:'/ack.mp3',follow_up_question:null,is_last:true,closing:{text:'Sampai jumpa.',audio_url:'/closing.mp3'}}});
  await flush();await start(final);await answer(final);
  assert.equal(final.calls.filter(([url])=>url.endsWith('/finish')).length,1);
  assert.equal(final.nodes.get('chat-activity').hidden,true,'finishing clears transient response activity');
  assert.equal(final.local.has('preptiva-active-fixture-session'),false);
  assert(final.tracks.every(track=>track.readyState==='ended'));
  assert.deepEqual(final.navigations,['/sesi/fixture-session/hasil']);
  console.log('PASS finish releases resources and redirects to results');

  const cached=fixture();await flush();cached.nodes.get('devices').click();await flush();cached.nodes.get('test-sound').click();await flush();
  cached.window.dispatchEvent(new Event('pagehide'));await flush();
  const restored=new Event('pageshow');Object.defineProperty(restored,'persisted',{value:true});cached.window.dispatchEvent(restored);await flush();
  assert.equal(cached.nodes.get('test-sound').disabled,false,'back-cache restoration must allow a fresh sound test');
  assert.equal(cached.nodes.get('devices').disabled,false,'back-cache restoration must allow device retry');
  console.log('PASS ready back-cache restoration can verify devices again');

  let initialStateRequests = 0;
  const loading = fixture({fetchState:(signal, state) => {
    initialStateRequests++;
    if (initialStateRequests > 1) return new Response(JSON.stringify(state));
    return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Navigated away', 'AbortError')), {once:true}));
  }});
  await flush();
  loading.window.dispatchEvent(new Event('pagehide')); await flush();
  const loadingRestored = new Event('pageshow'); Object.defineProperty(loadingRestored, 'persisted', {value:true});
  loading.window.dispatchEvent(loadingRestored); await flush();
  assert.equal(initialStateRequests, 2, 'back-cache restore must restart an aborted initial state request');
  assert.equal(loading.nodes.get('preflight').open, true, 'restored initial load must reach verification');
  console.log('PASS interrupted initial load resumes after back-cache restoration');

  let resumeCalls=0, releaseResume;
  const changed=fixture({resume:()=>++resumeCalls===3?new Promise(resolve=>{releaseResume=resolve;}):Promise.resolve()});
  await flush();await verify(changed);changed.nodes.get('start').click();await flush();
  changed.tracks.find(track=>track.kind==='audio').enabled=false;releaseResume();await flush();
  assert.equal(changed.calls.some(([url])=>url.endsWith('/start')),false,'device changes while preparing start must revalidate before POST');
  console.log('PASS start revalidates devices after gesture awaits');

  const typed=fixture();await flush();
  typed.nodes.get('text-mode').checked=true;typed.nodes.get('text-mode').dispatchEvent(new Event('change'));
  typed.nodes.get('focus-check').checked=true;typed.nodes.get('focus-check').dispatchEvent(new Event('change'));
  assert.equal(typed.nodes.get('start').disabled,false,'desktop text mode can start without requesting physical devices');
  typed.nodes.get('start').click();await flush();await typed.advance(3100);
  assert.equal(typed.nodes.get('camera').srcObject,undefined);
  assert.equal(typed.nodes.get('text-answer-area').hidden,false);
  typed.nodes.get('text-answer').value='Saya mengukur dampak pekerjaan.';typed.nodes.get('text-answer').dispatchEvent(new Event('input'));
  typed.nodes.get('send-text').click();await flush();
  const form=typed.calls.find(([url])=>url.includes('/answers'))[1].body;
  assert.equal(form.get('text_answer'),'Saya mengukur dampak pekerjaan.');assert.equal(form.has('audio'),false);assert.equal(form.get('duration_ms'),'100');
  assert.equal(typed.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--candidate').length,1);
  console.log('PASS desktop-only text startup and multipart text answers preserve chat idempotency');

  let permissionRequests = 0, denyMicrophone = true;
  const modes = fixture({getUserMedia:(stream,constraints) => {
    permissionRequests++; assert.equal(constraints.video,false,'text-to-voice only requests a microphone');
    return denyMicrophone ? Promise.reject(new DOMException('Denied','NotAllowedError')) : Promise.resolve(stream);
  }});
  await flush(); assert.equal(modes.nodes.get('voice-mode').checked,true,'voice is the default');
  await startText(modes); assert.equal(permissionRequests,0,'text startup never requests microphone access');
  modes.nodes.get('text-answer').value='Draf jawaban tetap ada.';
  modes.nodes.get('text-answer').dispatchEvent(new Event('input'));
  modes.nodes.get('use-voice').click(); await flush();
  assert.equal(modes.nodes.get('text-answer-area').hidden,false);
  assert.equal(modes.nodes.get('text-mode').checked,true);
  assert.equal(modes.nodes.get('use-voice').disabled,false,'denied access can be retried');
  assert.match(modes.nodes.get('room-error').textContent,/Izin mikrofon/);
  assert.equal(modes.nodes.get('text-answer').value,'Draf jawaban tetap ada.');
  denyMicrophone=false; modes.nodes.get('use-voice').click(); await flush();
  assert.equal(modes.nodes.get('voice-mode').checked,true);
  assert.equal(modes.nodes.get('text-mode').checked,false);
  assert.equal(modes.nodes.get('record-controls').hidden,false);
  assert.equal(modes.captures.length,0,'changing modes never starts a recorder');
  assert.equal(modes.nodes.get('answer-mode-status').textContent,'Mode jawaban: Rekam suara');
  modes.nodes.get('record').click(); await modes.advance(1000); modes.nodes.get('record').click(); await flush();
  const preview = modes.nodes.get('answer-preview').src;
  modes.nodes.get('use-text').click(); await flush();
  assert.equal(modes.nodes.get('text-answer').value,'Draf jawaban tetap ada.');
  modes.nodes.get('use-voice').click(); await flush();
  assert.equal(permissionRequests,2,'existing live microphone is reused');
  assert.equal(modes.nodes.get('answer-preview').src,preview,'recorded audio survives mode changes');
  assert.equal(modes.nodes.get('answer-preview').hidden,false);
  assert.equal(modes.nodes.get('send').hidden,false);
  modes.nodes.get('send').click(); await flush();
  assert.equal(modes.calls.find(([url])=>url.includes('/answers'))[1].body.has('audio'),true);
  assert.equal(modes.nodes.get('text-answer').value,'','draft is cleared for the next question');
  console.log('PASS text-to-voice permission retry, explicit capture, retained drafts and audio, and fresh next question');

  let releaseMicrophone, delayedTracks;
  const delayedMode = fixture({getUserMedia:stream => {
    delayedTracks=stream.getTracks(); return new Promise(resolve=>{releaseMicrophone=()=>resolve(stream);});
  }});
  await startText(delayedMode);
  delayedMode.nodes.get('use-voice').click(); await flush();
  delayedMode.document.hidden=true; delayedMode.document.dispatchEvent(new Event('visibilitychange')); await flush();
  releaseMicrophone(); await flush();
  assert(delayedTracks.every(track=>track.readyState==='ended'),'permission granted after interruption stops all acquired tracks');
  assert.equal(delayedMode.nodes.get('interruption').hidden,false);
  assert.equal(delayedMode.nodes.get('record-controls').hidden,true);
  assert.equal(delayedMode.nodes.get('room-status').textContent,'PERTANYAAN DIJEDA');
  assert.equal(delayedMode.nodes.get('text-mode').checked,true,'late permission cannot change the selected mode');
  assert.equal(delayedMode.captures.length,0);
  delayedMode.document.hidden=false; delayedMode.nodes.get('retry-question').click(); await flush();
  assert.equal(delayedMode.nodes.get('use-voice').disabled,false,'Retry re-enables the voice action');
  assert.equal(delayedMode.nodes.get('text-answer-area').hidden,false);
  console.log('PASS interrupted text-to-voice permission stays discarded and Retry remains usable');

  const failedAudioMode = fixture({answerEvents:()=>[{type:'error',message:'Pemrosesan gagal.'}]});
  await flush(); await start(failedAudioMode); await answer(failedAudioMode);
  assert.equal(failedAudioMode.nodes.get('use-text').hidden,false,'audio upload error still offers text');
  failedAudioMode.nodes.get('use-text').click(); await flush();
  assert.equal(failedAudioMode.nodes.get('text-answer-area').hidden,false);
  failedAudioMode.nodes.get('use-voice').click(); await flush();
  assert.equal(failedAudioMode.nodes.get('send').hidden,false,'failed audio remains available after switching back');
  console.log('PASS upload errors allow switching modes without discarding the recording');

  const panel=fixture({state:{panel:[{key:'hr',name:'Rina',title:'HR Interviewer'},{key:'user',name:'Andi',title:'Technical Lead'},{key:'manager',name:'Hendra',title:'Hiring Manager'}]},
    result:{action:'next',response_interviewer:'hr',response_text:'Terima kasih.',follow_up_question:null,next_question:{id:3,kind:'main',main_order:2,interviewer:'user',persona:{name:'Andi',title:'Technical Lead'},question_text:'Bagaimana Anda menguji hasil kerja?',audio_url:null}}});
  await flush();await start(panel);await answer(panel);
  assert.equal(panel.nodes.get('interviewer-name').textContent,'Andi');assert.match(panel.nodes.get('interviewer-avatar').style.backgroundImage,/andi-sprite/);
  assert.equal(panel.nodes.get('participant-count').textContent,'4 peserta');
  const aiMessages=panel.nodes.get('chat-log').children.filter(child=>child.className==='chat-message chat-message--ai');
  assert.equal(aiMessages.at(-1).children[0].textContent,'Andi');assert.equal(aiMessages.at(-2).children[0].textContent,'Rina');
  assert.equal(aiMessages.at(-1).dataset.continuation,'false','a panel handoff keeps the new author visible');
  console.log('PASS panel sprite, actual response author, handoff grouping, and participant count');

  const resuming=fixture({state:{status:'running'}});await flush();
  assert.equal(resuming.calls.some(([url])=>url.endsWith('/close')),false,'opening a running session must not close it');
  resuming.nodes.get('text-mode').checked=true;resuming.nodes.get('text-mode').dispatchEvent(new Event('change'));
  resuming.nodes.get('focus-check').checked=true;resuming.nodes.get('focus-check').dispatchEvent(new Event('change'));
  resuming.nodes.get('start').click();await flush();
  assert.equal(resuming.nodes.get('interruption').hidden,false);assert.equal(resuming.plays.length,0,'reload requires an explicit recovery choice');
  resuming.nodes.get('skip-question').click();await flush();
  assert.equal(resuming.calls.find(([url])=>url.endsWith('/recover'))[1].body.includes('"action":"next"'),true);
  assert(resuming.nodes.get('chat-log').children.some(child=>child.className==='chat-message chat-message--system'));
  console.log('PASS running-session reopen and explicit Next recovery do not close or invent answers');

  const silent=fixture({holdAudio:url=>url==='/intro.mp3'});await flush();await verify(silent);silent.nodes.get('start').click();await flush();await silent.advance(3100);
  assert.equal(silent.nodes.get('stop-audio').hidden,false);silent.nodes.get('stop-audio').click();await flush();
  assert.equal(silent.nodes.get('record-controls').hidden,false,'stopping interviewer audio must keep the conversation usable');
  const evaluation=fixture({state:{status:'evaluation_failed'}});await flush();
  assert.deepEqual(evaluation.navigations,['/sesi/fixture-session/hasil']);
  console.log('PASS stop-audio continuation and evaluation-failed results navigation');

  let releaseRecovery,recoveryCalls=0;
  const racing=fixture({recoveryResponse:(payload,state)=>{
    recoveryCalls++;
    if(recoveryCalls===1)return new Promise(resolve=>{releaseRecovery=()=>resolve(new Response(JSON.stringify(state)));});
    return new Response(JSON.stringify(state));
  }});
  await flush();await start(racing);
  racing.document.hidden=true;racing.document.dispatchEvent(new Event('visibilitychange'));await flush();
  racing.document.hidden=false;racing.nodes.get('retry-question').click();await flush();
  racing.document.hidden=true;racing.document.dispatchEvent(new Event('visibilitychange'));await flush();
  releaseRecovery();await flush();racing.document.hidden=false;racing.nodes.get('retry-question').click();await flush();
  assert.equal(recoveryCalls,2,'an older recovery response must not leave the newer interrupted turn permanently busy');
  console.log('PASS interruption during pending recovery can recover again');

  const realtimeState = {script:{intro:{text:'Selamat datang.',audio_url:'/intro.mp3'},closing:{text:'Selesai.',audio_url:'/closing.mp3'},settings:{language:'id',streaming_voice:true}}};
  const live = fixture({state:realtimeState}); await flush(); await start(live);
  assert.equal(live.nodes.get('realtime-mode').checked,true);
  assert.equal(live.nodes.get('auto-send').checked,false); assert.equal(live.nodes.get('barge-in').checked,false);
  live.nodes.get('record').click(); await flush();
  live.voices[0].callbacks.onTranscript('Transkrip bertahap.');
  assert.equal(live.nodes.get('transcript').textContent,'Transkrip bertahap.');
  assert.equal(live.nodes.get('chat-log').children.at(-1).children[0].textContent,'Anda');
  live.nodes.get('record').click(); await flush();
  assert.equal(live.nodes.get('live-review').hidden,false);
  live.nodes.get('live-transcript').value='Transkrip realtime yang saya koreksi.';
  live.nodes.get('send').click(); await flush();
  const captureForm = live.calls.find(([url])=>url.includes('/answers'))[1].body;
  assert.equal(captureForm.get('capture_token'),'capture-1'); assert.equal(captureForm.has('audio'),false);
  assert.equal(captureForm.get('corrected_transcript'),'Transkrip realtime yang saya koreksi.');
  assert.equal(captureForm.get('duration_ms'),'1200'); assert.equal(captureForm.get('timed_out'),'false');
  assert.equal(live.calls.filter(([url])=>url.endsWith('/voice-latency')).length,1);
  live.nodes.get('replay').click(); await flush();
  assert.equal(live.calls.filter(([url])=>url.endsWith('/voice-latency')).length,1,'replay must not duplicate first-playing latency');
  console.log('PASS realtime partial chat, manual review, corrected receipt upload, and once-per-answer latency');

  const liveModes = fixture({state:realtimeState}); await startText(liveModes);
  liveModes.nodes.get('use-voice').click(); await flush();
  assert.equal(liveModes.voices.length,1,'switching from text initializes realtime microphone support');
  assert.equal(liveModes.voices[0].url,undefined,'realtime connection waits for an explicit record click');
  liveModes.nodes.get('record').click(); await flush(); liveModes.nodes.get('record').click(); await flush();
  liveModes.nodes.get('live-transcript').value='Koreksi saya disimpan.';
  liveModes.nodes.get('use-text').click(); await flush();
  liveModes.nodes.get('text-answer').value='Alternatif draf teks.';
  liveModes.nodes.get('use-voice').click(); await flush();
  assert.equal(liveModes.nodes.get('live-review').hidden,false);
  assert.equal(liveModes.nodes.get('live-transcript').value,'Koreksi saya disimpan.');
  assert.equal(liveModes.nodes.get('text-answer').value,'Alternatif draf teks.');
  liveModes.nodes.get('send').click(); await flush();
  const switchedCapture = liveModes.calls.find(([url])=>url.includes('/answers'))[1].body;
  assert.equal(switchedCapture.get('capture_token'),'capture-1');
  assert.equal(switchedCapture.get('corrected_transcript'),'Koreksi saya disimpan.');
  console.log('PASS text-to-realtime requires explicit capture and retains corrected transcripts across mode switches');

  let completeLate;
  const interruptedLive = fixture({state:realtimeState,realtimeFinish:()=>new Promise(resolve=>{completeLate=resolve;})});
  await flush(); await start(interruptedLive); interruptedLive.nodes.get('record').click(); await flush();
  interruptedLive.voices[0].callbacks.onTranscript('Belum terkirim.');
  interruptedLive.nodes.get('record').click(); await flush();
  interruptedLive.document.hidden=true; interruptedLive.document.dispatchEvent(new Event('visibilitychange')); await flush();
  completeLate({capture_token:'stale',transcript:'Tidak boleh kembali.',duration_ms:1000}); await flush();
  assert.equal(interruptedLive.nodes.get('live-review').hidden,true); assert.equal(interruptedLive.nodes.get('record-controls').hidden,true);
  assert.equal(interruptedLive.nodes.get('transcript').textContent,''); assert.equal(interruptedLive.uploads,0);
  assert(interruptedLive.voices[0].cancelled>0);
  interruptedLive.document.hidden=false; interruptedLive.nodes.get('retry-question').click(); await flush();
  interruptedLive.nodes.get('record').click(); await flush();
  assert.equal(interruptedLive.nodes.get('room-status').textContent,'MENDENGARKAN ANDA');
  console.log('PASS interrupted realtime completion stays discarded and Retry starts a fresh capture');

  const vad = fixture({state:realtimeState}); await flush(); await start(vad);
  vad.nodes.get('record').click(); await flush(); vad.voices[0].callbacks.onSpeech('speech_stopped'); await vad.advance(2000);
  assert.equal(vad.uploads,0,'VAD must not send without explicit opt-in');
  vad.nodes.get('auto-send').checked=true; vad.voices[0].callbacks.onSpeech('speech_stopped'); await vad.advance(1000);
  vad.voices[0].callbacks.onSpeech('speech_started'); await vad.advance(1500);
  assert.equal(vad.uploads,0,'resumed speech cancels the pending auto-send');
  vad.voices[0].callbacks.onSpeech('speech_stopped'); await vad.advance(1800);
  assert.equal(vad.uploads,1); assert.equal(vad.nodes.get('live-review').hidden,true);
  console.log('PASS VAD remains opt-in and resumed speech cancels auto-send');

  const broken = fixture({state:realtimeState}); await flush(); await start(broken);
  broken.nodes.get('record').click(); await flush(); broken.voices[0].callbacks.onError(new Error('Provider indisponibel.')); await flush();
  assert.equal(broken.nodes.get('realtime-mode').checked,false); assert.equal(broken.nodes.get('record').disabled,false);
  assert.equal(broken.nodes.get('use-text').hidden,false); await answer(broken);
  assert(broken.calls.find(([url])=>url.includes('/answers'))[1].body.has('audio'));
  console.log('PASS realtime provider failure restores recorder and text fallbacks');

  const barge = fixture({state:realtimeState,holdAudio:url=>url==='/question.mp3'}); await flush(); await start(barge);
  barge.voices[0].callbacks.onActivity(); await flush(); assert.equal(barge.voices[0].url,undefined,'barge-in must be opt-in');
  barge.nodes.get('barge-in').checked=true; barge.voices[0].callbacks.onActivity(); await flush();
  assert.match(barge.voices[0].url,/\/voice\/1$/); assert.equal(barge.nodes.get('room-status').textContent,'MENDENGARKAN ANDA');
  barge.window.dispatchEvent(new Event('pagehide')); await flush(); assert.equal(barge.voices[0].destroyed,true);
  console.log('PASS explicit barge-in hands a question to capture and pagehide destroys realtime audio');

  const textBarge = fixture({state:realtimeState,holdAudio:url=>url==='/question.mp3'}); await flush(); await verify(textBarge);
  textBarge.nodes.get('barge-in').checked=true;
  await startText(textBarge);
  textBarge.voices[0].callbacks.onActivity(); await flush();
  assert.equal(textBarge.voices[0].url,undefined,'barge-in ignores microphone activity when text mode is selected');
  assert.equal(textBarge.nodes.get('room-status').textContent,'MENDENGARKAN');
  textBarge.nodes.get('stop-audio').click(); await flush();
  assert.equal(textBarge.nodes.get('text-answer-area').hidden,false);
  assert.equal(textBarge.voices[0].url,undefined);
  console.log('PASS text mode never starts barge-in capture even with live microphone and opt-in');
})().catch(error=>{console.error(error);process.exitCode=1;});
