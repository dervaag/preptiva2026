"""Optional Chrome UI checks. Synthetic devices and test-only provider fixtures; no AI calls."""
import asyncio
import io
import math
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
temporary = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{temporary.name}/browser.db'
os.environ['APP_ENV'] = 'development'
os.environ['REDIS_URL'] = ''
os.environ['AI_MOCK'] = 'false'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SECRET_KEY'] = 'isolated-browser-test-secret'

import uvicorn
from playwright.sync_api import sync_playwright
from app.main import app
from app.db import init_db, SessionLocal
from app.models import User
from app.security import hash_password
from app.ai import speech, orchestrator
from app.storage import audio_dir


def wav(seconds):
    output = io.BytesIO()
    with wave.open(output, 'wb') as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(16000)
        file.writeframes(b''.join(struct.pack('<h', int(9000 * math.sin(2*math.pi*440*i/16000))) for i in range(int(16000*seconds))))
    return output.getvalue()


async def seed():
    await init_db()
    async with SessionLocal() as db:
        db.add(User(email='demo@interview.local', password_hash=hash_password('demo1234'), name='Demo User', gender='male', age=28))
        await db.commit()


async def parse(*args):
    return {'cv_summary':{},'jd_summary':{}}


async def questions(context, history):
    return {'intro':'Selamat datang.', 'closing':'Terima kasih.', 'questions':[
        {'slot':slot,'category':'Latihan','question_text':text,'competencies':['communication'],'expected_points':['impact']}
        for slot, text in [('opening','Ceritakan perjalanan karier Anda?'),('behavior','Bagaimana Anda berkolaborasi dengan tim?'),('decision','Apa yang Anda pelajari dari perubahan?')]]}


async def tts(text, persona, uuid, name, live=False):
    (audio_dir(uuid) / name).write_bytes(wav(.12))
    return f'/api/sessions/{uuid}/audio/{name}'


async def transcribe(*args):
    return 'Saya mengukur hasil eksperimen dan meningkatkan hasil sebesar 35 persen.'


async def respond(context):
    return {'action':'next','response_text':'Terima kasih.'}


async def adapt(context):
    return {**context['planned_question'], 'question_text': 'Dari proyek kuliah itu, apa yang berubah setelah Anda menerima masukan?'}


async def evaluate(context):
    return {'competency_scores':{'communication':{'score':4,'evidence':['Saya mengukur hasil eksperimen']}},'feedback':{'strengths':['Terstruktur'],'improvements':['Tambah konteks'],'better_answer_tip':'Jelaskan dampak.'},'star':{'action':True,'result':True}}


async def summarize(context):
    return {'summary':'Jawaban terstruktur dengan hasil nyata.','strengths':['Terstruktur'],'improvements':['Tambah konteks'],'study_recommendations':[]}


