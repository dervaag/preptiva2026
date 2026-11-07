"""Account provisioning uses an isolated database and never resets implicitly."""
import test_system

import argparse
import asyncio
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from app.db import SessionLocal
from app.models import User
from app.security import verify_password
from app.security_models import AuthSession
from app.scripts.seed_account import seed_account, run


class AccountSeederTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register

    async def test_create_and_repeat_preserve_one_account_and_existing_profile(self):
        first = await seed_account(' SEED@example.com ', 'Synthetic123', name='Synthetic Account')
        async with SessionLocal() as db:
            user = await db.get(User, first['id'])
            self.assertTrue(verify_password('Synthetic123', user.password_hash))
            self.assertNotEqual(user.password_hash, 'Synthetic123')
            self.assertIsNone(user.gender)
            self.assertIsNone(user.age)
            user.last_cv_text = 'Retained synthetic CV'
            await db.commit()
        second = await seed_account('seed@example.com', 'Synthetic123', name='Ignored replacement')
        self.assertEqual(first['status'], 'created')
        self.assertEqual(second['status'], 'existing')
        self.assertEqual(first['id'], second['id'])
        async with SessionLocal() as db:
            user = await db.get(User, first['id'])
            self.assertEqual(user.name, 'Synthetic Account')
            self.assertEqual(user.last_cv_text, 'Retained synthetic CV')
            self.assertEqual(await db.scalar(select(func.count()).select_from(User).where(
                User.email == 'seed@example.com')), 1)
            self.assertIsNone(await db.get(AuthSession, user.id))

    async def test_different_password_does_not_change_existing_account_or_login(self):
        user_id = (await self.client.get('/api/me')).json()['id']
        result = await seed_account('budi@example.com', 'Different123')
        self.assertEqual(result['status'], 'existing_password_differs')
        self.assertFalse(result['changed'])
        self.assertEqual((await self.client.get('/api/me')).status_code, 200)
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            self.assertTrue(verify_password('test12345', user.password_hash))

    async def test_explicit_password_reset_revokes_only_the_target_login(self):
        await self.register(self.other, 'other@example.com')
        result = await seed_account('budi@example.com', 'Different123', reset_password=True)
        self.assertEqual(result['status'], 'password_reset')
        self.assertTrue(result['sessions_revoked'])
        self.assertEqual((await self.client.get('/api/me')).status_code, 401)
        self.assertEqual((await self.other.get('/api/me')).status_code, 200)
        response = await self.client.post('/api/auth/login', json={
            'email': 'budi@example.com', 'password': 'Different123'})
        self.assertEqual(response.status_code, 200)

    async def test_concurrent_seed_creates_one_account(self):
        results = await asyncio.gather(*(seed_account('race-seed@example.com', 'Synthetic123') for _ in range(2)))
        self.assertEqual(sorted(r['status'] for r in results), ['created', 'existing'])
        self.assertEqual(results[0]['id'], results[1]['id'])

    async def test_validation_error_output_never_echoes_password_and_does_not_open_database(self):
        secret = 'PRIVATE_PASSWORD_MARKER_' * 10
        output = io.StringIO()
        arguments = argparse.Namespace(email='seed@example.com', name='Synthetic', reset_password=False)
        with redirect_stdout(output), patch('app.scripts.seed_account.init_db') as initialize:
            code = await run(arguments, secret)
        self.assertEqual(code, 1)
        initialize.assert_not_called()
        self.assertNotIn(secret, output.getvalue())
        self.assertNotIn('PRIVATE_PASSWORD_MARKER', output.getvalue())


if __name__ == '__main__':
    unittest.main()
