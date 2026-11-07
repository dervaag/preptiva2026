'use strict';
class RealtimeVoice {
  constructor(stream, callbacks={}) {
    this.stream=stream; this.callbacks=callbacks; this.socket=null; this.buffer=[]; this.recent=[];
    this.capturing=false; this.sending=false; this.energyFrames=0; this.stopping=false;
  }
  async initialize() {
    this.context=new AudioContext({sampleRate:24000});
    await this.context.audioWorklet.addModule('/static/js/pcm-worklet.js');
    this.node=new AudioWorkletNode(this.context,'pcm24');
    this.source=this.context.createMediaStreamSource(new MediaStream(this.stream.getAudioTracks()));
    this.silent=this.context.createGain(); this.silent.gain.value=0;
    this.source.connect(this.node).connect(this.silent).connect(this.context.destination);
    this.node.port.onmessage=({data})=>{
      if(data.type==='flushed') {
        if(this.awaitingFlush && this.socket?.readyState===WebSocket.OPEN){this.awaitingFlush=false;this.socket.send(JSON.stringify({type:'finish'}));}
        return;
      }
      const values=new Int16Array(data);
      const rms=Math.sqrt(values.reduce((sum,x)=>sum+(x/32768)**2,0)/values.length);
      this.energyFrames=rms>.045?this.energyFrames+1:0;
      this.recent.push(data); if(this.recent.length>4)this.recent.shift();
      if(this.energyFrames===4)this.callbacks.onActivity?.();
      if(!this.capturing || (this.stopping && !this.awaitingFlush))return;
      if(this.sending && this.socket?.readyState===WebSocket.OPEN) {
        if(this.socket.bufferedAmount>48000*2) {this.fail(new Error('Koneksi audio terlalu lambat.'));return;}
        this.socket.send(data);
      } else {
        this.buffer.push(data);
        if(this.buffer.length>100)this.fail(new Error('Koneksi suara belum siap.'));
      }
    };
    await this.context.resume();
  }
  async start(url) {
    this.cancel(); this.capturing=true; this.stopping=false; this.buffer=[...this.recent];
    return new Promise((resolve,reject)=>{
      this.startReject=reject;
      const socket=new WebSocket(url); this.socket=socket;
      const timer=this.startTimer=setTimeout(()=>this.fail(new Error('Koneksi suara terlalu lama.')),18000);
      socket.onmessage=event=>{
        const data=JSON.parse(event.data);
        if(data.type==='ready') {
          clearTimeout(timer); this.sending=true; this.buffer.forEach(b=>socket.send(b));this.buffer=[];
          this.startReject=null; resolve();
        }
        if(data.type==='speech_started' || data.type==='speech_stopped')this.callbacks.onSpeech?.(data.type);
        if(data.type==='transcript_delta')this.callbacks.onTranscript?.(data.transcript);
        if(data.type==='transcript_final') {
          clearTimeout(timer);this.capturing=false;this.sending=false;
          this.finalResolve?.(data);this.finalResolve=null;this.finalReject=null;
        }
        if(data.type==='error') {clearTimeout(timer);this.fail(new Error(data.message));}
      };
      const lost=()=>{clearTimeout(timer);const error=new Error('Koneksi suara terputus.');error.transportLost=true;this.fail(error);};
      socket.onerror=lost;
      socket.onclose=()=>{if(this.capturing)lost();};
    });
  }
  finish() {
    this.stopping=true;this.awaitingFlush=true;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>this.fail(new Error('Transkrip belum selesai. Gunakan rekaman biasa atau teks.')),35000);
      this.finalResolve=data=>{clearTimeout(timer);resolve(data);};
      this.finalReject=e=>{clearTimeout(timer);reject(e);};
      if(this.socket?.readyState!==WebSocket.OPEN){this.fail(new Error('Koneksi suara terputus.'));return;}
      this.node.port.postMessage({type:'flush'});
    });
  }
  fail(error) {
    const rejectStart=this.startReject,rejectFinal=this.finalReject;
    this.startReject=null;this.finalReject=null;this.finalResolve=null;
    this.cancel();rejectStart?.(error);rejectFinal?.(error);this.callbacks.onError?.(error);
  }
  cancel() {
    clearTimeout(this.startTimer);
    const error=new DOMException('Rekaman dihentikan.','AbortError');
    this.startReject?.(error);this.finalReject?.(error);
    this.startReject=null;this.finalReject=null;this.finalResolve=null;
    this.capturing=false;this.sending=false;this.stopping=false;this.awaitingFlush=false;this.buffer=[];
    if(this.socket){this.socket.onclose=null;this.socket.onerror=null;this.socket.onmessage=null;this.socket.close();this.socket=null;}
  }
  destroy(){this.cancel();this.node?.disconnect();this.source?.disconnect();this.context?.close().catch(()=>{});}
}
window.RealtimeVoice=RealtimeVoice;