def main():
    speech.require_credentials = lambda persona: None
    speech.synthesize = tts; speech.transcribe = transcribe
    orchestrator.parse_documents = parse; orchestrator.build_questions = questions
    orchestrator.respond = respond; orchestrator.evaluate = evaluate; orchestrator.summarize = summarize
    orchestrator.adapt_question = adapt
    asyncio.run(seed())
    mic_file = Path(temporary.name) / 'mic.wav'; mic_file.write_bytes(wav(5))
    sock = socket.socket(); sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]; sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1',port=port,log_level='warning'))
    thread = threading.Thread(target=server.run,daemon=True); thread.start()
    for _ in range(100):
        if server.started: break
        time.sleep(.05)
    if not server.started: raise RuntimeError('Preview server did not start.')
    failures = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream', f'--use-file-for-fake-audio-capture={mic_file}'])
            context = browser.new_context(permissions=['camera','microphone'], viewport={'width':1440,'height':1100})
            page = context.new_page(); page.on('pageerror',lambda error: failures.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/login')
            page.locator('[name=email]').fill('demo@interview.local'); page.locator('[name=password]').fill('demo1234')
            page.get_by_role('button',name='Masuk ke workspace').click(); page.wait_for_url('**/dashboard')
            page.wait_for_function("document.querySelector('#stat-total').textContent === '0'")
            artifacts = ROOT / 'artifacts'; artifacts.mkdir(exist_ok=True)
            page.screenshot(path=str(artifacts/'dashboard-desktop.png'),full_page=True)
            for width in (390,768,1440):
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Dashboard overflows at {width}'
            page.set_viewport_size({'width':1440,'height':1100})
            for scenario, panel_size in enumerate((1, 2, 3), 1):
                page.set_viewport_size({'width':1440,'height':1100})
                page.goto(f'http://127.0.0.1:{port}/simulasi/baru')
                page.locator('[name=cv_text]').fill('Lulusan baru Akuntansi. Proyek kuliah koperasi kampus, organisasi mahasiswa, dan magang administrasi. ' * 4)
                page.locator('[name=career_stage]').select_option('fresh_graduate')
                page.locator('[name=job_role]').fill('Accountant'); page.locator('[name=industry]').fill('Finance')
                page.locator('[name=job_description]').fill('Prepare accurate reports and coordinate financial information with colleagues.')
                page.locator('[name=question_count]').select_option('3'); page.locator('[name=consent]').check()
                if panel_size > 1:
                    page.locator('#interview-mode').select_option('panel')
                    assert page.locator('#panel-personas').is_visible()
                    assert not page.locator('#single-personas').is_visible()
                    if panel_size == 3: page.locator('[name=panel][value=manager]').check()
                    page.set_viewport_size({'width':390,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Panel form overflow'
                    page.screenshot(path=str(artifacts/f'panel-{panel_size}-form.png'),full_page=True)
                    page.set_viewport_size({'width':1440,'height':1100})
                page.get_by_role('button',name='Siapkan wawancara').click(); page.wait_for_url('**/ruang')
                page.wait_for_function("document.querySelector('#room-status').textContent === 'SIAP DIMULAI'")
                page.locator('#devices').click(); page.locator('#test-sound').click()
                page.locator('#camera-check').check(); page.locator('#speaker-check').check(); page.locator('#focus-check').check()
                page.wait_for_function("!document.querySelector('#start').disabled",timeout=15000)
                page.locator('#start').click()
                names = ['Rina'] if panel_size == 1 else ['Rina', 'Andi'] if panel_size == 2 else ['Rina', 'Andi', 'Hendra']
                for turn in range(3):
                    page.wait_for_function("!document.querySelector('#record').hidden && !document.querySelector('#record-controls').hidden")
                    assert page.locator('#interviewer-name').inner_text() == names[turn % len(names)]
                    if turn:
                        assert 'proyek kuliah' in page.locator('#question-text').inner_text()
                    if panel_size > 1:
                        assert page.locator('.panel-member.active').count() == 1
                        if turn == 1: page.screenshot(path=str(artifacts/f'panel-{panel_size}-room.png'),full_page=True)
                    page.locator('#record').click(); page.wait_for_timeout(600); page.locator('#record').click()
                    page.locator('#send').click()
                page.wait_for_url('**/hasil',timeout=30000)
                page.wait_for_selector('.score-number'); assert page.locator('.score-number').inner_text().strip().startswith('80')
                if panel_size > 1: assert page.locator('.panel-results article').count() == panel_size
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Results overflow on mobile'
                page.screenshot(path=str(artifacts/f'panel-{panel_size}-results.png'),full_page=True)
                page.goto(f'http://127.0.0.1:{port}/dashboard')
                page.wait_for_function("document.querySelector('#stat-total').textContent === String(" + str(scenario) + ")")
            assert not failures, failures
            browser.close()
            print('Chrome checks passed: single, 2-person and 3-person panels; fresh graduate setup, active speaker, adaptive turns, streaming, per-persona results and mobile layout. No AI calls.')
    finally:
        server.should_exit = True; thread.join(timeout=10)


if __name__ == '__main__':
    main()
