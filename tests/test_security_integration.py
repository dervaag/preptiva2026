"""Security boundaries tested with temporary storage and synthetic providers."""
import test_system

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from starlette.websockets import WebSocket

from app import storage
from app.ai import speech
from app.config import settings
from app.db import engine
from app.main import app


class BrowserSecurityBoundaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register
    form = test_system.SystemTests.form
    create = test_system.SystemTests.create
    ready_session = test_system.SystemTests.ready_session

    async def test_websocket_origin_uses_https_policy_and_rejects_cross_site(self):
        from app.api.voice import same_origin
        async def unused(*args):
            raise AssertionError('Origin validation must not start websocket transport')
        def socket(origin, site='same-origin'):
            return WebSocket({'type': 'websocket', 'scheme': 'ws', 'path': '/',
                'query_string': b'', 'headers': [(b'host', b'testserver'),
                    (b'origin', origin.encode()), (b'sec-fetch-site', site.encode())]}, unused, unused)
        with patch.object(settings, 'cookie_secure', True), patch.object(settings, 'public_origin', ''):
            self.assertTrue(same_origin(socket('https://testserver')))
            for origin in ('http://testserver', 'https://user@testserver', 'https://testserver/path', 'null'):
                self.assertFalse(same_origin(socket(origin)))
            self.assertFalse(same_origin(socket('https://testserver', 'cross-site')))
        with patch.object(settings, 'cookie_secure', False), patch.object(settings, 'public_origin', ''):
            self.assertTrue(same_origin(socket('http://testserver')))

    async def test_origin_requires_exact_scheme_host_and_no_credential_or_path(self):
        for origin in ('https://testserver', 'http://testserver.evil.test', 'http://user@testserver',
                       'http://testserver/path', 'http://testserver?x=1', 'http://testserver#x', 'null', ''):
            with self.subTest(origin=origin):
                response = await self.client.patch('/api/profile', data={'name': 'Should not save'},
                    headers={'Origin': origin})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.headers['x-frame-options'], 'DENY')
        for headers in ({'Referer': 'http://evil.test/profile'}, {'Sec-Fetch-Site': 'same-site'},
                        {'Sec-Fetch-Site': 'cross-site', 'Origin': 'http://testserver'}):
            self.assertEqual((await self.client.patch('/api/profile', data={'name': 'Should not save'},
                headers=headers)).status_code, 403)
        for headers in ({'Origin': 'http://testserver'}, {'Referer': 'http://testserver/profile'},
                        {'Sec-Fetch-Site': 'same-origin'}):
            self.assertEqual((await self.client.patch('/api/profile', data={'name': 'Allowed name'},
                headers=headers)).status_code, 200)

    async def test_private_html_and_api_are_not_cacheable_and_cookie_replay_cannot_render_profile(self):
        old_cookie = self.client.cookies.get('isim_session')
        for path in ('/profile', '/dashboard', '/api/profile', '/api/privacy/policy'):
            response = await self.client.get(path)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.headers['x-frame-options'], 'DENY')
            self.assertIn("frame-ancestors 'none'", response.headers['content-security-policy'])
        await self.client.post('/api/auth/logout')
        self.other.cookies.set('isim_session', old_cookie)
        response = await self.other.get('/profile')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/login')

    async def test_email_change_requires_current_password(self):
        for fields, status in (({'email': 'new@example.com'}, 403),
                               ({'email': 'new@example.com', 'current_password': 'wrong123'}, 403)):
            self.assertEqual((await self.client.patch('/api/profile', data=fields)).status_code, status)
        self.assertEqual((await self.client.get('/api/me')).json()['email'], 'budi@example.com')
        self.assertEqual((await self.client.patch('/api/profile', data={
            'email': 'new@example.com', 'current_password': 'test12345'})).status_code, 200)

    async def test_unexpected_request_error_does_not_log_private_exception_message(self):
        marker = 'PRIVATE-CREDENTIAL-OR-CV-IN-EXCEPTION'
        with patch('app.main.resolve_user', side_effect=ValueError(marker)), \
                self.assertLogs('preptiva', level='INFO') as captured:
            response = await self.client.get('/profile')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(marker, response.text)
        self.assertNotIn(marker, '\n'.join(captured.output))
        self.assertIn('request_failed', '\n'.join(captured.output))

    async def test_body_limit_applies_before_parsing_and_to_chunked_input(self):
        async def chunks():
            yield b'{"password":"' + b'x' * 60
            yield b'x' * 60 + b'"}'
        with patch.object(settings, 'max_request_bytes', 100):
            declared = await self.other.post('/api/auth/login', content=b'{}',
                headers={'Content-Length': '101', 'Content-Type': 'application/json'})
            streamed = await self.other.post('/api/auth/login', content=chunks(),
                headers={'Content-Type': 'application/json'})
        self.assertEqual(declared.status_code, 413)
        self.assertEqual(streamed.status_code, 413, streamed.text)
        self.assertNotIn('xxxx', streamed.text)

    async def test_revoked_login_cookie_cannot_open_paid_realtime_connection(self):
        sid, _, state = await self.ready_session()
        await self.client.post(f'/api/sessions/{sid}/start')
        cookie = self.client.cookies.get('isim_session')
        await self.client.post('/api/auth/logout')
        # TestClient owns another event loop; close pooled test connections first.
        await engine.dispose()
        with patch.object(settings, 'realtime_voice_enabled', True), \
                patch('app.api.voice.realtime.connection', side_effect=AssertionError('Must reject before provider')):
            with TestClient(app) as client:
                client.cookies.set('isim_session', cookie)
                with self.assertRaises(WebSocketDisconnect) as caught:
                    with client.websocket_connect(f'/api/sessions/{sid}/voice/{state["current_turn"]["id"]}',
                            headers={'Origin': 'http://testserver'}):
                        pass
                self.assertEqual(caught.exception.code, 1008)


class ScopedSpeechPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_text_has_separate_caches_and_deletion_preserves_other_session(self):
        client_type = httpx.AsyncClient
        calls = []
        def response(request):
            calls.append(request)
            return httpx.Response(200, content=b'synthetic-mp3')
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'ROOT', Path(folder)), \
                patch.object(settings, 'tts_cache', True), patch('app.ai.speech.httpx.AsyncClient',
                    side_effect=lambda **kwargs: client_type(transport=httpx.MockTransport(response))):
            await speech.synthesize('Personalized synthetic question.', 'hr', 'session-a', 'first.mp3')
            await speech.synthesize('Personalized synthetic question.', 'hr', 'session-b', 'first.mp3')
            storage.mark_session_deleted('session-a')
            await speech.synthesize('Personalized synthetic question.', 'hr', 'session-b', 'cached.mp3')
            self.assertEqual(len(calls), 2)
            self.assertEqual(storage.read_session_audio('session-b', 'cached.mp3'), b'synthetic-mp3')
            self.assertFalse((Path(folder) / 'data/audio/session-a').exists())
            self.assertFalse((Path(folder) / 'data/tts_cache').exists())

    async def test_inflight_synthesis_cannot_recreate_audio_after_deletion(self):
        started, finish = asyncio.Event(), asyncio.Event()
        client_type = httpx.AsyncClient
        async def response(request):
            started.set()
            await finish.wait()
            return httpx.Response(200, content=b'late-synthetic-audio')
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'ROOT', Path(folder)), \
                patch.object(settings, 'tts_cache', True), patch('app.ai.speech.httpx.AsyncClient',
                    side_effect=lambda **kwargs: client_type(transport=httpx.MockTransport(response))):
            task = asyncio.create_task(speech.synthesize('Synthetic question.', 'hr', 'session-late', 'q1.mp3'))
            await started.wait()
            storage.mark_session_deleted('session-late')
            finish.set()
            with self.assertRaises(storage.SessionStorageDeleted):
                await task
            self.assertFalse((Path(folder) / 'data/audio/session-late').exists())

    async def test_stream_stops_after_deletion_and_never_commits_partial_cache(self):
        class Chunks(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'first'
                yield b'second'
        client_type = httpx.AsyncClient
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'ROOT', Path(folder)), \
                patch.object(settings, 'tts_cache', True), patch('app.ai.speech.httpx.AsyncClient',
                    side_effect=lambda **kwargs: client_type(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, stream=Chunks())))):
            stream = speech.stream_audio('Synthetic question.', 'hr', 'session-stream')
            self.assertEqual(await stream.__anext__(), b'first')
            storage.mark_session_deleted('session-stream')
            with self.assertRaises(StopAsyncIteration):
                await stream.__anext__()
            self.assertFalse((Path(folder) / 'data/audio/session-stream').exists())


if __name__ == '__main__':
    unittest.main()
