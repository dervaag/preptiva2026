import os
import tempfile
from pathlib import Path

_temporary = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///' + str(Path(_temporary.name) / 'test.db')
os.environ['APP_ENV'] = 'development'
os.environ['AI_MOCK'] = 'false'
os.environ['REDIS_URL'] = ''
os.environ['MAX_SESSIONS_PER_HOUR'] = '5'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['SECRET_KEY'] = 'isolated-test-secret-key'
os.environ.update({'ANSWER_SECONDS_JUNIOR':'90', 'ANSWER_SECONDS_MIDDLE':'120',
    'ANSWER_SECONDS_SENIOR':'120', 'ANSWER_SECONDS_MANAGER':'150', 'RETRY_LIMIT':'2',
    'MAX_FOLLOWUPS_ENABLED':'true', 'FOLLOWUPS_DEMO':'1', 'FOLLOWUPS_SHORT':'2', 'FOLLOWUPS_STANDARD':'3',
    'RESPOND_TIMEOUT_SEC':'60', 'TTS_PROVIDER':'elevenlabs', 'STT_PROVIDER':'openai', 'STT_FALLBACK_PROVIDER':''})

import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock
import httpx
from sqlalchemy import select
from app.main import app
from app.db import init_db, engine, SessionLocal
from app.models import Base, InterviewSession, InterviewQuestion, InterviewAnswer
from app.ai.assessment import snapshot
from app.ai.scoring import verified_scores, aggregate, WEIGHTS
from app.ai.blueprint import validate_questions
from app.ai import orchestrator
from app.worker.tasks import prepare_session, finalize_session
from app.services.text import clean_text, chunks, validate_text
from fastapi import HTTPException
from pydantic import ValidationError
from app.config import Settings, settings
from app.ai.errors import check_response, ProviderError


