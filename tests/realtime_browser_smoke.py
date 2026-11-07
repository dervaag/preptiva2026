"""Chrome AudioWorklet/WebSocket/VAD/Retry checks with injected providers; no paid API calls."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import socket
import threading
import time
import browser_smoke as fixture
from app.ai import realtime, speech, orchestrator
from app.config import settings
from playwright.sync_api import sync_playwright
from validation.kit import starter, packet

stats={'connections':0,'pcm_bytes':0,'streamed_responses':0}
TRANSCRIPT='Saya mengukur hasil eksperimen dan meningkatkan hasil sebesar 35 persen.'

class Upstream:
    def __init__(self): self.events=asyncio.Queue(); self.chunks=0
    async def send(self, raw):
        event=json.loads(raw)
        if event['type']=='session.update':
            await self.events.put({'type':'session.updated'})
        elif event['type']=='input_audio_buffer.commit':
            await self.events.put({'type':'error','error':{'code':'input_audio_buffer_commit_empty'}})
        elif event['type']=='input_audio_buffer.append':
            import base64
            pcm=base64.b64decode(event['audio']);assert len(pcm)%2==0
            stats['pcm_bytes']+=len(pcm);self.chunks+=1
            if self.chunks==1:
                for e in [{'type':'input_audio_buffer.speech_started'},
                    {'type':'input_audio_buffer.committed','item_id':'a'},
                    {'type':'conversation.item.input_audio_transcription.delta','item_id':'a','delta':TRANSCRIPT[:30]}]:
                    await self.events.put(e)
            if self.chunks==10:
                await self.events.put({'type':'conversation.item.input_audio_transcription.completed','item_id':'a','transcript':TRANSCRIPT})
                await self.events.put({'type':'input_audio_buffer.speech_stopped'})
    def __aiter__(self): return self
    async def __anext__(self): return json.dumps(await self.events.get())

@asynccontextmanager
async def connection(language):
    stats['connections']+=1
    yield Upstream()

async def stream_audio(text,persona):
    stats['streamed_responses']+=1
    data=fixture.wav(3 if '?' in text else .2)
    for i in range(0,len(data),4096):
        yield data[i:i+4096]
        await asyncio.sleep(.005)


def main():
    from app import storage
    storage.ROOT=Path(fixture.temporary.name)
    artifacts=Path(os.environ.get('PREPTIVA_BROWSER_ARTIFACTS',str(Path(fixture.temporary.name)/'artifacts')))
    artifacts.mkdir(parents=True,exist_ok=True)
    settings.realtime_voice_enabled=True
    settings.tts_cache=False
    speech.require_credentials=lambda persona:None
    speech.stream_audio=stream_audio;realtime.connection=connection
    orchestrator.parse_documents=fixture.parse;orchestrator.build_questions=fixture.questions
    orchestrator.respond=fixture.respond;orchestrator.adapt_question=fixture.adapt
    orchestrator.evaluate=fixture.evaluate;orchestrator.summarize=fixture.summarize
    asyncio.run(fixture.seed())
    mic=Path(fixture.temporary.name)/'mic.wav';mic.write_bytes(fixture.wav(5))
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=fixture.uvicorn.Server(fixture.uvicorn.Config(fixture.app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    if not server.started:raise RuntimeError('Realtime preview server did not start.')
    failures=[];report={'paid_api_calls':False,'ok':False}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',f'--use-file-for-fake-audio-capture={mic}'])
            context=browser.new_context(permissions=['camera','microphone'],viewport={'width':1440,'height':1100})
            page=context.new_page();page.on('pageerror',lambda error:failures.append(str(error)))
            page.add_init_script("localStorage.setItem('preptiva-ui-language', 'id')")
            page.goto(f'http://127.0.0.1:{port}/login')
            page.locator('[name=email]').fill('demo@interview.local');page.locator('[name=password]').fill('demo1234')
            page.get_by_role('button',name='Masuk',exact=True).click();page.wait_for_url('**/dashboard')
            page.goto(f'http://127.0.0.1:{port}/simulasi/baru')
            page.locator('#setup-context > summary').click()
            page.locator('[name=cv_pdf]').set_input_files(fixture.cv_pdf('Lulusan baru Akuntansi. Proyek kuliah koperasi kampus dan organisasi mahasiswa. '*4))
            page.locator('#setup-select-career_stage-trigger').click()
            page.locator('#setup-select-career_stage-menu [data-value="fresh_graduate"]').click()
            page.locator('[name=job_role]').fill('Accountant')
            page.locator('[name=industry]').fill('Finance');page.locator('[name=job_description]').fill('Prepare accurate reports and coordinate financial information with colleagues.')
            page.locator('.setup-question-choice:has(input[value="3"])').click();page.locator('[name=consent]').check()
            page.get_by_role('button',name='Siapkan wawancara').click();page.wait_for_url('**/ruang')
            sid=page.url.split('/sesi/')[1].split('/')[0]
            base=f'/api/sessions/{sid}'
            page.wait_for_function("document.querySelector('#room-status').textContent==='SIAP DIMULAI'")
            page.locator('.meeting-voice-options > summary').click()
            page.evaluate("() => {const original=RealtimeVoice.prototype.initialize;RealtimeVoice.prototype.initialize=function(){window.testVoice=this;return original.call(this)};}")
            assert page.locator('#voice-mode').is_checked()
            page.locator('#text-mode').check();page.locator('#focus-check').check()
            assert page.locator('#realtime-mode').is_checked()
            assert not page.locator('#auto-send').is_checked();assert not page.locator('#barge-in').is_checked()
            page.wait_for_function("!document.querySelector('#start').disabled");page.locator('#start').click()
            def answer_ready():page.wait_for_function("!document.querySelector('#record-controls').hidden && !document.querySelector('#record').disabled && !document.querySelector('#record').hidden")
            page.wait_for_selector('#text-answer-area')
            page.locator('#use-voice').click()
            answer_ready()
            assert page.locator('#voice-mode').is_checked() and not page.locator('#text-mode').is_checked()
            assert page.locator('#realtime-mode').is_checked()
            assert stats['connections']==0  # Switching mode does not start a recording.
            report['text_to_realtime_voice']=True
            answer_ready();page.locator('#record').click()
            page.wait_for_function("!document.querySelector('#transcript').hidden && document.querySelector('#transcript').textContent.includes('Saya mengukur')")
            # Visibility interruption cancels the capture and immediately permits a new lease on Retry.
            page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,value:false});")
            page.wait_for_function("!document.querySelector('#retry-question').disabled");page.locator('#retry-question').click()
            answer_ready();page.locator('#record').click()
            page.wait_for_function("document.querySelector('#transcript').textContent.includes('35 persen')")
            page.locator('#record').click();page.wait_for_selector('#live-review')
            page.locator('#live-transcript').fill(TRANSCRIPT+' Saya meninjau dampak bersama tim.')
            page.screenshot(path=str(artifacts/'realtime-review.png'),full_page=True)
            page.locator('#send').click()
            page.wait_for_function("document.querySelector('#question-progress').textContent.includes('2 / 3')")
            answer_ready()
            # VAD can send when opted in; leave microphone muted after speech to test next-question barge-in.
            # Enable barge-in only for the intended scenario, so a fresh fake-mic onset
            # cannot start the earlier Retry recording before its explicit click.
            page.evaluate("document.querySelector('#auto-send').checked=true;document.querySelector('#barge-in').checked=true")
            page.locator('#record').click()
            page.wait_for_function("document.querySelector('#room-status').textContent.includes('JEDA BICARA')")
            page.evaluate("document.querySelector('#camera').srcObject.getAudioTracks()[0].enabled=false")
            page.wait_for_function("document.querySelector('#question-progress').textContent.includes('3 / 3')")
            page.evaluate("document.querySelector('#camera').srcObject.getAudioTracks()[0].enabled=true")
            # Continuous fake-microphone sine is suppressed by Chrome noise suppression.
            # Inject a fresh synthetic onset into the same real AudioWorklet for the detector.
            page.evaluate("() => {const tone=testVoice.context.createOscillator(),gain=testVoice.context.createGain();gain.gain.value=.12;tone.connect(gain).connect(testVoice.node);tone.start();tone.stop(testVoice.context.currentTime+1.3);}")
            page.wait_for_function("['MENGHUBUNGKAN MIKROFON','MEREKAM REALTIME','MENDENGARKAN ANDA','JEDA BICARA · AKAN DIKIRIM'].includes(document.querySelector('#room-status').textContent)")
            print('Waiting for results',flush=True)
            page.wait_for_url('**/hasil',timeout=30000)
            print('Result page reached',flush=True)
            page.wait_for_selector('.score-number')
            result=page.evaluate('async path => (await fetch(path,{signal:AbortSignal.timeout(15000)})).json()',base+'/result')
            print('Result payload received',flush=True)
            assert len(result['items'])==3,result.keys()
            assert all(q['input_mode']=='realtime' for q in result['items'])
            assert 'Saya meninjau dampak' in result['items'][0]['transcript']
            report.update(realtime_pcm=True,live_transcript=True,correction=True,interruption_retry=True,auto_send_vad=True,barge_in=True)
            # Independent assessor UI with disposable test output, never counted as actual human assessment.
            dataset=starter(); packet_path=Path(fixture.temporary.name)/'packet.html';packet_path.write_text(packet(dataset,'browser-test'))
            page.goto(packet_path.as_uri())
            print('Packet opened',flush=True)
            for i in range(7):
                page.locator(f'[name=score-{i}]').select_option('insufficient')
                page.locator(f'[name=reason-{i}]').fill('Automated UI fixture only; not an actual human assessment.')
            page.locator('#independent').check()
            with page.expect_download() as event:page.get_by_role('button',name='Unduh hasil penilaian JSON').click()
            print('Download event received',flush=True)
            download=event.value
            downloaded=json.loads(Path(download.path()).read_text())
            assert len(downloaded['ratings'])==7 and all(r['score'] is None for r in downloaded['ratings'])
            download.delete()
            report['assessor_packet_download']=True
            assert not failures,failures
            context.close()
            browser.close();report.update(ok=True,**stats)
            print(json.dumps(report,indent=2))
    finally:
        server.should_exit=True;thread.join(timeout=10)
        (artifacts/'realtime-browser-smoke.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
