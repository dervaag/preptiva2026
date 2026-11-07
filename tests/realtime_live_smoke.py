"""Opt-in real voice transport test: synthetic audio, temporary database, no production data."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


async def check(folder):
    import httpx
    import uvicorn
    from websockets.asyncio.client import connect
    from app.main import app
    from app.db import init_db,SessionLocal,engine
    from app.models import User,InterviewSession,InterviewQuestion
    from app.security import hash_password
    from app.ai import speech,orchestrator
    from app.ai.assessment import snapshot
    from app import storage
    speech.ROOT=folder;storage.ROOT=folder
    await init_db()
    async with SessionLocal() as db:
        user=User(email='voice-synthetic@example.com',name='Synthetic Voice',password_hash=hash_password('test-only-pass123'))
        db.add(user);await db.flush()
        session=InterviewSession(user_id=user.id,candidate_name='Synthetic Voice',gender='male',age=28,job_role='Manager',level='manager',industry='Technology',
            job_description='Coordinate projects and develop team members.',cv_text='Synthetic example only.',interviewer='hr',status='running',question_count=3,answer_seconds=90,
            script={'settings':{'language':'id','panel':['hr'],'streaming_voice':True},'assessment':snapshot('hr'),
                'intro':{'text':'Selamat datang.','audio_url':None},'closing':{'text':'Terima kasih.','audio_url':None}})
        db.add(session);await db.flush()
        for i in range(1,4):db.add(InterviewQuestion(session_id=session.id,main_order=i,slot='behavior',question_text='Ceritakan pengalaman bekerja sama dengan tim.',competencies=['teamwork'],expected_points=[]))
        await db.commit();sid=session.uuid
    async def respond(context): return {'action':'next','response_text':'Terima kasih atas penjelasan Anda.'}
    orchestrator.respond=respond
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    while not server.started:await asyncio.sleep(.05)
    report={'synthetic':True,'paid_stt_tts':True,'paid_llm':False,'ok':False}
    try:
        # A synthetic answer, synthesized via the same provider; no user recordings.
        answer_audio=bytearray()
        async for data in speech.stream_audio('Saya memimpin proyek bersama tim. Kami membagi tugas dan menyelesaikan laporan tepat waktu.','hr',sid):answer_audio.extend(data)
        assert answer_audio,'Synthetic TTS failed'
        mp3=folder/'answer.mp3';mp3.write_bytes(answer_audio)
        pcm=folder/'answer.pcm'
        subprocess.run(['ffmpeg','-v','error','-i',str(mp3),'-f','s16le','-ac','1','-ar','24000',str(pcm)],check=True)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',timeout=90) as client:
            login=await client.post('/api/auth/login',json={'email':'voice-synthetic@example.com','password':'test-only-pass123'});assert login.status_code==200
            state=(await client.get(f'/api/sessions/{sid}/state')).json();qid=state['current_turn']['id']
            cookie='; '.join(f'{k}={v}' for k,v in client.cookies.items())
            async with connect(f'ws://127.0.0.1:{port}/api/sessions/{sid}/voice/{qid}',
                    additional_headers={'Cookie':cookie,'Origin':f'http://127.0.0.1:{port}'},max_size=100000) as ws:
                ready=json.loads(await asyncio.wait_for(ws.recv(),20));assert ready['type']=='ready',ready
                messages=[]
                async def reader():
                    async for raw in ws:
                        data=json.loads(raw);messages.append(data)
                        if data['type']=='error':raise RuntimeError(data['message'])
                        if data['type']=='transcript_final':return data
                task=asyncio.create_task(reader())
                audio=pcm.read_bytes()+bytes(48000*2)
                for offset in range(0,len(audio),4800):
                    await ws.send(audio[offset:offset+4800]);await asyncio.sleep(.1)
                await ws.send(json.dumps({'type':'finish'}))
                final=await asyncio.wait_for(task,35)
            assert final and len(final['transcript'])>20
            report['vad_started']=any(e['type']=='speech_started' for e in messages)
            report['vad_stopped']=any(e['type']=='speech_stopped' for e in messages)
            report['transcript_deltas']=sum(e['type']=='transcript_delta' for e in messages)
            report['transcript_chars']=len(final['transcript'])
            assert report['vad_started'] and report['vad_stopped'] and report['transcript_deltas']
            response=await client.post(f'/api/sessions/{sid}/answers',data={'question_id':qid,'duration_ms':final['duration_ms'],'capture_token':final['capture_token']})
            assert response.status_code==200,response.text
            result=response.json();assert result['input_mode']=='realtime'
            report['receipt_committed']=True
            started=time.monotonic();size=0
            async with client.stream('GET',result['response_audio_url']) as audio_response:
                assert audio_response.status_code==200
                async for chunk in audio_response.aiter_bytes():
                    if not size:report['tts_first_chunk_ms']=round((time.monotonic()-started)*1000)
                    size+=len(chunk)
            assert size>1000;report['tts_bytes']=size
            report['ok']=True
    finally:
        server.should_exit=True;await asyncio.to_thread(thread.join,10)
        await engine.dispose()
        (ROOT/'artifacts/realtime-live-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-paid',action='store_true');args=parser.parse_args()
    if not args.run_paid:parser.error('--run-paid is required')
    with tempfile.TemporaryDirectory() as directory:
        folder=Path(directory)
        os.environ.update(DATABASE_URL=f'sqlite+aiosqlite:///{folder}/voice.db',REDIS_URL='',APP_ENV='development',COOKIE_SECURE='false',
                          REALTIME_VOICE_ENABLED='true',SECRET_KEY='isolated-realtime-voice-test-secret')
        asyncio.run(check(folder))

if __name__=='__main__':main()
