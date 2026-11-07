"""Auth UI and real account flow on an isolated database, without provider calls."""
import argparse
import asyncio
from pathlib import Path
import socket
import threading

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
    server = fixture.uvicorn.Server(fixture.uvicorn.Config(fixture.app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 900})
            page = context.new_page(); page.set_default_timeout(4000)
            page.add_init_script("localStorage.setItem('preptiva-ui-language', 'id')")
            errors, pending, registrations = [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: registrations.append(request) if request.url.endswith('/api/auth/register') else None)
            page.route('**/api/sessions**', lambda route: route.abort() if route.request.method != 'GET' else route.continue_())
            base = f'http://127.0.0.1:{port}'
            page.goto(base + '/login')
            expect(page.get_by_role('heading', name='Selamat datang kembali.')).to_be_visible()
            password = page.locator('[name=password]')
            password.fill('contoh1234')
            page.get_by_role('button', name='Tampilkan password', exact=True).focus()
            page.keyboard.press('Space')
            expect(password).to_have_attribute('type', 'text')
            expect(password).to_have_value('contoh1234')
            page.get_by_role('button', name='Sembunyikan password', exact=True).click()
            expect(password).to_have_attribute('type', 'password')

            page.route('**/api/auth/login', lambda route: pending.append(route))
            page.locator('[name=email]').fill('demo@interview.local')
            page.get_by_role('button', name='Masuk', exact=True).click()
            expect(page.locator('#auth-form')).to_have_attribute('aria-busy', 'true')
            expect(page.locator('[type=submit]')).to_be_disabled()
            page.evaluate('''async () => {
              document.querySelector('#auth-form').requestSubmit();
              await new Promise(requestAnimationFrame);
            }''')
            assert len(pending) == 1, 'Pending auth must not submit twice'
            pending[0].fulfill(status=401, content_type='application/json', body='{"detail":"Email atau password salah."}')
            expect(page.locator('#auth-error')).to_have_text('Email atau password salah.')
            expect(page.get_by_role('button', name='Masuk', exact=True)).to_be_enabled()
            expect(page.locator('#auth-form')).not_to_have_attribute('aria-busy', 'true')
            expect(page.locator('[name=email]')).to_have_value('demo@interview.local')
            page.unroute('**/api/auth/login')
            password.fill('demo1234')
            page.get_by_role('button', name='Masuk', exact=True).click()
            page.wait_for_url('**/dashboard')
            assert context.request.get(base + '/api/me').json()['email'] == 'demo@interview.local'
            page.goto(base + '/login')
            expect(page.locator('.sidebar')).to_have_count(0)
            expect(page.locator('.topbar')).to_have_count(0)
            context.request.post(base + '/api/auth/logout')

            for kind in ('login', 'register'):
                page.goto(base + '/' + kind)
                page.evaluate('document.fonts.ready')
                for width, height in ((1440, 900), (1024, 600), (768, 1024), (390, 844), (320, 640)):
                    page.set_viewport_size({'width': width, 'height': height})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{kind} overflow at {width}'
                    action = page.get_by_role('button', name='Buat akun' if kind == 'register' else 'Masuk', exact=True)
                    action.scroll_into_view_if_needed()
                    expect(action).to_be_visible()
                    if args.screenshots_dir and width in (1440, 390):
                        args.screenshots_dir.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(args.screenshots_dir / f'{kind}-{width}.png'), full_page=True)

            page.set_viewport_size({'width': 1440, 'height': 900})
            page.locator('[name=name]').fill('Kandidat Contoh')
            page.locator('[name=email]').fill('contoh-auth@example.com')
            page.locator('[name=password]').fill('latihan1234')
            page.locator('[name=password_confirm]').fill('berbeda1234')
            page.locator('[name=age]').fill('24')
            page.locator('#setup-select-gender-trigger').click()
            page.get_by_role('option', name='Perempuan', exact=True).click()
            page.locator('[name=agree]').check()
            page.get_by_role('button', name='Buat akun', exact=True).click()
            assert registrations == [], 'Password mismatch must not reach register API'
            assert page.locator('[name=password_confirm]').evaluate('el => !el.checkValidity()')
            page.locator('[name=password_confirm]').fill('latihan1234')
            page.get_by_role('button', name='Buat akun', exact=True).click()
            page.wait_for_url('**/dashboard')
            profile = context.request.get(base + '/api/me').json()
            assert profile['name'] == 'Kandidat Contoh' and profile['gender'] == 'female' and profile['age'] == 24
            assert len(registrations) == 1
            context.request.post(base + '/api/auth/logout')
            page.goto(base + '/login')
            page.get_by_role('link', name='Buat akun', exact=True).click()
            page.wait_for_url('**/register')
            page.get_by_role('link', name='Masuk', exact=True).click()
            page.wait_for_url('**/login')
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    print('PASS: isolated real login/register/logout, password visibility/mismatch, duplicate guard, failed-login recovery, custom gender, auth shell and 320–1440px layouts. No providers.')


if __name__ == '__main__':
    main()
