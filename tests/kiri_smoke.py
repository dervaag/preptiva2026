"""Verify a running Kiri stack with trusted HTTPS, a temporary account and a no-op job.

Requires Chrome and Playwright. Does not call AI providers. Deletes only its own test account.
Run: .venv/bin/python tests/kiri_smoke.py
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import uuid
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://preptiva.kiri.local'
COMPOSE = ['docker','--context','kiri','compose','--project-name','preptiva','--env-file','.env',
           '--env-file','.env.kiri','-f','compose.kiri.yaml']


def container_python(source, service='web'):
    result = subprocess.run(COMPOSE + ['exec','-T',service,'python','-c',source],cwd=ROOT,
                            capture_output=True,text=True,timeout=45)
    if result.returncode:
        # Container errors can embed environment values: do not echo stderr.
        raise RuntimeError('Pemeriksaan internal container gagal; output mentah tidak dicetak.')
    return result.stdout.strip()


def main(url=URL):
    email = f'kiri-check-{uuid.uuid4().hex}@example.com'
    password = secrets.token_hex(16)+'A1'
    report = {'url':url,'ok':False,'paid_api_calls':False}
    artifact_prefix = 'kiri' if url == URL else 'kiri-public'
    created_id = None
    browser = None
    artifacts = ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome',headless=True)
            context = browser.new_context(viewport={'width':1440,'height':1000})
            page = context.new_page()
            page_errors = []
            page.on('pageerror',lambda error: page_errors.append(str(error)))
            page.goto(url+'/login')  # Default TLS validation stays enabled.
            if page.title() == 'You are about to visit a shared site':
                page.get_by_text('Continue to site', exact=True).click()
                page.wait_for_selector('[name=email]')
                report['kiri_share_confirmation'] = True
            def get(path):
                # Use Chrome's trusted system CA store, not Playwright's Node API client.
                return page.evaluate('''async path => {
                    const response = await fetch(path);
                    return {status: response.status, data: await response.json()};
                }''', path)
            report['trusted_https'] = page.evaluate('window.isSecureContext')
            report['media_api_available'] = page.evaluate("typeof navigator.mediaDevices?.getUserMedia === 'function'")
            assert report['trusted_https'] and report['media_api_available']
            health = get('/health')
            assert health['status'] == 200
            report['health'] = health['data']
            assert report['health']['db'] and report['health']['redis']
            assert get('/dev-login')['status'] == 404
            assert get('/api/me')['status'] == 401
            page.screenshot(path=str(artifacts/(artifact_prefix+'-login.png')),full_page=True)
            page.goto(url+'/register')
            page.locator('[name=name]').fill('Verifikasi Kiri')
            page.locator('[name=email]').fill(email)
            page.locator('[name=password]').fill(password)
            page.locator('[name=password_confirm]').fill(password)
            page.locator('[name=age]').fill('28')
            page.locator('[name=agree]').check()
            page.get_by_role('button',name='Buat akun').click()
            page.wait_for_url('**/dashboard')
            created_id = get('/api/me')['data']['id']
            cookies = [c for c in context.cookies() if c['name']=='isim_session']
            assert len(cookies)==1 and cookies[0]['secure'] and cookies[0]['httpOnly']
            report['secure_session_cookie'] = True
            page.wait_for_function("document.querySelector('#stat-total').textContent === '0'")
            page.goto(url+'/simulasi/baru')
            assert page.locator('#session-form').is_visible()
            page.locator('#interview-mode').select_option('panel')
            assert page.locator('#panel-personas').is_visible()
            assert page.locator('[name=panel]:checked').count() == 2
            page.locator('[name=career_stage]').select_option('fresh_graduate')
            report['panel_and_candidate_background_form'] = True
            page.locator('#logout').click()
            page.wait_for_url('**/login')
            assert get('/api/me')['status'] == 401
            page.locator('[name=email]').fill(email)
            page.locator('[name=password]').fill(password)
            page.get_by_role('button',name='Masuk ke workspace').click()
            page.wait_for_url('**/dashboard')
            assert get('/api/me')['data']['id'] == created_id
            assert not page_errors, 'Kesalahan JavaScript pada browser'
            report['registration_login_logout'] = True
            browser.close()
        output = container_python('''
import asyncio
from uuid import uuid4
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings
async def main():
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        job = await pool.enqueue_job('prepare_session', -1, _job_id='kiri-check-' + uuid4().hex)
        assert job is not None
        await job.result(timeout=25, poll_delay=.25)
        print('worker-ok')
    finally:
        await pool.aclose()
asyncio.run(main())
''')
        assert output == 'worker-ok'
        report['redis_worker_job'] = True
        probe = '/app/data/.kiri-check-' + uuid.uuid4().hex
        try:
            container_python(f'from pathlib import Path; Path({probe!r}).write_text("from-web")')
            container_python(f'from pathlib import Path; p=Path({probe!r}); assert p.read_text()=="from-web"; p.write_text("from-worker")',service='worker')
            container_python(f'from pathlib import Path; assert Path({probe!r}).read_text()=="from-worker"')
            report['shared_audio_volume_writable'] = True
        finally:
            container_python(f'from pathlib import Path; Path({probe!r}).unlink(missing_ok=True)')
        report['ok'] = True
    finally:
        # This account was created by this check and has no interview sessions.
        # Use its unique random email even if the browser failed before returning its ID.
        try:
            cleanup = '''
import asyncio
from sqlalchemy import select, delete, func
from app.db import SessionLocal, engine
from app.models import User, InterviewSession
async def main():
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == EMAIL))
        if user:
            count = await db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.user_id == user.id))
            assert count == 0, 'Test account has sessions; cleanup stopped'
            await db.execute(delete(User).where(User.id == user.id, User.email == EMAIL))
            await db.commit()
    await engine.dispose()
    print('cleanup-ok')
asyncio.run(main())
'''.replace('EMAIL',repr(email))
            report['temporary_account_removed'] = container_python(cleanup) == 'cleanup-ok'
        finally:
            (artifacts/(artifact_prefix+'-smoke.json')).write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=URL, help='HTTPS origin; defaults to local Kiri')
    args = parser.parse_args()
    main(args.url.rstrip('/'))
