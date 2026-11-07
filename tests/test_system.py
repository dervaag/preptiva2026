import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

_temporary = tempfile.TemporaryDirectory()
_test_database = os.environ.get('PREPTIVA_TEST_DATABASE_URL', '')
if _test_database:
    _parsed_test_database = urlsplit(_test_database)
    if (_parsed_test_database.scheme != 'postgresql+asyncpg'
            or _parsed_test_database.hostname not in ('127.0.0.1', 'localhost')
            or not _parsed_test_database.path.startswith('/preptiva_test_')):
        raise RuntimeError('Test database override requires a local disposable preptiva_test_* PostgreSQL database.')
os.environ['DATABASE_URL'] = _test_database or 'sqlite+aiosqlite:///' + str(Path(_temporary.name) / 'test.db')
os.environ['APP_ENV'] = 'development'
os.environ['AI_MOCK'] = 'false'
os.environ['ORCHESTRATION_ENGINE'] = 'legacy'
os.environ['REALTIME_VOICE_ENABLED'] = 'false'
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

    def test_public_origin_must_be_an_exact_https_origin(self):
        for origin in ('*', 'https://*.runkiri.cloud', 'http://app.example.com',
                       'https://app.example.com/path', 'https://user@app.example.com',
                       'https://app.example.com?query=1'):
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                Settings(_env_file=None, public_origin=origin)

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

    def test_job_description_requires_five_words_while_cv_uses_characters(self):
        self.assertEqual(validate_text('Build APIs and write tests', 'JD'), 'Build APIs and write tests')
        for text in ('Build APIs and tests', 'OneVeryLongWord' * 5):
            with self.subTest(text=text), self.assertRaises(HTTPException) as caught:
                validate_text(text, 'JD')
            self.assertEqual(caught.exception.status_code, 422)
        with self.assertRaises(HTTPException) as caught:
            validate_text('x' * 199, 'CV')
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(len(validate_text('x' * 200, 'CV')), 200)

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
        self.storage_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage_temporary.cleanup)
        storage_patch = patch('app.storage.ROOT', Path(self.storage_temporary.name))
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        async def adapt(context):
            return dict(context['planned_question'])
        self.adapt_patch = patch('app.api.sessions.orchestrator.adapt_question', side_effect=adapt)
        self.adapt_mock = self.adapt_patch.start()
        self.addCleanup(self.adapt_patch.stop)
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

    async def test_result_language_is_saved_separately_from_interview_language(self):
        response = await self.create(language='en', feedback_language='id')
        self.assertEqual(response.status_code, 200, response.text)
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == response.json()['session_id']))
            self.assertEqual(session.script['settings']['language'], 'en')
            self.assertEqual(session.script['settings']['feedback_language'], 'id')
        invalid = await self.create(feedback_language='fr')
        self.assertEqual(invalid.status_code, 422)

    async def test_mobile_device_cannot_start_session(self):
        sid, _, _ = await self.ready_session()
        mobile_headers = [
            {'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile'},
            {'User-Agent':'Mozilla/5.0 (Linux; Android 15; Tablet) AppleWebKit'},
            {'User-Agent':'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)'},
            {'Sec-CH-UA-Mobile':'?1'},
            {'Sec-CH-UA-Platform':'"Android"'},
            {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)', 'X-Preptiva-Device':'mobile'},
        ]
        for headers in mobile_headers:
            with self.subTest(headers=headers):
                response = await self.client.post(f'/api/sessions/{sid}/start',headers=headers)
                self.assertEqual(response.status_code,403,response.text)
                self.assertIn('PC atau laptop',response.json()['detail'])
        state = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(state['status'],'ready')
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/start',headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})).status_code,200)

    async def ready_session(self, **changes):
        created = await self.create(**changes)
        self.assertEqual(created.status_code, 200, created.text)
        sid = created.json()['session_id']
        prepared = {'intro':'Selamat datang.', 'closing':'Terima kasih. Sesi selesai.', 'questions':[
            {'slot':'opening','category':'Perkenalan','question_text':'Ceritakan perjalanan karier Anda?', 'competencies':['communication'],'expected_points':['personal contribution']},
            {'slot':'behavior','category':'Kolaborasi','question_text':'Bagaimana Anda menghadapi konflik tim?', 'competencies':['teamwork'],'expected_points':['outcome']},
            {'slot':'decision','category':'Adaptasi','question_text':'Apa keputusan yang Anda ambil saat rencana berubah?', 'competencies':['adaptability'],'expected_points':['learning']} ]}
        self.prepared_voices = {}
        async def fake_tts(text, persona, uuid, name, live=False):
            self.prepared_voices[name] = persona
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
        if not hasattr(self, 'turn_voices'):
            self.turn_voices = []
        async def audio(text, persona, uuid, name, live=False):
            self.turn_voices.append((name, persona))
            return f'/api/sessions/{sid}/audio/response.mp3'
        with patch('app.api.sessions.speech.transcribe', AsyncMock(return_value='Saya mengukur hasil eksperimen dan meningkatkan hasil tim sebesar 35 persen.')), \
             patch('app.api.sessions.orchestrator.respond', AsyncMock(return_value={'action':'follow_up' if follow else 'next', 'response_text':'Apa hasil yang Anda ukur?' if follow else 'Terima kasih.'})), \
             patch('app.api.sessions.speech.synthesize', side_effect=audio):
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

    async def test_public_tunnel_origin_keeps_cross_site_protection(self):
        public = 'https://test-public.runkiri.cloud'
        credentials = {'email':'budi@example.com', 'password':'test12345'}
        await self.client.post('/api/auth/logout')
        with patch.object(settings, 'public_origin', ''):
            response = await self.other.post('/api/auth/login', json=credentials, headers={'Origin':public})
            self.assertEqual(response.status_code, 403)
        with patch.object(settings, 'public_origin', public):
            response = await self.other.post('/api/auth/login', json=credentials,
                headers={'Origin':public, 'Sec-Fetch-Site':'same-origin'})
            self.assertEqual(response.status_code, 200)
            for origin in ('https://attacker.example', public+'.attacker.example',
                           'http://test-public.runkiri.cloud', 'https://other.runkiri.cloud'):
                with self.subTest(origin=origin):
                    response = await self.other.post('/api/auth/logout',
                        headers={'Origin':origin, 'X-Forwarded-Host':origin.split('://')[1]})
                    self.assertEqual(response.status_code, 403)
            response = await self.other.post('/api/auth/logout',
                headers={'Origin':public, 'Sec-Fetch-Site':'cross-site'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual((await self.other.get('/api/me')).status_code, 200)
            response = await self.other.post('/api/auth/logout',
                headers={'Origin':public, 'Sec-Fetch-Site':'same-origin'})
            self.assertEqual(response.status_code, 200)

    async def test_profile_authentication_and_user_isolation(self):
        for method, path, data in (
                ('GET', '/api/profile', None),
                ('PATCH', '/api/profile', {'name':'Unauthorized update'}),
                ('DELETE', '/api/profile/cv', None)):
            response = await self.other.request(method, path, data=data)
            self.assertEqual(response.status_code, 401, response.text)
        own_cv = 'Pengalaman riset produk dan evaluasi aksesibilitas pengguna. ' * 8
        other_cv = 'Pengalaman menyusun laporan akuntansi dan rekonsiliasi bank. ' * 8
        response = await self.client.patch('/api/profile', data={'cv_text':own_cv})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual((await self.register(self.other, 'other@example.com')).status_code, 200)
        response = await self.other.patch('/api/profile', data={'name':'Kandidat Lain', 'cv_text':other_cv})
        self.assertEqual(response.status_code, 200, response.text)
        own = (await self.client.get('/api/profile')).json()
        other = (await self.other.get('/api/profile')).json()
        self.assertNotEqual(own['id'], other['id'])
        self.assertEqual(own['name'], 'Budi Santoso')
        self.assertEqual(own['cv_text'], own_cv.strip())
        self.assertEqual(other['cv_text'], other_cv.strip())
        for method, path, data in (
                ('PATCH', '/api/profile', {'name':'Cross origin update'}),
                ('DELETE', '/api/profile/cv', None)):
            response = await self.client.request(method, path, data=data,
                headers={'Origin':'https://attacker.example'})
            self.assertEqual(response.status_code, 403)
        self.assertEqual((await self.other.request('DELETE', '/api/profile/cv',
            json={'password':'test12345','confirmation':'HAPUS CV'})).status_code, 200)
        self.assertEqual((await self.client.get('/api/profile')).json(), own)
        self.assertFalse((await self.other.get('/api/profile')).json()['has_cv'])

    async def test_profile_updates_login_and_rolls_back_duplicate_email(self):
        self.assertEqual((await self.register(self.other, 'other@example.com')).status_code, 200)
        response = await self.client.patch('/api/profile', data={
            'name':'  Nama Baru  ', 'email':'NEW@example.com', 'gender':'female', 'age':'31', 'current_password':'test12345'})
        self.assertEqual(response.status_code, 200, response.text)
        profile = response.json()
        self.assertEqual((profile['name'], profile['email'], profile['gender'], profile['age']),
                         ('Nama Baru', 'new@example.com', 'female', 31))
        response = await self.client.patch('/api/profile', data={
            'name':'Should roll back', 'email':'other@example.com', 'current_password':'test12345'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual((await self.client.get('/api/profile')).json(), profile)
        for changes in ({'name':'  '}, {'email':'not-an-email'}, {'age':'81'}, {}):
            with self.subTest(changes=changes):
                response = await self.client.patch('/api/profile', data=changes)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual((await self.client.get('/api/profile')).json(), profile)
        self.assertEqual((await self.client.post('/api/auth/logout')).status_code, 200)
        response = await self.client.post('/api/auth/login', json={
            'email':'new@example.com', 'password':'test12345'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.get('/api/me')).json()['id'], profile['id'])

    async def test_profile_cv_validation_delete_and_existing_session_snapshot(self):
        created = await self.create()
        self.assertEqual(created.status_code, 200, created.text)
        sid = created.json()['session_id']
        original_cv = self.form()['cv_text'].strip()
        cv = '</textarea><script>alert(1)</script> Pengalaman sintetis untuk uji profil. ' * 8
        response = await self.client.patch('/api/profile', data={'cv_text':cv})
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertTrue(saved['has_cv'])
        self.assertEqual(saved['cv_text'], cv.strip())
        response = await self.client.patch('/api/profile', data={'name':'Should not save', 'cv_text':'short'})
        self.assertEqual(response.status_code, 422, response.text)
        for content, status in ((b'not a PDF', 422), (b'%PDF-' + b'x' * (5 * 1024 * 1024), 413)):
            response = await self.client.patch('/api/profile', files={'cv_pdf':('cv.pdf', content, 'application/pdf')})
            self.assertEqual(response.status_code, status, response.text)
        self.assertEqual((await self.client.get('/api/profile')).json(), saved)
        for route in ('/profile', '/profil'):
            response = await self.client.get(route)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('</textarea><script>alert(1)</script>', response.text)
            self.assertNotIn('&lt;/textarea&gt;&lt;script&gt;', response.text)
            self.assertNotIn('name="cv_text"', response.text)
        response = await self.client.request('DELETE', '/api/profile/cv',
            json={'password':'test12345','confirmation':'HAPUS CV'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['has_cv'])
        self.assertEqual(response.json()['cv_text'], '')
        self.assertFalse((await self.client.get('/api/me')).json()['has_cv'])
        async with SessionLocal() as db:
            existing = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
            self.assertEqual(existing.cv_text, original_cv)

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

    async def test_panel_turns_adapt_from_conversation_and_keep_speaker(self):
        sid, internal, data = await self.ready_session(panel=['hr', 'user', 'manager'], career_stage='fresh_graduate')
        self.assertEqual([q['interviewer'] for q in data['questions']], ['hr', 'user', 'manager'])
        self.assertEqual(len(data['panel']), 3)
        self.assertEqual(self.prepared_voices['q1.mp3'], 'hr')
        self.assertNotIn('q2.mp3', self.prepared_voices)
        self.assertEqual(self.prepared_voices['closing.mp3'], 'manager')
        await self.client.post(f'/api/sessions/{sid}/start')
        first = data['current_turn']['id']
        follow = (await self.send_answer(sid, first, follow=True)).json()
        self.assertEqual(follow['follow_up_question']['interviewer'], 'hr')
        self.adapt_mock.assert_not_called()
        next_turn = (await self.send_answer(sid, follow['follow_up_question']['id'])).json()
        self.assertEqual(next_turn['next_question']['interviewer'], 'user')
        context = self.adapt_mock.call_args.args[0]
        self.assertEqual(context['interviewer'], 'user')
        self.assertEqual(context['candidate_profile']['career_stage'], 'fresh_graduate')
        self.assertEqual(len(context['context_packet']['recent_turns']), 2)
        self.assertIn('35 persen', context['context_packet']['recent_turns'][-1]['answer'])
        third = (await self.send_answer(sid, next_turn['next_question']['id'])).json()
        self.assertEqual(third['next_question']['interviewer'], 'manager')
        self.assertEqual(third['response_interviewer'], 'user')
        self.assertEqual([persona for name, persona in self.turn_voices if name.startswith('q')], ['user','manager'])

    async def test_panel_rejects_invalid_members_and_checks_all_voices(self):
        for roles in (['hr'], ['hr', 'hr'], ['hr', 'unknown'], ['hr', 'user', 'manager', 'hr']):
            self.assertEqual((await self.create(panel=roles)).status_code, 422)
        with patch('app.api.sessions.speech.require_credentials', side_effect=[None, ValueError('Voice User missing')]) as voice:
            response = await self.client.post('/api/sessions', data={**self.form(), 'panel':['hr', 'user']})
        self.assertEqual(response.status_code, 503)
        self.assertEqual([call.args[0] for call in voice.call_args_list], ['hr', 'user'])

    async def test_dynamic_failure_rolls_back_and_retry_is_idempotent(self):
        sid, internal, data = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        qid = data['current_turn']['id']
        self.adapt_mock.side_effect = RuntimeError('adaptation unavailable')
        response = await self.send_answer(sid, qid, streaming=True)
        self.assertIn('"type": "error"', response.text)
        current = (await self.client.get(f'/api/sessions/{sid}/state')).json()
        self.assertEqual(current['current_turn']['id'], qid)
        self.assertEqual(current['questions'][1]['question_text'], data['questions'][1]['question_text'])
        async def revised(context):
            return {**context['planned_question'], 'question_text':'Apa yang Anda ubah dalam proyek kuliah setelah menerima masukan?'}
        self.adapt_mock.side_effect = revised
        result = (await self.send_answer(sid, qid)).json()
        self.assertIn('proyek kuliah', result['next_question']['question_text'])
        calls = self.adapt_mock.call_count
        retry = (await self.send_answer(sid, qid)).json()
        self.assertEqual(result, retry)
        self.assertEqual(self.adapt_mock.call_count, calls)

    async def test_panel_evaluation_keeps_hr_separate_from_technical_scores(self):
        from app.models import InterviewQuestion
        sid, internal, data = await self.ready_session(panel=['hr','user','manager'], career_stage='fresh_graduate')
        async with SessionLocal() as db:
            q = await db.get(InterviewQuestion, data['questions'][1]['id'])
            q.competencies = ['technical']
            await db.commit()
        await self.client.post(f'/api/sessions/{sid}/start')
        for q in data['questions']:
            response = await self.send_answer(sid, q['id'])
            self.assertEqual(response.status_code, 200)
        with patch('app.api.sessions.enqueue', AsyncMock()):
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/finish')).status_code,200)
        seen = []
        async def evaluate(context):
            seen.append(context)
            return {'competency_scores':{k:{'score':4,'evidence':['Saya mengukur hasil eksperimen']} for k in context['competencies']},
                    'feedback':{}, 'star':{}}
        with patch('app.worker.tasks.orchestrator.evaluate', side_effect=evaluate), \
             patch('app.worker.tasks.orchestrator.summarize', AsyncMock(return_value={'summary':'Ringkasan panel'})):
            await finalize_session({},internal)
        result = (await self.client.get(f'/api/sessions/{sid}/result')).json()
        self.assertEqual([c['interviewer'] for c in seen], ['hr','user','manager'])
        self.assertNotIn('| technical |', seen[0]['rubric'])
        self.assertIn('| technical |', seen[1]['rubric'])
        self.assertNotIn('cv_summary',seen[0])
        self.assertEqual(len(result['panel_results']),3)
        hr = result['panel_results'][0]
        technical = next(c for c in hr['competencies'] if c['key']=='technical')
        self.assertEqual(technical['weight'],0)
        self.assertIsNone(technical['score'])
        self.assertFalse(result['assessment']['validated'])

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


    async def test_question_interruption_retry_skip_and_duplicate_delivery(self):
        from app.models import InterviewEvent
        sid, internal, initial = await self.ready_session(panel=['hr','user'])
        await self.client.post(f'/api/sessions/{sid}/start')
        qid = initial['current_turn']['id']
        payload = {'question_id':qid,'reason':'tab_hidden'}
        interrupted = (await self.client.post(f'/api/sessions/{sid}/interrupt',json=payload)).json()['state']
        self.assertEqual(interrupted['status'],'running')
        self.assertEqual(interrupted['checkpoint']['remaining_seconds'],0)
        duplicate = (await self.client.post(f'/api/sessions/{sid}/interrupt',json=payload)).json()['state']
        self.assertEqual(interrupted['checkpoint'],duplicate['checkpoint'])
        self.assertEqual((await self.send_answer(sid,qid)).status_code,409)
        data = {'question_id':qid,'interruption_id':interrupted['checkpoint']['interruption_id'],'action':'retry'}
        retried = (await self.client.post(f'/api/sessions/{sid}/recover',json=data)).json()
        self.assertEqual(retried['current_turn']['id'],qid)
        self.assertEqual(retried['checkpoint']['remaining_seconds'],initial['answer_seconds'])
        repeated = (await self.client.post(f'/api/sessions/{sid}/recover',json=data)).json()
        self.assertEqual(repeated['checkpoint'],retried['checkpoint'])
        interrupted = (await self.client.post(f'/api/sessions/{sid}/interrupt',json=payload)).json()['state']
        data.update(action='next',interruption_id=interrupted['checkpoint']['interruption_id'])
        with patch('app.api.sessions.speech.synthesize',AsyncMock(return_value=None)), \
             patch('app.api.sessions.speech.transcribe',AsyncMock()) as stt:
            skipped = await self.client.post(f'/api/sessions/{sid}/recover',json=data)
            self.assertEqual(skipped.status_code,200,skipped.text)
            result = skipped.json()
            duplicate = await self.client.post(f'/api/sessions/{sid}/recover',json=data)
            self.assertEqual(result,duplicate.json())
            self.assertTrue(result['skipped'])
            self.assertEqual(result['next_question']['main_order'],2)
            stt.assert_not_called()
        late = (await self.client.post(f'/api/sessions/{sid}/interrupt',json=payload)).json()
        self.assertTrue(late['already_completed'])
        self.assertEqual(late['state']['checkpoint']['phase'],'question_ready')
        async with SessionLocal() as db:
            events = (await db.scalars(select(InterviewEvent).where(InterviewEvent.session_id==internal))).all()
            self.assertEqual(sum(e.kind=='question_skipped' for e in events),1)
            self.assertEqual(sum(e.kind=='question_retried' for e in events),1)
        await self.register(self.other,'other@example.com')
        self.assertEqual((await self.other.post(f'/api/sessions/{sid}/interrupt',json=payload)).status_code,404)
        self.assertEqual((await self.other.post(f'/api/sessions/{sid}/recover',json=data)).status_code,404)

    async def test_text_answer_and_tts_failure_keep_interview_usable(self):
        sid, _, initial = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        with patch('app.api.sessions.speech.transcribe',AsyncMock()) as stt, \
             patch('app.api.sessions.speech.synthesize',AsyncMock(side_effect=RuntimeError('voice unavailable'))), \
             patch('app.api.sessions.orchestrator.respond',AsyncMock(return_value={'action':'next','response_text':'Terima kasih.'})):
            response = await self.client.post(f'/api/sessions/{sid}/answers',data={
                'question_id':initial['current_turn']['id'],'duration_ms':100,'text_answer':'Saya mengukur hasil eksperimen.'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['input_mode'],'text')
        self.assertIsNone(response.json()['response_audio_url'])
        self.assertIsNone(response.json()['next_question']['audio_url'])
        stt.assert_not_called()

    async def test_skipped_session_and_failed_evaluation_can_be_retried(self):
        sid, internal, initial = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        for q in initial['questions']:
            result = (await self.client.post(f'/api/sessions/{sid}/interrupt',json={'question_id':q['id']})).json()
            with patch('app.api.sessions.speech.synthesize',AsyncMock(return_value=None)):
                skip = await self.client.post(f'/api/sessions/{sid}/recover',json={'question_id':q['id'],
                    'interruption_id':result['state']['checkpoint']['interruption_id'],'action':'next'})
            self.assertEqual(skip.status_code,200,skip.text)
        with patch('app.api.sessions.enqueue',AsyncMock()):
            await self.client.post(f'/api/sessions/{sid}/finish')
        with patch('app.worker.tasks.orchestrator.summarize',AsyncMock(side_effect=RuntimeError('temporary failure'))):
            await finalize_session({},internal)
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/state')).json()['status'],'evaluation_failed')
        with patch('app.api.sessions.enqueue',AsyncMock()):
            await self.client.post(f'/api/sessions/{sid}/finish')
        with patch('app.worker.tasks.orchestrator.evaluate',AsyncMock()) as evaluator, \
             patch('app.worker.tasks.orchestrator.summarize',AsyncMock(return_value={'summary':'Belum ada jawaban.','strengths':[],'improvements':[],'study_recommendations':[]})):
            await finalize_session({},internal)
            await finalize_session({},internal)
        evaluator.assert_not_called()
        result = (await self.client.get(f'/api/sessions/{sid}/result')).json()
        self.assertIsNone(result['total_score'])
        self.assertEqual(result['coverage']['measured'],0)
        self.assertTrue(all(i['skipped'] for i in result['items']))


    async def test_realtime_receipt_correction_idempotency_and_retry_scope(self):
        from app.services.voice_capture import seal
        from app.models import InterviewEvent
        with patch.object(settings, 'realtime_voice_enabled', True):
            sid, internal, state = await self.ready_session()
        self.assertFalse(self.prepared_voices)  # Speech is fetched on playback, not eagerly.
        qid = state['current_turn']['id']
        self.assertTrue(state['current_turn']['audio_url'].endswith(f'/speech/question/{qid}'))
        await self.client.post(f'/api/sessions/{sid}/start')
        async with SessionLocal() as db:
            stored = await db.get(InterviewSession, internal)
            token = seal(stored, qid, 'Saya mengukur hasil eksperimen.', 1200, ['segment-1'])
            stored.script = {**stored.script, 'voice_lease': {'id':'old', 'until':'9999'}}
            await db.commit()
        stopped = (await self.client.post(f'/api/sessions/{sid}/interrupt', json={'question_id':qid,'reason':'tab_hidden'})).json()
        async with SessionLocal() as db:
            self.assertEqual((await db.get(InterviewSession, internal)).script['voice_lease'], {})
        await self.client.post(f'/api/sessions/{sid}/recover', json={'question_id':qid,'action':'retry',
            'interruption_id':stopped['state']['checkpoint']['interruption_id']})
        data = {'question_id':qid, 'capture_token':token, 'duration_ms':100}
        self.assertEqual((await self.client.post(f'/api/sessions/{sid}/answers', data=data)).status_code, 422)
        async with SessionLocal() as db:
            data['capture_token'] = seal(await db.get(InterviewSession, internal), qid, 'Saya mengukur hasil eksperimen.', 1200, ['segment-2'])
        data['corrected_transcript'] = 'Saya mengukur hasil eksperimen sebesar 35 persen.'
        with patch('app.api.sessions.orchestrator.respond', AsyncMock(return_value={'action':'next','response_text':'Terima kasih.'})), \
                patch('app.api.sessions.speech.transcribe', AsyncMock()) as stt, \
                patch('app.api.sessions.speech.optional_synthesize', AsyncMock()) as tts:
            response = await self.client.post(f'/api/sessions/{sid}/answers', data=data)
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result['input_mode'], 'realtime')
            self.assertEqual(result['original_transcript'], 'Saya mengukur hasil eksperimen.')
            self.assertEqual(result['transcript'], data['corrected_transcript'])
            self.assertTrue(result['transcript_corrected'])
            self.assertIn('/speech/response/', result['response_audio_url'])
            stt.assert_not_called(); tts.assert_not_called()
            # A previously accepted answer is returned even when its receipt has expired.
            data['capture_token'] = 'expired-token'
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/answers', data=data)).json(), result)
        async with SessionLocal() as db:
            answer = await db.get(InterviewAnswer, result['answer_id'])
            self.assertEqual(answer.duration_sec, 1.2)
            questions = (await db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id==internal).order_by(InterviewQuestion.main_order))).all()
            future = questions[-1].id
        self.assertEqual((await self.client.get(f'/api/sessions/{sid}/speech/question/{future}')).status_code, 404)
        await self.register(self.other, 'other-voice@example.com')
        self.assertEqual((await self.other.get(f'/api/sessions/{sid}/speech/response/{result["answer_id"]}')).status_code, 404)
        metric={'answer_id':result['answer_id'],'elapsed_ms':1234}
        for _ in range(2):
            self.assertEqual((await self.client.post(f'/api/sessions/{sid}/voice-latency',json=metric)).status_code, 200)
        async with SessionLocal() as db:
            events=(await db.scalars(select(InterviewEvent).where(InterviewEvent.session_id==internal,
                InterviewEvent.kind=='voice_first_playing'))).all()
            self.assertEqual(len(events), 1)


    async def test_job_rubric_is_opt_in_and_full_evaluation_keeps_snapshot_sources(self):
        from app.ai.blueprint import blueprint
        from app.ai.job_rubric import snapshot_profile
        for changes in ({'interviewer':'hr','job_role':'Engineering Manager'},
                        {'interviewer':'manager','job_role':'Product Manager'},
                        {'interviewer':'manager','job_role':'Engineering Manager','panel':['manager','user']}):
            self.assertEqual((await self.create(use_job_rubric='true',**changes)).status_code,422)
        created=await self.create(use_job_rubric='true',job_role='Engineering Manager',interviewer='manager',question_count='5')
        self.assertEqual(created.status_code,200,created.text);sid=created.json()['session_id']
        async def prepare(context,history):
            plan=blueprint(5,context['uuid'],['manager'],context['guidebook'],context['assessment'])
            return {'intro':'Selamat datang.','closing':'Terima kasih.','plan':plan,'questions':[
                {'slot':p['slot'],'category':p['competencies'][0],'question_text':f'Ceritakan pengalaman pada konteks kerja nomor {i}?',
                 'competencies':p['competencies'],'expected_points':['Kontribusi dan hasil']} for i,p in enumerate(plan,1)]}
        async with SessionLocal() as db:
            stored=await db.scalar(select(InterviewSession).where(InterviewSession.uuid==sid));internal=stored.id
            frozen=json.loads(json.dumps(stored.script['assessment']))
        with patch('app.worker.tasks.orchestrator.parse_documents',AsyncMock(return_value={'cv_summary':{},'jd_summary':{}})), \
                patch('app.worker.tasks.orchestrator.build_questions',side_effect=prepare), \
                patch('app.worker.tasks.speech.optional_synthesize',AsyncMock(return_value=None)):
            await prepare_session({},internal)
        await self.client.post(f'/api/sessions/{sid}/start')
        for _ in range(5):
            current=(await self.client.get(f'/api/sessions/{sid}/state')).json()['current_turn']
            self.assertEqual((await self.send_answer(sid,current['id'])).status_code,200)
        with patch('app.api.sessions.enqueue',AsyncMock()):await self.client.post(f'/api/sessions/{sid}/finish')
        seen=[]
        async def evaluate(context):
            seen.append(context)
            self.assertEqual(set(context['competency_definitions']),set(context['competencies']))
            quote=context['source_turns'][0]['transcript'];key=context['competencies'][0]
            anchor=context['competency_definitions'][key]['levels']['4']['id']
            return {'competency_scores':{key:{'score':4,'evidence':[quote],'evidence_sufficiency':'sufficient',
                'indicators_met':[anchor],'indicator_evidence':[{'indicator_id':anchor,'quote':quote}],
                'next_level_gap':'Perlu menjelaskan hasil peninjauan.'}},'star':{},'feedback':{}}
        summary={'summary':'Synthetic integration fixture.','strengths':[],'improvements':[],'study_recommendations':[]}
        with patch('app.worker.tasks.orchestrator.evaluate',side_effect=evaluate), \
                patch('app.worker.tasks.orchestrator.summarize',AsyncMock(return_value=summary)), \
                patch('app.ai.job_rubric.load_profile',side_effect=AssertionError('Must use frozen snapshot')):
            await finalize_session({},internal)
            response=await self.client.get(f'/api/sessions/{sid}/result')
        self.assertEqual(response.status_code,200,response.text);result=response.json()
        self.assertEqual(len(seen),5);self.assertEqual(result['total_score'],4)
        self.assertEqual(result['coverage']['total'],5);self.assertEqual(result['coverage']['weighted_percent'],100)
        self.assertEqual(result['assessment']['sha256'],frozen['sha256']);self.assertFalse(result['assessment']['validated'])
        self.assertEqual({c['name'] for c in result['competencies']},{c['name'] for c in frozen['competency_definitions'].values()})
        dashboard=(await self.client.get('/api/dashboard')).json()
        self.assertEqual(dashboard['competency_trend'],{})
        self.assertEqual(dashboard['competency_trend_by_rubric'][frozen['sha256']]['profile_id'],frozen['profile_id'])
        for item in result['items']:
            for score in item['competency_scores'].values():
                self.assertEqual(score['indicator_validation'],'verified')
                self.assertTrue(score['sources']);self.assertEqual(score['next_level_indicators'][0]['level'],5)


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


class GuidebookTests(unittest.IsolatedAsyncioTestCase):
    def context(self, roles=None):
        from app.ai.guidebook import snapshot, profile
        cv = 'Lulusan baru Akuntansi. Proyek kuliah menyusun laporan keuangan koperasi kampus.'
        summary = {'skills':['rekonsiliasi'], 'education':['Akuntansi'], 'career_stage':'fresh_graduate',
                   'career_stage_evidence':'Lulusan baru Akuntansi.',
                   'evidence':[{'kind':'project', 'quote':'Proyek kuliah menyusun laporan keuangan koperasi kampus.'}]}
        return {'uuid':'stable-session', 'question_count':3, 'interviewer':'hr', 'panel':roles or ['hr'],
                'job_role':'Accountant', 'level':'junior', 'industry':'Finance', 'language':'id',
                'cv_summary':summary, 'jd_summary':{'requirements':['Technical accounting standards'], 'responsibilities':['Prepare accurate reports']},
                'candidate_profile':profile(summary, cv), 'guidebook':snapshot()}

    def test_profile_requires_cv_evidence_and_never_uses_target_level(self):
        from app.ai.guidebook import profile
        cv = 'Lulusan baru Akuntansi. Proyek kampus koperasi mahasiswa.'
        actual = profile({'career_stage':'experienced', 'career_stage_evidence':'Managed ten people for five years',
                          'evidence':[{'quote':'Nonexistent employment at Acme'}], 'years_exp':0}, cv)
        self.assertEqual(actual['career_stage'], 'unknown')
        self.assertNotIn('Nonexistent', str(actual['anchors']))
        self.assertEqual(profile({}, cv, 'fresh_graduate')['career_stage'], 'fresh_graduate')
        self.assertEqual(self.context()['candidate_profile']['career_stage'], 'fresh_graduate')

    def test_role_context_and_61_angles_are_separate_and_stable(self):
        from app.ai.guidebook import role_context
        from app.ai.blueprint import blueprint
        context = self.context(['hr', 'user', 'manager'])
        self.assertEqual([len(context['guidebook']['roles'][p]['angles']) for p in context['panel']], [21,20,20])
        hr = role_context(context, 'hr')
        self.assertNotIn('cv_summary', hr)
        self.assertNotIn('Technical accounting standards', str(hr))
        self.assertIn('Technical accounting standards', str(role_context(context, 'user')))
        first = blueprint(7, 'a', context['panel'], context['guidebook'])
        self.assertEqual(first, blueprint(7, 'a', context['panel'], context['guidebook']))
        self.assertNotEqual(first, blueprint(7, 'b', context['panel'], context['guidebook']))
        self.assertEqual(len({s['intent_id'] for s in first}),7)

    def test_hr_allows_technical_cv_background_but_rejects_quizzes_and_scores(self):
        from app.ai.blueprint import forbidden_hr, validate_questions
        self.assertFalse(forbidden_hr('Dalam proyek SQL Anda, bagaimana Anda menangani konflik tim?'))
        self.assertTrue(forbidden_hr('Bagaimana optimasi query SQL Anda?'))
        q={'slot':'opening','question_text':'Apa motivasi memilih posisi ini?', 'competencies':['technical']}
        with self.assertRaises(ValueError):
            validate_questions([q],[{'slot':'opening'}],'hr',[])

    async def test_generation_uses_separate_prompts_and_voices_by_plan(self):
        from app.ai.closing import closing_text
        context = self.context(['hr','user','manager'])
        async def complete(system, data, **kwargs):
            return {'intro':'Selamat datang.', 'closing':'Penutup ' + data['interviewer'], 'questions':[
                {'slot':s['slot'],'category':'Latihan','question_text':s['angle']+'?', 'anchor_id':'cv1',
                 'expected_points':['Concrete example'], 'competencies':s['competencies']} for s in data['blueprint']]}
        for language in ('id', 'en'):
            with self.subTest(language=language):
                context['language'] = language
                with patch('app.ai.orchestrator.complete', side_effect=complete) as calls:
                    result = await orchestrator.build_questions(context, {'hr':[], 'user':[], 'manager':[]})
                self.assertEqual(calls.call_count,3)
                self.assertEqual([c.args[1]['interviewer'] for c in calls.call_args_list], ['hr','user','manager'])
                self.assertEqual([c.args[1]['language'] for c in calls.call_args_list], [language] * 3)
                self.assertNotIn('requirements', str(calls.call_args_list[0].args[1]))
                self.assertEqual([s['interviewer'] for s in result['plan']], ['hr','user','manager'])
                self.assertEqual(len(result['questions']),3)
                self.assertEqual(result['closing'], closing_text(language))

    async def test_adaptation_repairs_repetition_and_retains_grounding(self):
        from app.ai.guidebook import role_context
        context = role_context(self.context(), 'hr')
        old = 'Bagaimana Anda menangani konflik dalam proyek koperasi kampus?'
        new = 'Setelah masukan dari tim koperasi kampus, kebiasaan komunikasi apa yang Anda ubah?'
        planned = {'slot':'behavior','category':'Kolaborasi','question_text':old,'anchor_id':'cv1',
                   'expected_points':['Concrete example'],'competencies':['teamwork']}
        context.update(planned_question=planned, conversation=[{'question':'Apa pengalaman Anda?', 'answer':'Saya baru lulus dan hanya pernah mengerjakan proyek koperasi kampus.'}], asked_questions=[old])
        with patch('app.ai.orchestrator.complete', side_effect=[{'question':planned}, {'question':{**planned,'question_text':new}}]) as call:
            result = await orchestrator.adapt_question(context)
        self.assertEqual(result['question_text'],new)
        self.assertEqual(call.call_count,2)
        self.assertIn('baru lulus', call.call_args.args[1]['conversation'][0]['answer'])

    async def test_hr_followup_repairs_wrong_scope(self):
        with patch('app.ai.orchestrator.complete', side_effect=[{'action':'follow_up','response_text':'Bagaimana optimasi query SQL?'},
                {'action':'follow_up','response_text':'Bagaimana Anda meminta bantuan dalam proyek tersebut?'}]) as call:
            result = await orchestrator.respond({'interviewer':'hr','language':'id','allow_followup':True})
        self.assertEqual(call.call_count,2)
        self.assertIn('meminta bantuan', result['response_text'])


if __name__ == '__main__':
    unittest.main()


class MemoryAndEvidenceTests(unittest.TestCase):
    def test_packet_bounds_and_retrieves_source_claim_without_inventing_verification(self):
        from types import SimpleNamespace
        from app.ai import memory
        session=SimpleNamespace(script={'assessment':snapshot('hr')})
        question=SimpleNamespace(id=70,question_text='Apa strategi rekonsiliasi yang digunakan?',competencies=['technical'],kind='main',slot='behavior')
        turns=[{'turn_id':f'q{i}','question_id':i,'question':'Apa pengalaman Anda?', 'interviewer':'hr',
                'answer':('Saya melakukan rekonsiliasi bank. ' if i == 1 else 'Saya berkolaborasi dengan teman. ') * 400,
                'competencies':['technical'] if i == 1 else ['communication']} for i in range(1,25)]
        data=memory.packet(session,turns,question,'user')
        self.assertLessEqual(len(json.dumps(data,ensure_ascii=False)),memory.PACKET_CHARS)
        self.assertEqual(len(data['recent_turns']),3)
        self.assertIn('q1',[t['turn_id'] for t in data['retrieved_turns']])
        self.assertTrue(all(f['verification_status']=='unverified' for f in data['candidate_facts']))
        quote='Saya melakukan rekonsiliasi bank.'
        self.assertEqual(memory.validate_refs([{'turn_id':'q1','quote':quote}],data)[0]['quote'],quote)
        for ref in ({'turn_id':'q999','quote':quote},{'turn_id':'q1','quote':'I managed one hundred employees.'}):
            with self.assertRaises(ValueError): memory.validate_refs([ref],data)
        with self.assertRaises(ValueError): memory.validate_refs([],data,required=True)
        for fact in data['candidate_facts']:
            original = next(t['answer'] for t in turns if t['turn_id'] == fact['source_turn_id'])
            self.assertIn(fact['quote'],original)
        self.assertEqual(len(turns[0]['answer']),len('Saya melakukan rekonsiliasi bank. ')*400)

    def test_insufficient_evidence_is_not_low_ability_and_quotes_keep_turn_boundaries(self):
        source=[{'turn_id':'q1','transcript':'Saya tidak memeriksa hasil sebelum mengirim laporan.'},
                {'turn_id':'q2','transcript':'Saya mengukur hasil eksperimen.'}]
        scores=verified_scores({'technical':{'score':5,'evidence':['laporan. Saya mengukur']},
            'communication':{'score':1,'evidence':['Saya tidak memeriksa hasil sebelum mengirim laporan.'],'evidence_sufficiency':'sufficient'},
            'teamwork':{'score':4,'evidence':['Saya mengukur hasil eksperimen.'],'evidence_sufficiency':'partial'}},
            ' '.join(t['transcript'] for t in source),['technical','communication','teamwork'],source)
        self.assertEqual(scores['technical']['score'],2)
        self.assertEqual(scores['technical']['status'],'insufficient')
        self.assertEqual(scores['teamwork']['score_status'],'provisional')
        self.assertEqual(scores['communication']['source_refs'][0]['turn_id'],'q1')
        total,items=aggregate([scores],WEIGHTS['hr'])
        self.assertEqual(total,1)  # Demonstrated low performance remains measurable.
        self.assertIsNone(next(c['score'] for c in items if c['key']=='teamwork'))
        empty=verified_scores({},'???',['communication'],[{'turn_id':'q9','transcript':'???'}])
        self.assertEqual(empty['communication']['status'],'unusable_transcript')

    def test_assessor_comparison_rejects_unrated_cases_and_handles_undefined_kappa(self):
        from validation.compare import compare,kappa
        self.assertEqual(kappa([1,2,3,4,5],[1,2,3,4,5]),1)
        self.assertIsNone(kappa([3,3],[3,3]))
        cases=[{'id':str(i),'split':'test','competency':'leadership','transcript':'Saya mengukur hasil eksperimen.',
                'language':'id','human_ratings':{'a':i,'b':i,'c':i},'consensus_score':i,
                'ai_runs':[i]*5,'ai_quotes':['Saya mengukur hasil eksperimen.']} for i in (1,2,3)]
        report=compare({'cases':cases})
        self.assertEqual(report['ai_vs_consensus_kappa'],1)
        self.assertEqual(report['stable_range_at_most_one_percent'],100)
        self.assertFalse(report['validated'])
        cases[0]['human_ratings']={}
        with self.assertRaises(ValueError): compare({'cases':cases})


class RealtimeAndPacketTests(unittest.IsolatedAsyncioTestCase):
    def test_transcript_order_receipt_scope_and_origin(self):
        from app.ai.realtime import Transcript
        from app.services.voice_capture import seal, verify
        from app.api.voice import same_origin
        from types import SimpleNamespace
        transcript=Transcript()
        for item in ('a','b'):
            transcript.feed({'type':'input_audio_buffer.committed','item_id':item})
        transcript.feed({'type':'conversation.item.input_audio_transcription.completed','item_id':'b','transcript':'Second.'})
        self.assertFalse(transcript.complete())
        transcript.feed({'type':'conversation.item.input_audio_transcription.delta','item_id':'a','delta':'First'})
        self.assertEqual(transcript.text(),'First\nSecond.')
        transcript.feed({'type':'conversation.item.input_audio_transcription.completed','item_id':'a','transcript':'First.'})
        self.assertTrue(transcript.complete());self.assertEqual(transcript.text(),'First.\nSecond.')
        with self.assertRaises(ValueError):
            transcript.feed({'type':'conversation.item.input_audio_transcription.delta','item_id':'c','delta':'x'*8001})
        session=SimpleNamespace(uuid='s1',user_id=1,script={})
        token=seal(session,2,'Hello there.',3000,['a'])
        self.assertEqual(verify(token,session,2)['transcript'],'Hello there.')
        for changed,qid in ((SimpleNamespace(uuid='s2',user_id=1,script={}),2),(SimpleNamespace(uuid='s1',user_id=2,script={}),2),(session,3)):
            with self.assertRaises(HTTPException):verify(token,changed,qid)
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=9999999999):
            with self.assertRaises(HTTPException):verify(token,session,2)
        with self.assertRaises(HTTPException):verify('tampered',session,2)
        for origin,valid in [('http://localhost:8000',True),('https://evil.example',False),('',False),('http://localhost:8000/else',False)]:
            self.assertEqual(same_origin(SimpleNamespace(url=SimpleNamespace(scheme='ws'), headers={'origin':origin,'host':'localhost:8000'})),valid)
        self.assertFalse(same_origin(SimpleNamespace(url=SimpleNamespace(scheme='ws'), headers={'origin':'http://localhost:8000','host':'localhost:8000','sec-fetch-site':'cross-site'})))

    async def test_speech_stream_yields_early_and_never_caches_cancelled_audio(self):
        from app.ai import speech
        class Chunks(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'first'
                yield b'second'
        calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(200,stream=Chunks())
        original=httpx.AsyncClient
        with tempfile.TemporaryDirectory() as directory, patch.object(speech,'ROOT',Path(directory)), \
                patch('app.storage.ROOT',Path(directory)), \
                patch.object(settings,'tts_cache',True), \
                patch('app.ai.speech.httpx.AsyncClient',side_effect=lambda **kw: original(transport=httpx.MockTransport(handle),**kw)):
            cache=speech.stream_cache('Synthetic streaming fixture.','hr','stream-test')
            stream=speech.stream_audio('Synthetic streaming fixture.','hr','stream-test')
            self.assertEqual(await stream.__anext__(),b'first')
            self.assertFalse(cache.exists())
            await stream.aclose()
            self.assertFalse(cache.exists());self.assertFalse(list(cache.parent.glob('*.tmp')))
            self.assertEqual(b''.join([chunk async for chunk in speech.stream_audio('Synthetic streaming fixture.','hr','stream-test')]),b'firstsecond')
            self.assertTrue(cache.exists())
            self.assertEqual(b''.join([chunk async for chunk in speech.stream_audio('Synthetic streaming fixture.','hr','stream-test')]),b'firstsecond')
            self.assertEqual(len(calls),2)

    def test_blind_packets_merge_integrity_and_no_automatic_validation(self):
        from validation.kit import starter,packet,merge,digest
        data=starter()
        self.assertFalse(data['validated']);self.assertTrue(all(not c['human_ratings'] and not c['ai_runs'] for c in data['cases']))
        data['cases'][0]['ai_runs']=[5]*5;data['cases'][0]['human_ratings']={'secret-assessor':2}
        data['cases'][0]['transcript']+=' </script><script>alert(1)</script>'
        output=packet(data,'assessor-a')
        self.assertNotIn('secret-assessor',output);self.assertNotIn('human_ratings',output);self.assertNotIn('ai_runs',output)
        self.assertNotIn('</script><script>alert(1)',output)
        rows=[{'case_id':c['id'],'status':'insufficient','score':None,'quote':'','rationale':'Synthetic test only, not actual human assessment.'} for c in data['cases']]
        rating={'assessor_id':'assessor-a','dataset_hash':digest(data),'personally_rated_independently':True,'ratings':rows}
        merged=merge(data,[rating])
        self.assertFalse(merged['validated']);self.assertIsNone(merged['cases'][0]['human_ratings']['assessor-a'])
        with self.assertRaises(ValueError):merge(merged,[rating])
        for changes in ({'dataset_hash':'wrong'},{'personally_rated_independently':False},{'ratings':rows[:-1]}):
            with self.assertRaises(ValueError):merge(data,[{**rating,**changes}])
        badrows=json.loads(json.dumps(rows));badrows[0].update(status='measured',score=4,quote='Made up evidence')
        with self.assertRaises(ValueError):merge(data,[{**rating,'ratings':badrows}])
        data['level']='senior'
        with self.assertRaises(ValueError):merge(data,[rating])
        data['rubric']+='edited'
        with self.assertRaises(ValueError):packet(data,'assessor-b')

    async def test_assessor_ai_runs_use_no_human_scores_and_keep_integer_ratings(self):
        from validation.kit import starter,run_ai
        data=starter();data['cases']=data['cases'][:1]
        data['cases'][0]['human_ratings']={'private-rater':1}
        evidence=data['cases'][0]['transcript']
        response={'competency_scores':{'communication':{'score':4.0,'evidence':[evidence],'evidence_sufficiency':'sufficient'}}}
        with patch('app.ai.orchestrator.evaluate',AsyncMock(return_value=response)) as evaluate:
            result=await run_ai(data)
        self.assertEqual(evaluate.await_count,5)
        self.assertEqual(result['cases'][0]['ai_runs'],[4]*5)
        self.assertTrue(all(type(score) is int for score in result['cases'][0]['ai_runs']))
        self.assertNotIn('private-rater',json.dumps([call.args for call in evaluate.call_args_list]))
        self.assertFalse(result['validated'])
