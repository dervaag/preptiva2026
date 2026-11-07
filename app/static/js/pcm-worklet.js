/* PCM16, mono, 24 kHz. No audio leaves the worklet unless the page starts capture. */
class PCM24Processor extends AudioWorkletProcessor {
  constructor() {
    super(); this.phase=0; this.sum=0; this.count=0; this.block=[];
    this.port.onmessage=()=>{
      if(this.block.length){const pcm=new Int16Array(this.block);this.block=[];this.port.postMessage(pcm.buffer,[pcm.buffer]);}
      this.port.postMessage({type:'flushed'});
    };
  }
  process(inputs) {
    const input=inputs[0]?.[0]; if (!input) return true;
    for (const sample of input) {
      this.sum+=sample; this.count++; this.phase+=24000;
      if (this.phase>=sampleRate) {
        const value=Math.max(-1,Math.min(1,this.sum/this.count));
        this.block.push(Math.round(value*(value<0?32768:32767)));
        this.phase-=sampleRate; this.sum=0; this.count=0;
      }
      if (this.block.length===2400) {
        const pcm=new Int16Array(this.block); this.block=[];
        this.port.postMessage(pcm.buffer,[pcm.buffer]);
      }
    }
    return true;
  }
}
registerProcessor('pcm24',PCM24Processor);
