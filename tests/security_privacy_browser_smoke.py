"""Isolated browser contract tests for security/privacy UI; no DB or provider writes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_system  # Isolate application configuration before rendering templates.

import argparse
import json
from types import SimpleNamespace
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from starlette.requests import Request

from app.main import templates
from app.config import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts-dir', type=Path)
    args = parser.parse_args()
    if args.artifacts_dir:
        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    origin = 'https://privacy-ui.example.test'
    secret = 'SyntheticPassword123'
    profile = {'id': 100, 'name': 'Privacy Candidate', 'email': 'privacy@example.test', 'gender': 'female',
               'age': 28, 'has_cv': True, 'cv_text': 'Synthetic candidate project experience. ' * 10}
    items = [{'id': f'synthetic-session-{index}', 'job_role': role, 'company': 'Sample company',
              'interviewer': 'hr', 'level': 'middle', 'status': 'done', 'total_score': 3,
              'created_at': '2026-11-01T10:00:00Z', 'finished_at': '2026-11-01T11:00:00Z'}
             for index, role in enumerate(('Designer <script>bad()</script>', 'Analyst', 'Engineer'), 1)]
    receipts, mutations, errors = [], [], []
    delayed_background = []
    hold_background = False

    def receipt(scope, pending=False, sessions=0):
        value = {'id': f'synthetic-receipt-{len(receipts)+1}', 'scope': scope,
                 'status': 'pending_files' if pending else 'complete', 'database_deleted': True,
                 'created_at': '2026-11-07T00:00:00Z', 'completed_at': None if pending else '2026-11-07T00:00:01Z',
                 'counts': {'sessions': sessions, 'answers': sessions, 'questions': sessions, 'files': 0},
                 'files_pending': 1 if pending else 0}
        receipts.append(value)
        return value

    def render(kind):
        request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'query_string': b'',
                           'headers': [(b'cookie', b'preptiva_ui_language=id')]})
        user = None if kind == 'login' else SimpleNamespace(**profile, last_cv_text=profile['cv_text'])
        return templates.env.get_template('app.html').render(request=request, page=kind, sid='', user=user,
                                                             configured=True, development=False)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        try:
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)

            def route_request(route):
                nonlocal items
                request = route.request
                parsed = urlsplit(request.url)
                if parsed.netloc != urlsplit(origin).netloc:
                    route.abort(); return
                path = parsed.path
                if path.startswith('/static/'):
                    target = (ROOT / 'app' / path.lstrip('/')).resolve()
                    if not target.is_relative_to((ROOT / 'app/static').resolve()) or not target.is_file():
                        route.fulfill(status=404); return
                    content_type = {'.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png'}.get(target.suffix, 'application/octet-stream')
                    route.fulfill(body=target.read_bytes(), content_type=content_type); return
                if request.method == 'GET':
                    if path in ('/profile', '/riwayat', '/login'):
                        route.fulfill(body=render({'/profile':'profile', '/riwayat':'history', '/login':'login'}[path]), content_type='text/html'); return
                    if hold_background and path in ('/api/privacy/policy','/api/privacy/receipts','/api/auth/session'):
                        delayed_background.append(route); return
                    response = {'/api/profile': profile, '/api/sessions': {'items': items},
                                '/api/privacy/receipts': {'items': receipts},
                                '/api/privacy/policy': {'audio_days': 7, 'history_days': 90, 'receipt_days': 30,
                                                        'retention_enabled': True, 'cv_retention':'until_deleted'},
                                '/api/auth/session': {'single_session': True, 'idle_timeout_seconds':1800,
                                                      'absolute_timeout_seconds':43200}}.get(path)
                    if response is not None:
                        route.fulfill(json=response); return
                if request.method == 'PATCH' and path == '/api/profile':
                    body = request.post_data or ''
                    mutations.append((request.method, path))
                    if secret not in body:
                        route.fulfill(status=403, json={'detail':'Password saat ini tidak sesuai.'}); return
                    profile['email'] = 'changed@example.test'
                    route.fulfill(json=profile); return
                if request.method in ('DELETE', 'POST'):
                    body = request.post_data_json
                    mutations.append((request.method, path))
                    if body.get('password', body.get('current_password')) != secret:
                        route.fulfill(status=403, json={'detail':'Password saat ini tidak sesuai.'}); return
                    if path == '/api/auth/password':
                        assert body['new_password'] == body['password_confirm']
                        route.fulfill(json={'ok':True, 'reauthenticate':True}); return
                    if path == '/api/profile/cv':
                        assert body['confirmation'] == 'HAPUS CV'
                        profile.update(has_cv=False, cv_text='')
                        route.fulfill(json={**profile, 'receipt':receipt('saved_cv')}); return
                    if path == '/api/profile':
                        assert body['confirmation'] == 'HAPUS AKUN'
                        route.fulfill(json={'receipt':receipt('account')}); return
                    if path == '/api/sessions':
                        assert body['confirmation'] == 'HAPUS RIWAYAT'
                        value = receipt('history', sessions=len(items)); items=[]
                        route.fulfill(json={'receipt':value}); return
                    if path.startswith('/api/sessions/'):
                        assert body['confirmation'] == 'HAPUS'
                        sid = path.rsplit('/',1)[-1]
                        assert any(item['id']==sid for item in items)
                        items=[item for item in items if item['id']!=sid]
                        route.fulfill(json={'receipt':receipt('session', pending=True, sessions=1)}); return
                raise AssertionError(f'Unexpected request: {request.method} {path}')

            context.route('**/*', route_request)
            page = context.new_page()
            page.set_default_timeout(5000)
            page.add_init_script("localStorage.setItem('preptiva-ui-language','id')")
            page.on('pageerror', lambda error: errors.append(str(error)))

            def check_layout(label):
                for width in (390,768,1440):
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (label,width)
                if args.artifacts_dir:
                    if label == 'profile-security':
                        page.locator('#profile-security').scroll_into_view_if_needed()
                    elif label == 'account-deletion-receipt':
                        page.locator('#profile-account-deleted').scroll_into_view_if_needed()
                    else:
                        page.evaluate('window.scrollTo(0,0)')
                    page.screenshot(path=str(args.artifacts_dir / (label+'.png')))

            def download(target):
                with page.expect_download() as event:
                    page.locator(target).get_by_role('button',name='Unduh tanda terima',exact=True).click()
                value=json.loads(Path(event.value.path()).read_text())
                assert secret not in json.dumps(value)
                return value

            page.goto(origin+'/profile')
            expect(page.locator('#profile-retention-policy')).to_contain_text('7 hari')
            expect(page.locator('#profile-retention-policy')).to_contain_text('90 hari')
            expect(page.locator('#profile-session-info')).to_contain_text('30 menit')
            check_layout('profile-security')
            page.locator('#profile-email').fill('changed@example.test')
            expect(page.locator('#profile-email-password-field')).to_be_visible()
            before=len(mutations)
            page.locator('#profile-personal-form [type=submit]').click()
            assert len(mutations)==before
            page.locator('#profile-email-password').fill(secret)
            page.locator('#profile-personal-form [type=submit]').click()
            expect(page.locator('#profile-email-password-field')).to_be_hidden()
            expect(page.locator('#profile-email-password')).to_have_value('')

            page.locator('#profile-delete-cv').click()
            page.locator('#profile-delete-form [name=password]').fill(secret)
            page.locator('#profile-cancel-delete').click()
            expect(page.locator('#profile-delete-form [name=password]')).to_have_value('')
            page.locator('#profile-delete-cv').click()
            page.locator('#profile-delete-form [name=password]').fill(secret)
            page.locator('#profile-delete-form [name=confirmation]').fill('WRONG')
            before=len(mutations)
            page.locator('#profile-confirm-delete').click()
            assert len(mutations)==before
            page.locator('#profile-delete-form [name=confirmation]').fill('HAPUS CV')
            page.locator('#profile-delete-form [name=password]').fill('wrong-password')
            page.locator('#profile-confirm-delete').click()
            expect(page.locator('#profile-delete-error')).to_be_visible()
            expect(page.locator('#profile-delete-cv')).to_be_enabled()
            expect(page.locator('#profile-delete-form [name=password]')).to_have_value('')
            page.locator('#profile-delete-form [name=password]').fill(secret)
            page.locator('#profile-confirm-delete').click()
            expect(page.locator('#profile-delete-dialog')).not_to_be_visible()
            expect(page.locator('[name=cv_text]')).to_have_count(0)
            expect(page.locator('#profile-delete-cv')).to_be_disabled()
            assert download('#profile-cv-receipt')['scope']=='saved_cv'
            page.locator('#account-menu > summary').click()
            page.locator('[data-language-toggle]').click()
            page.keyboard.press('Escape')
            expect(page.locator('#profile-security')).to_contain_text('Account security')
            expect(page.locator('#profile-retention-policy')).to_contain_text('7 days')
            page.locator('#account-menu > summary').click()
            page.locator('[data-language-toggle]').click()
            page.keyboard.press('Escape')

            page.goto(origin+'/riwayat')
            expect(page.locator('#history-list .ws-session-row')).to_have_count(3)
            assert page.locator('#history-list script').count()==0
            assert page.locator('#history-list a button').count()==0
            check_layout('history-security')
            page.locator('[data-delete-session="synthetic-session-1"]').click()
            expect(page.locator('#history-delete-target')).to_have_text('Designer <script>bad()</script>')
            page.locator('#history-delete-form [name=password]').fill(secret)
            page.locator('#history-delete-form [name=confirmation]').fill('HAPUS')
            page.locator('#history-delete-confirm').click()
            expect(page.locator('#history-list .ws-session-row')).to_have_count(2)
            expect(page.locator('#history-delete-receipt')).to_contain_text('Penghapusan berkas masih diproses.')
            assert download('#history-delete-receipt')['status']=='pending_files'
            page.locator('#history-search').fill('Engineer')
            expect(page.locator('#history-list .ws-session-row')).to_have_count(1)
            page.locator('#history-delete-all').click()
            expect(page.locator('#history-delete-description')).to_contain_text('tidak terlihat karena filter')
            page.locator('#history-delete-form [name=password]').fill(secret)
            page.locator('#history-delete-form [name=confirmation]').fill('HAPUS RIWAYAT')
            page.locator('#history-delete-confirm').click()
            expect(page.locator('#history-list .ws-session-row')).to_have_count(0)
            expect(page.locator('#history-delete-all')).to_be_disabled()
            assert download('#history-delete-receipt')['counts']['sessions']==2

            page.goto(origin+'/profile')
            password_form=page.locator('#profile-password-form')
            password_form.locator('[name=current_password]').fill(secret)
            password_form.locator('[name=new_password]').fill('NewSyntheticPassword123')
            password_form.locator('[name=password_confirm]').fill('Mismatch123')
            before=len(mutations)
            password_form.locator('[type=submit]').click()
            assert len(mutations)==before
            password_form.locator('[name=password_confirm]').fill('NewSyntheticPassword123')
            password_form.locator('[type=submit]').click()
            page.wait_for_url(origin+'/login')

            hold_background = True
            page.goto(origin+'/profile')
            page.locator('#profile-delete-account').click()
            page.locator('#profile-account-delete-form [name=password]').fill(secret)
            page.locator('#profile-account-delete-form [name=confirmation]').fill('HAPUS AKUN')
            page.locator('#profile-account-confirm').click()
            expect(page.locator('#profile-account-deleted')).to_be_visible()
            expect(page.locator('#profile-layout')).to_be_hidden()
            assert delayed_background
            for delayed in delayed_background:
                delayed.fulfill(status=401,json={'detail':'Silakan masuk terlebih dahulu.'})
            page.wait_for_timeout(100)  # Let late responses dispatch if requests were not aborted.
            assert page.url==origin+'/profile'
            assert download('#profile-account-receipt')['scope']=='account'
            check_layout('account-deletion-receipt')
            assert secret not in page.evaluate('JSON.stringify(localStorage)')
            assert not errors, errors
            report={'ok':True,'backend':'mocked contract','paid_api_calls':False,
                    'email_reauthentication':True,'cv_confirmation_and_receipt':True,'password_change':True,
                    'single_and_bulk_history_delete':True,'pending_files_disclosed':True,
                    'account_receipt_before_navigation':True,'no_password_storage':True,
                    'late_status_request_cannot_hide_account_receipt':True,
                    'languages':['id','en'],'viewport_widths':[390,768,1440]}
            if args.artifacts_dir:
                (args.artifacts_dir/'security-privacy-ui.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report))
        finally:
            browser.close()


if __name__=='__main__':
    main()
