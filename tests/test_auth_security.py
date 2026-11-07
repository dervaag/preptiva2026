"""Authentication regressions against an isolated database, never real accounts."""
import test_system  # Configure the disposable database before importing application modules.

import asyncio
from base64 import b64encode, b64decode
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import User, now
from app.security import hash_password, verify_password
from app.security_models import AuthSession, LoginLimit
from app.services import login_limits
from app.services.auth_sessions import issue_session
from app.services.auth_sessions import resolve_user as actual_resolve_user


def signed_cookie(value):
    return TimestampSigner(settings.secret_key).sign(b64encode(json.dumps(value).encode())).decode()


class AuthSecurityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register

    async def login(self, client=None, password='test12345', email='budi@example.com'):
        return await (client or self.client).post('/api/auth/login', json={'email': email, 'password': password})

    async def expire(self, model=AuthSession, **values):
        async with SessionLocal() as db:
            await db.execute(update(model).values(**values))
            await db.commit()

    async def test_second_browser_rejected_until_first_logs_out(self):
        response = await self.login(self.other)
        self.assertEqual(response.status_code, 409)
        self.assertEqual((await self.client.get('/api/me')).status_code, 200)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        await self.client.post('/api/auth/logout')
        self.assertEqual((await self.login(self.other)).status_code, 200)
        self.assertEqual((await self.client.get('/api/me')).status_code, 401)

    async def test_read_only_authenticated_request_does_not_reissue_the_cookie(self):
        cookie = self.client.cookies.get('isim_session')
        response = await self.client.get('/api/me')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.client.cookies.get('isim_session'), cookie)

    async def test_delayed_expired_cookie_response_cannot_erase_a_new_login(self):
        await self.expire(idle_expires_at=now() - timedelta(seconds=1))
        expired_cookie = self.client.cookies.get('isim_session')
        checked, release = asyncio.Event(), asyncio.Event()
        async def delayed_resolve(request, db, touch=True):
            user = await actual_resolve_user(request, db, touch=touch)
            if user is None:
                checked.set()
                await asyncio.wait_for(release.wait(), 5)
            return user
        with patch('app.deps.resolve_user', side_effect=delayed_resolve):
            stale_request = asyncio.create_task(self.client.get('/api/me'))
            try:
                await asyncio.wait_for(checked.wait(), 5)
                response = await self.login()
                self.assertEqual(response.status_code, 200, response.text)
                fresh_cookie = self.client.cookies.get('isim_session')
                self.assertNotEqual(fresh_cookie, expired_cookie)
            finally:
                release.set()
            expired_response = await asyncio.wait_for(stale_request, 5)
        self.assertEqual(expired_response.status_code, 401)
        self.assertNotIn('set-cookie', expired_response.headers)
        self.assertEqual(self.client.cookies.get('isim_session'), fresh_cookie)
        self.assertEqual((await self.client.get('/api/me')).status_code, 200)

    async def test_login_race_allows_one_session_only(self):
        await self.client.post('/api/auth/logout')
        responses = await asyncio.gather(self.login(self.client), self.login(self.other))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(AuthSession)), 1)

    async def test_independent_processes_share_the_single_login_constraint(self):
        await self.client.post('/api/auth/logout')
        source = '''
import asyncio,json,sys
from pathlib import Path
import httpx
from app.main import app
from app.db import engine
async def main():
    Path(sys.argv[1]).write_text('ready')
    while not Path(sys.argv[2]).exists():await asyncio.sleep(.02)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        response=await client.post('/api/auth/login',json={'email':'budi@example.com','password':'test12345'})
        print(json.dumps({'status':response.status_code}),flush=True)
    await engine.dispose()
asyncio.run(main())
'''
        children = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate = root / 'start'
            try:
                for index in range(2):
                    children.append(await asyncio.create_subprocess_exec(sys.executable, '-c', source,
                        str(root / f'ready{index}'), str(gate),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
                for _ in range(400):
                    if all((root / f'ready{index}').exists() for index in range(2)):
                        break
                    await asyncio.sleep(.025)
                self.assertTrue(all((root / f'ready{index}').exists() for index in range(2)))
                gate.write_text('go')
                statuses = []
                for child in children:
                    output, error = await asyncio.wait_for(child.communicate(), 20)
                    self.assertEqual(child.returncode, 0, error.decode())
                    statuses.append(json.loads(output)['status'])
                self.assertEqual(sorted(statuses), [200, 409])
            finally:
                for child in children:
                    if child.returncode is None:
                        child.kill()
                        await child.wait()

    async def test_cookie_is_revocable_and_old_cookie_cannot_log_out_a_rotated_session(self):
        previous = self.client.cookies.get('isim_session')
        self.assertEqual((await self.login()).status_code, 200)
        replacement = self.client.cookies.get('isim_session')
        self.assertNotEqual(previous, replacement)
        self.other.cookies.set('isim_session', previous)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        self.other.cookies.set('isim_session', previous)
        self.assertEqual((await self.other.post('/api/auth/logout')).status_code, 200)
        self.assertEqual((await self.client.get('/api/me')).status_code, 200)
        await self.client.post('/api/auth/logout')
        self.other.cookies.clear()
        self.other.cookies.set('isim_session', replacement)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)

    async def test_token_hash_only_in_database_and_user_id_cookie_is_not_authority(self):
        payload = json.loads(b64decode(self.client.cookies.get('isim_session').split('.')[0]))
        async with SessionLocal() as db:
            session = await db.scalar(select(AuthSession))
            self.assertNotEqual(session.token_hash, payload['auth_token'])
            self.assertEqual(len(session.token_hash), 64)
        self.other.cookies.set('isim_session', signed_cookie({'user_id': payload['user_id']}))
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        self.other.cookies.clear()
        self.other.cookies.set('isim_session', signed_cookie({**payload, 'user_id': 987654321}))
        response = await self.other.get('/api/me')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'budi@example.com')

    async def test_expired_idle_or_absolute_session_can_never_be_renewed_by_an_api_call(self):
        for field in ('idle_expires_at', 'expires_at'):
            with self.subTest(field=field):
                await self.expire(**{field: now() - timedelta(seconds=1)})
                self.assertEqual((await self.client.get('/api/me')).status_code, 401)
                self.assertEqual((await self.login()).status_code, 200)
        info = (await self.client.get('/api/auth/session')).json()
        self.assertTrue(info['single_session'])
        self.assertEqual(info['idle_timeout_seconds'], 1800)
        self.assertEqual(info['absolute_timeout_seconds'], 43200)
        self.assertNotIn('token', json.dumps(info))

    async def test_five_failed_attempts_lock_account_even_when_requests_race(self):
        await self.client.post('/api/auth/logout')
        responses = await asyncio.gather(*(self.login(self.other, password='wrong12345') for _ in range(6)))
        self.assertEqual(sorted(response.status_code for response in responses), [401, 401, 401, 401, 401, 429])
        blocked = await self.login(self.other)
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers['Retry-After']), 0)
        await self.expire(LoginLimit, expires_at=now() - timedelta(seconds=1))
        self.assertEqual((await self.login(self.other)).status_code, 200)

    async def test_ip_limit_ignores_spoofed_forwarding_and_keys_hide_addresses(self):
        with patch.object(settings, 'auth_login_ip_max_attempts', 5):
            for index in range(5):
                response = await self.other.post('/api/auth/login',
                    json={'email': f'unknown-{index}@example.com', 'password': 'wrong12345'},
                    headers={'X-Forwarded-For': f'203.0.113.{index}'})
                self.assertEqual(response.status_code, 401)
            response = await self.other.post('/api/auth/login',
                json={'email': 'different@example.com', 'password': 'wrong12345'},
                headers={'X-Forwarded-For': '198.51.100.10'})
            self.assertEqual(response.status_code, 429)
        async with SessionLocal() as db:
            keys = (await db.scalars(select(LoginLimit.bucket_hash))).all()
        self.assertTrue(keys)
        self.assertTrue(all(len(key) == 64 and '@' not in key and '.' not in key for key in keys))

    async def test_unknown_account_uses_bcrypt_and_has_same_failure_body(self):
        with patch('app.api.auth.verify_password', return_value=False) as verify:
            missing = await self.login(self.other, email='not-registered@example.com')
            self.assertEqual(verify.call_count, 1)
            self.assertTrue(verify.call_args.args[1].startswith('$2b$'))
        known = await self.login(self.other, password='wrong12345')
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json(), known.json())

    async def test_successful_login_resets_account_attempts_but_not_ip_budget(self):
        await self.client.post('/api/auth/logout')
        for _ in range(4):
            self.assertEqual((await self.login(password='wrong12345')).status_code, 401)
        self.assertEqual((await self.login()).status_code, 200)
        async with SessionLocal() as db:
            self.assertIsNone(await db.get(LoginLimit, login_limits.bucket_key('login-account', 'budi@example.com')))
            self.assertEqual((await db.get(LoginLimit, login_limits.bucket_key('login-ip', '127.0.0.1'))).attempts, 5)

    async def test_password_change_requires_current_password_and_revokes_cookie_replay(self):
        cookie = self.client.cookies.get('isim_session')
        invalid = await self.client.post('/api/auth/password', json={
            'current_password': 'wrong-current1', 'new_password': 'replacement123', 'password_confirm': 'replacement123'})
        self.assertEqual(invalid.status_code, 403)
        self.assertEqual((await self.client.get('/api/me')).status_code, 200)
        changed = await self.client.post('/api/auth/password', json={
            'current_password': 'test12345', 'new_password': 'replacement123', 'password_confirm': 'replacement123'})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertTrue(changed.json()['reauthenticate'])
        self.other.cookies.set('isim_session', cookie)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        self.assertEqual((await self.login(password='test12345')).status_code, 401)
        self.assertEqual((await self.login(password='replacement123')).status_code, 200)
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            self.assertEqual(user.name, 'Budi Santoso')
            self.assertTrue(verify_password('replacement123', user.password_hash))

    async def test_old_password_verified_before_concurrent_change_cannot_issue_a_new_session(self):
        if test_system.engine.dialect.name != 'sqlite':
            self.skipTest('SQLite ignores FOR UPDATE; PostgreSQL ordering is tested separately.')
        await self.client.post('/api/auth/logout')
        entered, release = threading.Event(), threading.Event()
        def delayed_verify(password, hashed):
            result = verify_password(password, hashed)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test verification barrier expired')
            return result
        replacement = hash_password('replacement123')
        with patch('app.api.auth.verify_password', side_effect=delayed_verify):
            pending = asyncio.create_task(self.login(self.other))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                async with SessionLocal() as db:
                    await db.execute(update(User).where(User.email == 'budi@example.com').values(password_hash=replacement))
                    await db.commit()
            finally:
                release.set()
            response = await pending
        self.assertEqual(response.status_code, 403, response.text)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(AuthSession)), 0)
        self.assertEqual((await self.login(self.other, password='replacement123')).status_code, 200)

    async def test_stale_verified_user_cannot_issue_session_after_credential_change(self):
        replacement = hash_password('replacement123')
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            self.assertTrue(verify_password('test12345', user.password_hash))
            async with SessionLocal() as other:
                await other.execute(update(User).where(User.id == user.id).values(password_hash=replacement))
                await other.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
                await other.commit()
            with self.assertRaises(test_system.HTTPException) as caught:
                await issue_session(SimpleNamespace(session={}), user, db)
            self.assertEqual(caught.exception.status_code, 403)
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(AuthSession)), 0)

    async def test_postgres_orders_credential_change_after_locked_login_and_revokes_its_token(self):
        if test_system.engine.dialect.name != 'postgresql':
            self.skipTest('PostgreSQL row-lock ordering; SQLite credential race is tested separately.')
        await self.client.post('/api/auth/logout')
        entered, release = threading.Event(), threading.Event()
        def delayed_verify(password, hashed):
            result = verify_password(password, hashed)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test verification barrier expired')
            return result
        replacement = hash_password('replacement123')
        async def change_credentials(lock_timeout=False):
            async with SessionLocal() as db:
                user_id = await db.scalar(select(User.id).where(User.email == 'budi@example.com'))
                if lock_timeout:
                    await db.execute(text("SET LOCAL lock_timeout = '150ms'"))
                await db.execute(update(User).where(User.id == user_id).values(password_hash=replacement))
                await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
                await db.commit()
        with patch('app.api.auth.verify_password', side_effect=delayed_verify):
            pending = asyncio.create_task(self.login(self.other))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                # The database must report a real lock wait, not merely a task
                # that has not yet been scheduled. A bounded lock timeout avoids
                # waiting for the login barrier from the competing transaction.
                with self.assertRaises(DBAPIError) as caught:
                    await change_credentials(lock_timeout=True)
                self.assertEqual(caught.exception.orig.sqlstate, '55P03')
            finally:
                release.set()
            self.assertEqual((await asyncio.wait_for(pending, 5)).status_code, 200)
        await asyncio.wait_for(change_credentials(), 5)
        self.assertEqual((await self.other.get('/api/me')).status_code, 401)
        self.assertEqual((await self.login(self.other, password='test12345')).status_code, 401)
        self.assertEqual((await self.login(self.other, password='replacement123')).status_code, 200)

    async def test_high_risk_password_guessing_is_bounded_without_changing_credentials(self):
        private = 'SENSITIVE-WRONG-CURRENT1'
        with self.assertLogs('preptiva', level='INFO') as captured:
            statuses = []
            for _ in range(6):
                response = await self.client.post('/api/auth/password', json={
                    'current_password': private, 'new_password': 'replacement123', 'password_confirm': 'replacement123'})
                statuses.append(response.status_code)
        self.assertEqual(statuses, [403, 403, 403, 403, 403, 429])
        self.assertNotIn(private, '\n'.join(captured.output))
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == 'budi@example.com'))
            self.assertTrue(verify_password('test12345', user.password_hash))

    async def test_utf8_byte_limit_and_validation_never_echo_credentials(self):
        secret = 'PRIVATE-INPUT-' + 'é' * 35
        response = await self.login(self.other, password=secret)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(secret, response.text)
        response = await self.client.post('/api/auth/password', json={
            'current_password': 'test12345', 'new_password': 'PRIVATE-NO-DIGITS', 'password_confirm': 'PRIVATE-NO-DIGITS'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('PRIVATE-NO-DIGITS', response.text)
        self.assertNotIn('test12345', response.text)

    async def test_account_switch_releases_previous_browser_session(self):
        self.assertEqual((await self.register(self.client, 'another@example.com')).status_code, 200)
        self.assertEqual((await self.login(self.other)).status_code, 200)
        self.assertEqual((await self.client.get('/api/me')).json()['email'], 'another@example.com')
        self.assertEqual((await self.other.get('/api/me')).json()['email'], 'budi@example.com')


if __name__ == '__main__':
    unittest.main()