class TextAndScoringTests(unittest.TestCase):
    def test_config_rejects_invalid_limits_and_unsupported_providers(self):
        for values in ({'answer_seconds_junior':0}, {'followups_demo':4}, {'retry_limit':-1},
                       {'respond_timeout_sec':0}, {'stt_provider':'deepgram'}, {'tts_provider':'openai'},
                       {'elevenlabs_output_format':'pcm_44100'}, {'stt_fallback_provider':'deepgram'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Settings(_env_file=None, **values)

    def test_config_reads_all_levels_and_lengths(self):
        config = Settings(_env_file=None, answer_seconds_junior=30, answer_seconds_middle=45,
            answer_seconds_senior=60, answer_seconds_manager=75, followups_demo=0, followups_short=3, followups_standard=5)
        self.assertEqual([config.answer_seconds_for(level) for level in ('junior','middle','senior','manager')], [30,45,60,75])
        self.assertEqual([config.followups_for(n) for n in (3,5,7)], [0,3,5])
        config.max_followups_enabled = False
        self.assertEqual([config.followups_for(n) for n in (3,5,7)], [0,0,0])

    def test_provider_error_does_not_expose_remote_details(self):
        response = httpx.Response(429, json={'error':{'code':'insufficient_quota','message':'SECRET-IN-REMOTE-BODY'}},
                                  request=httpx.Request('POST','https://example.com'))
        with self.assertRaises(ProviderError) as caught:
            check_response(response,'OpenAI')
        self.assertIn('kuota',str(caught.exception))
        self.assertNotIn('SECRET',str(caught.exception))

    def test_clean_preserves_identity_and_numbers(self):
        original = 'Budi\u200b Santoso\r\nC++ / C#\t  +62 812 123\nNaik 35%\n\n\n2024–2026'
        cleaned = clean_text(original)
        self.assertIn('C++ / C# +62 812 123', cleaned)
        self.assertIn('35%', cleaned)
        self.assertEqual(cleaned, clean_text(cleaned))

    def test_chunks_keep_end_and_limits(self):
        text = 'Experience 2025.\n' * 4000 + 'END_UNIQUE_FACT'
        parts = chunks(text, 6000)
        self.assertTrue(all(len(part) <= 6000 for part in parts))
        self.assertTrue(parts[-1].endswith('END_UNIQUE_FACT'))
        self.assertEqual(''.join(text.split()), ''.join(''.join(parts).split()))
        with self.assertRaises(HTTPException) as error:
            validate_text('x' * 60001, 'CV')
        self.assertEqual(error.exception.status_code, 413)

    def test_scores_require_verbatim_evidence(self):
        result = verified_scores({'technical': {'score':5,'evidence':['made up evidence']},
            'communication':{'score':4,'evidence':['Saya mengukur hasil eksperimen']}},
            'Saya mengukur hasil eksperimen sebelum memutuskan.', ['technical','communication'])
        self.assertEqual(result['technical']['score'], 2)
        self.assertEqual(result['communication']['score'], 4)
        total, competencies = aggregate([{'communication':result['communication']}], WEIGHTS['hr'])
        self.assertEqual(total, 4)
        self.assertIsNone(next(c['score'] for c in competencies if c['key'] == 'leadership'))

    def test_rubric_snapshot_is_traceable(self):
        data = snapshot('hr')
        self.assertEqual(len(data['sha256']), 64)
        self.assertFalse(data['validated'])
        self.assertEqual(data['weights']['technical'], 0)

    def test_hr_rejects_technical_questions(self):
        with self.assertRaises(ValueError):
            validate_questions([{'question_text':'Bagaimana optimasi query SQL?', 'slot':'opening'}], [{'slot':'opening'}], 'hr', [])


class SystemTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await init_db()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver')
        self.other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver')
        response = await self.register(self.client, 'budi@example.com')
        self.assertEqual(response.status_code, 200, response.text)

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.other.aclose()
        await engine.dispose()

    async def register(self, client, email):
        return await client.post('/api/auth/register', json={'name':'Budi Santoso','email':email,
            'password':'test12345','password_confirm':'test12345','gender':'male','age':28,'agree':True})

    def form(self):
        return {'candidate_name':'Budi Santoso','gender':'male','age':'28','job_role':'Product Designer','level':'middle',
            'industry':'Technology','company':'Acme','job_description':'Design accessible user experiences with research and product experiments.',
            'question_count':'3','interviewer':'hr','language':'id','consent':'true','cv_text':'Pengalaman merancang produk dan melakukan riset bersama pengguna. ' * 8}

    async def create(self, **changes):
        data = {**self.form(), **changes}
        with patch('app.api.sessions.speech.require_credentials'), patch('app.api.sessions.enqueue', new_callable=AsyncMock):
            response = await self.client.post('/api/sessions', data=data)
        return response

    async def ready_session(self):
        created = await self.create()
        self.assertEqual(created.status_code, 200, created.text)
        sid = created.json()['session_id']
        prepared = {'intro':'Selamat datang.', 'closing':'Terima kasih. Sesi selesai.', 'questions':[
            {'slot':'opening','category':'Perkenalan','question_text':'Ceritakan perjalanan karier Anda?', 'competencies':['communication'],'expected_points':['personal contribution']},
            {'slot':'behavior','category':'Kolaborasi','question_text':'Bagaimana Anda menghadapi konflik tim?', 'competencies':['teamwork'],'expected_points':['outcome']},
            {'slot':'decision','category':'Adaptasi','question_text':'Apa keputusan yang Anda ambil saat rencana berubah?', 'competencies':['adaptability'],'expected_points':['learning']} ]}
        async def fake_tts(text, persona, uuid, name, live=False):
            return f'/api/sessions/{uuid}/audio/{name}'
        async with SessionLocal() as db:
            stored = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
            internal_id = stored.id
        with patch('app.worker.tasks.orchestrator.parse_documents', AsyncMock(return_value={'cv_summary':{},'jd_summary':{}})), \
             patch('app.worker.tasks.orchestrator.build_questions', AsyncMock(return_value=prepared)), \
             patch('app.worker.tasks.speech.synthesize', side_effect=fake_tts):
            await prepare_session({}, internal_id)
        response = await self.client.get(f'/api/sessions/{sid}/state')
        self.assertEqual(response.json()['status'], 'ready', response.text)
        return sid, internal_id, response.json()

    async def send_answer(self, sid, qid, follow=False, streaming=False):
        with patch('app.api.sessions.speech.transcribe', AsyncMock(return_value='Saya mengukur hasil eksperimen dan meningkatkan hasil tim sebesar 35 persen.')), \
             patch('app.api.sessions.orchestrator.respond', AsyncMock(return_value={'action':'follow_up' if follow else 'next', 'response_text':'Apa hasil yang Anda ukur?' if follow else 'Terima kasih.'})), \
             patch('app.api.sessions.speech.synthesize', AsyncMock(return_value=f'/api/sessions/{sid}/audio/response.mp3')):
            return await self.client.post(f'/api/sessions/{sid}/answers' + ('?stream=true' if streaming else ''),
                data={'question_id':str(qid),'duration_ms':'12000'},files={'audio':('answer.webm',b'test audio','audio/webm')})

    async def test_auth_and_page_rendering(self):
        for route in ('/dashboard','/simulasi/baru','/riwayat'):
            response = await self.client.get(route)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('preptiva', response.text)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        self.assertEqual((await self.client.get('/health')).json()['db'], True)
        self.assertEqual((await self.client.post('/api/auth/logout', headers={'Origin':'https://attacker.example'})).status_code,403)
        self.assertEqual((await self.client.post('/api/auth/logout')).status_code,200)
        self.assertEqual((await self.client.get('/api/me')).status_code,401)
        response = await self.client.post('/api/auth/login', json={'email':'budi@example.com','password':'test12345'})
        self.assertEqual(response.status_code,200)

    async def test_uuid_ownership_and_validation(self):
        sid, _, state = await self.ready_session()
        self.assertEqual(len(sid),36)
        self.assertEqual((await self.client.get('/api/sessions/1/state')).status_code,404)
        await self.register(self.other, 'other@example.com')
        for suffix in ('state','result','audio/intro.mp3'):
            self.assertEqual((await self.other.get(f'/api/sessions/{sid}/{suffix}')).status_code,404)
        self.assertEqual((await self.other.post(f'/api/sessions/{sid}/close')).status_code,404)
        self.assertEqual((await self.client.get(f'/sesi/{sid}/ruang')).status_code,200)
        self.assertEqual((await self.create(language='fr')).status_code,422)
        self.assertEqual((await self.create(cv_text='short')).status_code,422)
        self.assertEqual((await self.create(consent='false')).status_code,422)

    async def test_full_interview_with_followup_stream_retry_and_result(self):
        sid, internal_id, state = await self.ready_session()
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/start')).status_code,200)
        first = state['current_turn']['id']
        response = await self.send_answer(sid, first, follow=True, streaming=True)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertIn('transcript',[e['type'] for e in events])
        result = events[-1]
        self.assertEqual(result['type'],'result')
        self.assertEqual(result['action'],'follow_up')
        repeat = await self.send_answer(sid,first)
        self.assertEqual(repeat.json()['answer_id'],result['answer_id'])
        too_early = await self.client.post(f'/api/sessions/{sid}/finish')
        self.assertEqual(too_early.status_code,409)
        # The single session follow-up budget is exhausted after the first follow-up.
        for _ in range(3):
            current = (await self.client.get(f'/api/sessions/{sid}/state')).json()['current_turn']
            response = await self.send_answer(sid,current['id'],follow=True)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['action'],'next')
        self.assertTrue(response.json()['is_last'])
        with patch('app.api.sessions.enqueue',new_callable=AsyncMock) as enqueue:
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/finish')).json()['status'],'scoring')
            await self.client.post(f'/api/sessions/{sid}/finish')
            self.assertEqual(enqueue.await_count,1)
        async def evaluate(context):
            return {'competency_scores':{k:{'score':4,'evidence':['Saya mengukur hasil eksperimen']} for k in context['competencies']},
                'star':{'situation':True,'task':True,'action':True,'result':True},
                'feedback':{'strengths':['Jelas'],'improvements':['Tambah konteks'],'better_answer_tip':'Jelaskan kontribusi pribadi.'}}
        review = {'summary':'Jawaban menunjukkan kontribusi pribadi.','strengths':['Jelas'],'improvements':['Tambah konteks'],'study_recommendations':[]}
        with patch('app.worker.tasks.orchestrator.evaluate', side_effect=evaluate), patch('app.worker.tasks.orchestrator.summarize',AsyncMock(return_value=review)):
            await finalize_session({},internal_id)
        response = await self.client.get(f'/api/sessions/{sid}/result')
        self.assertEqual(response.status_code,200,response.text)
        result = response.json()
        self.assertEqual(result['total_score'],4)
        self.assertEqual(len(result['items']),4)
        self.assertIn('technical',result['unmeasured'])
        self.assertEqual((await self.client.get('/api/dashboard')).json()['best_score'],4)
        await self.client.post(f'/api/sessions/{sid}/close')
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['status'],'done')

    async def test_closed_session_rejects_answers_and_start(self):
        sid, _, state = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/close')
        await self.client.post(f'/api/sessions/{sid}/close')
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/start')).status_code,409)
        self.assertEqual((await self.send_answer(sid,state['current_turn']['id'])).status_code,409)

    async def test_missing_credentials_reports_configuration(self):
        with patch('app.api.sessions.speech.require_credentials',side_effect=ValueError('Credentials required')):
            response = await self.client.post('/api/sessions',data=self.form())
        self.assertEqual(response.status_code,503)

    async def test_hourly_quota(self):
        for _ in range(5):
            self.assertEqual((await self.create()).status_code,200)
        self.assertEqual((await self.create()).status_code,429)

    async def test_session_snapshots_limits_and_enforces_them(self):
        with patch.object(settings,'answer_seconds_middle',20), patch.object(settings,'retry_limit',4), \
             patch.object(settings,'max_followups_enabled',False):
            sid, _, state = await self.ready_session()
        self.assertEqual(state['answer_seconds'],20)
        self.assertEqual(state['retry_limit'],4)
        self.assertEqual(state['max_followups'],0)
        # A later runtime config change leaves an existing session's rules intact.
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['retry_limit'],4)
        await self.client.post(f'/api/sessions/{sid}/start')
        with patch('app.api.sessions.speech.transcribe',AsyncMock(return_value='Saya mengukur hasil eksperimen.')) as stt, \
             patch('app.api.sessions.orchestrator.respond',AsyncMock(return_value={'action':'follow_up','response_text':'Apa hasilnya?'})), \
             patch('app.api.sessions.speech.synthesize',AsyncMock(return_value='/audio.mp3')):
            for fields in ({'retry_count':5,'duration_ms':12000}, {'retry_count':0,'duration_ms':25000}):
                response = await self.client.post(f'/api/sessions/{sid}/answers',data={'question_id':state['current_turn']['id'],**fields},
                    files={'audio':('answer.webm',b'test','audio/webm')})
                self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(stt.await_count,0)
            response = await self.client.post(f'/api/sessions/{sid}/answers',data={'question_id':state['current_turn']['id'],'retry_count':4,'duration_ms':12000},
                files={'audio':('answer.webm',b'test','audio/webm')})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['action'],'next')
        self.assertIsNone(response.json()['follow_up_question'])

    async def test_response_timeout_covers_tts_and_allows_retry(self):
        sid, _, state = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        async def slow_audio(*args,**kwargs):
            await asyncio.sleep(1)
        with patch.object(settings,'respond_timeout_sec',.02), \
             patch('app.api.sessions.speech.transcribe',AsyncMock(return_value='Saya mengukur hasil eksperimen.')), \
             patch('app.api.sessions.orchestrator.respond',AsyncMock(return_value={'action':'next','response_text':'Terima kasih.'})), \
             patch('app.api.sessions.speech.synthesize',side_effect=slow_audio):
            response = await self.client.post(f'/api/sessions/{sid}/answers?stream=true',
                data={'question_id':state['current_turn']['id'],'duration_ms':12000},files={'audio':('answer.webm',b'test','audio/webm')})
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[0]['type'],'transcript')
        self.assertEqual(events[-1]['type'],'error')
        self.assertIn('Waktu tunggu',events[-1]['message'])
        current = (await self.client.get(f'/api/sessions/{sid}/state')).json()['current_turn']
        self.assertEqual(current['id'],state['current_turn']['id'])
        self.assertEqual((await self.send_answer(sid,current['id'])).status_code,200)

    async def test_parallel_retries_share_one_answer(self):
        sid, _, state = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        with patch('app.api.sessions.speech.transcribe', AsyncMock(return_value='Saya mengukur hasil eksperimen.')) as transcribe, \
             patch('app.api.sessions.orchestrator.respond', AsyncMock(return_value={'action':'next','response_text':'Terima kasih.'})), \
             patch('app.api.sessions.speech.synthesize', AsyncMock(return_value='/audio.mp3')):
            async def upload():
                return await self.client.post(f'/api/sessions/{sid}/answers',data={'question_id':state['current_turn']['id'],'duration_ms':12000}, files={'audio':('answer.webm',b'test','audio/webm')})
            responses = await asyncio.gather(upload(), upload())
        self.assertEqual([r.status_code for r in responses],[200,200])
        self.assertEqual(responses[0].json()['answer_id'],responses[1].json()['answer_id'])
        self.assertEqual(transcribe.await_count,1)

    async def test_prepare_failure_is_terminal_and_no_dummy_questions(self):
        created = await self.create()
        sid = created.json()['session_id']
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
            internal_id = session.id
        with patch('app.worker.tasks.orchestrator.parse_documents',AsyncMock(side_effect=RuntimeError('provider unavailable'))):
            await prepare_session({},internal_id)
        state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(state['status'],'failed')
        self.assertEqual(state['questions'],[])

    async def test_close_during_processing_wins(self):
        sid, _, state = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        started, proceed = asyncio.Event(), asyncio.Event()
        async def transcribe(*args):
            started.set(); await proceed.wait(); return 'Saya mengukur hasil eksperimen.'
        with patch('app.api.sessions.speech.transcribe',side_effect=transcribe), \
             patch('app.api.sessions.orchestrator.respond',AsyncMock(return_value={'action':'next','response_text':'Terima kasih.'})), \
             patch('app.api.sessions.speech.synthesize',AsyncMock(return_value='/audio.mp3')):
            upload = asyncio.create_task(self.client.post(f'/api/sessions/{sid}/answers',
                data={'question_id':state['current_turn']['id'],'duration_ms':12000}, files={'audio':('answer.webm',b'test','audio/webm')}))
            await started.wait()
            await self.client.post(f'/api/sessions/{sid}/close')
            proceed.set()
            response = await upload
        self.assertEqual(response.status_code,409)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['status'],'failed')

    async def test_long_document_reads_all_chunks(self):
        active, maximum, seen = 0, 0, []
        async def fake_complete(system, data, **kwargs):
            nonlocal active, maximum
            active += 1; maximum = max(maximum, active); seen.append(data)
            await asyncio.sleep(.002)
            active -= 1
            return {'cv_summary':{'skills':['Research'],'years_exp':3},'jd_summary':{'requirements':['Design']}}
        with patch('app.ai.orchestrator.complete', side_effect=fake_complete):
            parsed = await orchestrator.parse_documents('Experience\n' * 2000 + 'FINAL_FACT', 'Job description ' * 1000)
        self.assertLessEqual(maximum,2)
        self.assertTrue(any('FINAL_FACT' in data['cv'] for data in seen))
        self.assertEqual(parsed['cv_summary']['skills'],['Research'])


class SpeechConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_format_cache_and_compatible_language_parameter(self):
        from app.ai import speech
        calls = []
        async def handle(request):
            calls.append(request)
            return httpx.Response(200,content=b'test-mp3',headers={'Content-Type':'audio/mpeg'})
        client_type = httpx.AsyncClient
        def client(**kwargs):
            return client_type(transport=httpx.MockTransport(handle))
        with tempfile.TemporaryDirectory() as folder, patch('app.ai.speech.ROOT',Path(folder)), \
             patch('app.storage.ROOT',Path(folder)), patch('app.ai.speech.httpx.AsyncClient',side_effect=client), \
             patch.object(settings,'tts_cache',True), patch.object(settings,'elevenlabs_language_code','id'), \
             patch.object(settings,'elevenlabs_model_prepared','eleven_multilingual_v2'), \
             patch.object(settings,'elevenlabs_output_format','mp3_44100_128'):
            await speech.synthesize('Halo','hr','session-test','first.mp3')
            await speech.synthesize('Halo','hr','session-test','cached.mp3')
            self.assertEqual(len(calls),1)
            self.assertNotIn('language_code',json.loads(calls[0].content))
            with patch.object(settings,'elevenlabs_output_format','mp3_22050_32'):
                await speech.synthesize('Halo','hr','session-test','different.mp3')
            self.assertEqual(calls[1].url.params['output_format'],'mp3_22050_32')
            with patch.object(settings,'elevenlabs_model_prepared','eleven_flash_v2_5'):
                await speech.synthesize('Halo','hr','session-test','language.mp3')
            self.assertEqual(json.loads(calls[2].content)['language_code'],'id')
            self.assertEqual(len(calls),3)


if __name__ == '__main__':
    unittest.main()
