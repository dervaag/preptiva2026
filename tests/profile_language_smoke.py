"""Isolated Chrome profile and UI-language checks; no real users or provider calls."""
import argparse
import asyncio
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
import browser_smoke as fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    asyncio.run(fixture.seed())
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    server = fixture.uvicorn.Server(fixture.uvicorn.Config(
        fixture.app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        if not server.started:
            raise RuntimeError('Isolated profile server did not start.')
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width':1440, 'height':1000})
            errors, unexpected_sessions = [], []

            def local_only(route):
                request = route.request
                if urlsplit(request.url).netloc != urlsplit(base).netloc:
                    route.abort()
                elif urlsplit(request.url).path.startswith('/api/sessions') and request.method != 'GET':
                    unexpected_sessions.append(request.url)
                    route.abort()
                else:
                    route.continue_()

            context.route('**/*', local_only)
            page = context.new_page()
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script('window.__profileXss = false')

            def language(value):
                expect(page.locator('html')).to_have_attribute('lang', value)
                assert page.evaluate('window.PreptivaI18n.language') == value
                assert page.evaluate("localStorage.getItem('preptiva-ui-language')") == value
                assert next(cookie['value'] for cookie in context.cookies()
                            if cookie['name'] == 'preptiva_ui_language') == value

            def toggle(value):
                page.locator('[data-language-toggle]').click()
                language(value)
                expect(page.locator('[data-language-label]')).to_have_text(value.upper())

            def profile():
                response = context.request.get(base + '/api/profile')
                assert response.status == 200
                return response.json()

            def save_personal():
                with page.expect_response(lambda response: response.url.endswith('/api/profile')
                                          and response.request.method == 'PATCH') as response:
                    page.locator('#profile-personal-form [type=submit]').click()
                assert response.value.status == 200
                expect(page.locator('#profile-personal-form')).not_to_have_attribute('aria-busy', 'true')

            def names_equal(name):
                for element in page.locator('[data-account-name]').all():
                    expect(element).to_have_text(name)

            def responsive(label):
                page.evaluate('document.fonts.ready')
                for width in (390, 768, 1440):
                    page.set_viewport_size({'width':width, 'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (
                        f'{label} overflows at {width}px')
                    if args.screenshots_dir:
                        args.screenshots_dir.mkdir(parents=True, exist_ok=True)
                        page.evaluate('window.scrollTo(0, 0)')
                        page.evaluate('new Promise(requestAnimationFrame)')
                        page.screenshot(path=str(args.screenshots_dir / f'{label}-{width}.png'), animations='disabled')

            page.goto(base + '/login')
            language('en')
            expect(page.locator('#auth-title')).to_have_text('Welcome back.')
            # Auth has no visible toggle; its supported language URL sets the preference.
            page.goto(base + '/login?lang=id')
            language('id')
            expect(page.locator('#auth-title')).to_have_text('Selamat datang kembali.')
            page.locator('[name=email]').fill('demo@interview.local')
            page.locator('[name=password]').fill('demo1234')
            page.locator('#auth-form [type=submit]').click()
            page.wait_for_url('**/dashboard')
            language('id')
            page.locator('#account-menu > summary').click()
            page.locator('#account-menu a[href="/profile"]').click()
            page.wait_for_url('**/profile')
            expect(page.locator('h1')).to_have_text('Profil saya')
            expect(page.locator('#profile-delete-cv')).to_be_disabled()

            markup_name = '<img src=x onerror="window.__profileXss=true">'
            email = 'profile-language@example.com'
            page.locator('#profile-name').fill(markup_name)
            page.locator('#profile-email').fill(email)
            page.locator('#profile-email-password').fill('demo1234')
            save_personal()
            names_equal(markup_name)
            assert page.locator('[data-account-name] img').count() == 0
            assert page.evaluate('window.__profileXss') is False
            page.reload()
            names_equal(markup_name)
            expect(page.locator('#profile-name')).to_have_value(markup_name)
            assert page.locator('[data-account-name] img').count() == 0
            assert page.evaluate('window.__profileXss') is False

            # This exact dictionary key must remain a person's name in either UI language.
            name = 'Komunikasi'
            page.locator('#profile-name').fill(name)
            save_personal()
            toggle('en')
            expect(page.locator('h1')).to_have_text('My profile')
            names_equal(name)
            expect(page.locator('#profile-name')).to_have_value(name)
            expect(page.locator('#profile-email')).to_have_value(email)
            expect(page.locator('#profile-personal-status')).to_have_text('Changes saved.')

            cv = ('</textarea><script>window.__profileXss=true</script>\n'
                  + 'Komunikasi, Kepemimpinan, dan Kerja sama. Pengalaman sintetis untuk latihan. ' * 8)
            page.locator('#profile-cv-text').fill(cv)
            toggle('id')
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            toggle('en')
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            with page.expect_response(lambda response: response.url.endswith('/api/profile')
                                      and response.request.method == 'PATCH') as response:
                page.locator('#profile-cv-form [type=submit]').click()
            assert response.value.status == 200
            cv = cv.strip()
            expect(page.locator('#profile-cv-status')).to_have_text('CV saved.')
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            expect(page.locator('#profile-delete-cv')).to_be_enabled()
            assert profile()['cv_text'] == cv
            page.reload()
            language('en')
            names_equal(name)
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            assert page.evaluate('window.__profileXss') is False
            responsive('profile-en')
            toggle('id')
            names_equal(name)
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            responsive('profile-id')

            page.locator('.setup-nav a[href="/simulasi/baru"]').click()
            page.wait_for_url('**/simulasi/baru')
            language('id')
            page.locator('#setup-context > summary').click()
            expect(page.locator('[name=candidate_name]')).to_have_value(name)
            page.locator('[name=job_role]').fill('Komunikasi')
            description = 'Kerja sama dan Kepemimpinan. Ini isian pengguna yang harus tetap asli.'
            page.locator('[name=job_description]').fill(description)
            page.locator('#setup-select-language-trigger').click()
            page.locator('#setup-select-language-menu [data-value="en"]').click()
            expect(page.locator('[name=language]')).to_have_value('en')
            for ui_language in ('en', 'id', 'en'):
                toggle(ui_language)
                expect(page.locator('[name=language]')).to_have_value('en')
                expect(page.locator('[name=candidate_name]')).to_have_value(name)
                expect(page.locator('[name=job_role]')).to_have_value('Komunikasi')
                expect(page.locator('[name=job_description]')).to_have_value(description)
            responsive('setup-en')

            page.locator('#account-menu > summary').click()
            page.locator('#account-menu a[href="/profile"]').click()
            page.wait_for_url('**/profile')
            language('en')
            names_equal(name)
            expect(page.locator('#profile-cv-text')).to_have_value(cv)
            page.locator('#profile-delete-cv').click()
            expect(page.locator('#profile-delete-dialog')).to_be_visible()
            expect(page.locator('#profile-delete-title')).to_have_text('Remove your saved CV?')
            page.locator('#profile-cancel-delete').click()
            expect(page.locator('#profile-delete-dialog')).not_to_be_visible()
            assert profile()['cv_text'] == cv
            page.locator('#profile-delete-cv').click()
            page.locator('#profile-delete-dialog [name=password]').fill('demo1234')
            page.locator('#profile-delete-dialog [name=confirmation]').fill('HAPUS CV')
            with page.expect_response(lambda response: response.url.endswith('/api/profile/cv')
                                      and response.request.method == 'DELETE') as response:
                page.locator('#profile-confirm-delete').click()
            assert response.value.status == 200
            expect(page.locator('#profile-delete-dialog')).not_to_be_visible()
            expect(page.locator('#profile-cv-status')).to_have_text('CV removed.')
            expect(page.locator('#profile-cv-text')).to_have_value('')
            expect(page.locator('#profile-delete-cv')).to_be_disabled()
            assert profile()['has_cv'] is False
            page.reload()
            language('en')
            expect(page.locator('#profile-cv-text')).to_have_value('')
            expect(page.locator('#profile-delete-cv')).to_be_disabled()
            expect(page.locator('#profile-name')).to_have_value(name)
            expect(page.locator('#profile-email')).to_have_value(email)

            page.locator('#account-menu > summary').click()
            page.locator('#logout').click()
            page.wait_for_url('**/login')
            language('en')
            expect(page.locator('#auth-title')).to_have_text('Welcome back.')
            assert context.request.get(base + '/api/profile').status == 401
            assert not errors, errors
            assert not unexpected_sessions, unexpected_sessions
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    print('PASS: isolated profile update/CV save/cancel/delete/logout, escaped user content, '
          'EN/ID persistence and content preservation, separate interview language, '
          '390/768/1440px layouts. No external requests or provider calls.')


if __name__ == '__main__':
    main()
