"""Panel selection with an older setup bundle already cached. No provider calls."""
import argparse
import asyncio
from pathlib import Path
import socket
import threading

from playwright.sync_api import expect, sync_playwright
from fastapi.responses import HTMLResponse, Response
import browser_smoke as fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    legacy_requests = []

    @fixture.app.middleware('http')
    async def previous_release(request, call_next):
        path = request.url.path
        if path == '/cached-setup-release':
            return HTMLResponse('<link rel="stylesheet" href="/static/css/session-setup.css">'
                                '<script src="/static/js/session-setup.js"></script>')
        if path in ('/static/css/session-setup.css', '/static/js/session-setup.js') and not request.url.query:
            legacy_requests.append(path)
            script = path.endswith('.js')
            return Response('window.__cachedSetupRelease = true;' if script else '/* Previous release */',
                            media_type='application/javascript' if script else 'text/css',
                            headers={'Cache-Control': 'public, max-age=31536000'})
        if path.startswith('/api/sessions') and request.method != 'GET':
            return Response('Interview writes disabled in UI test', status_code=503)
        return await call_next(request)

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
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.add_init_script("localStorage.setItem('preptiva-ui-language', 'id')")
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = f'http://127.0.0.1:{port}'
            page.goto(base + '/cached-setup-release')
            assert page.evaluate('window.__cachedSetupRelease === true')
            page.goto(base + '/dev-login')
            page.locator('#setup-select-interview_mode-trigger').click()
            page.get_by_role('option', name='Panel · 2–3 pewawancara', exact=True).click()
            expect(page.locator('#single-personas')).not_to_be_visible()
            expect(page.locator('#panel-personas')).to_be_visible()
            assert len(legacy_requests) == 2, 'Old unversioned files must come from the primed browser cache'

            def selected():
                return page.evaluate('new FormData(document.querySelector("#session-form")).getAll("panel")')

            def card(value):
                return page.locator(f'#panel-personas label:has(input[value="{value}"])')

            assert selected() == ['hr', 'user']
            expect(page.locator('#panel-personas input[type=checkbox]:enabled')).to_have_count(3)
            expect(page.locator('#panel-personas .setup-persona-avatar')).to_have_count(3)
            card('manager').click()
            assert selected() == ['hr', 'user', 'manager']
            card('hr').click()
            assert selected() == ['user', 'manager']
            page.locator('[name=panel][value=hr]').focus()
            page.keyboard.press('Space')
            assert selected() == ['hr', 'user', 'manager']
            card('user').click()
            card('manager').click()
            assert page.locator('[name=panel][value=hr]').evaluate('el => !el.checkValidity()')
            card('user').click()
            card('manager').click()

            for width in (1440, 768, 390, 320):
                page.set_viewport_size({'width': width, 'height': 1000})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}px'
                gap = page.evaluate('''() => document.querySelector('#panel-personas').getBoundingClientRect().top
                    - document.querySelector('.setup-mode-field').getBoundingClientRect().bottom''')
                assert gap >= 16, f'Format control and persona cards touch at {width}px: {gap}'
                if args.screenshots_dir and width in (1440, 390):
                    args.screenshots_dir.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(args.screenshots_dir / f'panel-{width}.png'), full_page=True)

            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.locator('#setup-select-interview_mode-trigger').click()
            page.get_by_role('option', name='Satu pewawancara', exact=True).click()
            expect(page.locator('#single-personas')).to_be_visible()
            expect(page.locator('#panel-personas')).not_to_be_visible()
            assert selected() == []
            page.locator('#single-personas label:has(input[value="manager"])').click()
            page.locator('#single-personas label:has(input[value="user"])').click()
            expect(page.locator('#single-personas input:checked')).to_have_count(1)
            expect(page.locator('#single-personas input[value=user]')).to_be_checked()
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    print('PASS: cached old bundle bypassed; 2/3-member panel, card/keyboard toggles, minimum validation, single mode and 320–1440px layout. No provider calls.')


if __name__ == '__main__':
    main()
