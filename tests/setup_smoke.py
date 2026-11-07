"""Check a running local setup page with fake devices and an intercepted session POST."""
import argparse
from email import policy
from email.parser import BytesParser
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    failures, submissions = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True, args=[
            '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
        context = browser.new_context(permissions=['camera', 'microphone'],
                                      viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        page.add_init_script("localStorage.setItem('preptiva-ui-language', 'id')")
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.add_init_script('''
          window.__deviceTracks = [];
          const acquire = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
          navigator.mediaDevices.getUserMedia = async (...args) => {
            const stream = await acquire(...args);
            window.__deviceTracks.push(...stream.getTracks());
            return stream;
          };
        ''')

        def intercept(route):
            request = route.request
            message = BytesParser(policy=policy.default).parsebytes(
                ('Content-Type: ' + request.headers['content-type'] + '\r\n\r\n').encode()
                + request.post_data_buffer)
            fields = {}
            for part in message.iter_parts():
                if part.get_filename() is not None:
                    continue
                name = part.get_param('name', header='content-disposition')
                value = part.get_payload(decode=True).decode(errors='replace')
                if name == 'panel':
                    fields.setdefault(name, []).append(value)
                else:
                    fields[name] = value
            submissions.append(fields)
            route.fulfill(status=503, content_type='application/json',
                          body='{"detail":"Respons uji: layanan sedang tidak tersedia."}')

        page.route('**/api/sessions', intercept)
        page.goto(args.base_url + '/dev-login')
        expect(page.get_by_role('heading', name='Siapkan Ruang Wawancara')).to_be_visible(timeout=3000)
        expect(page.locator('.setup-header')).to_be_visible()
        expect(page.locator('.sidebar')).to_have_count(0)
        expect(page.locator('#session-form')).to_be_visible()
        page.evaluate('document.fonts.ready')

        if args.screenshots_dir:
            args.screenshots_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.screenshots_dir / 'desktop.png'), full_page=True)
        for width in (320, 390, 768, 1024, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
            expect(page.get_by_role('button', name='Siapkan wawancara', exact=True)).to_be_visible()
            if width <= 390:
                assert page.evaluate('document.querySelector(".setup-actions").getBoundingClientRect().top >= document.querySelector(".setup-consent").getBoundingClientRect().bottom'), 'Mobile actions must not cover form content'
            if width == 390 and args.screenshots_dir:
                page.screenshot(path=str(args.screenshots_dir / 'mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 900})

        page.locator('.setup-header').get_by_role('link', name='Preptiva', exact=True).focus()
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.getAttribute("href") === "/dashboard"')
        page.locator('[name=interviewer][value=hr]').focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('[name=interviewer][value=user]')).to_be_checked()
        expect(page.locator('#setup-persona-description')).to_contain_text('Andi')
        page.keyboard.press('ArrowLeft')
        expect(page.locator('[name=interviewer][value=hr]')).to_be_checked()
        page.locator('#setup-context > summary').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#setup-context')).to_have_attribute('open', '')
        page.keyboard.press('Enter')
        assert not page.locator('#setup-context').evaluate('(el) => el.open')

        camera = page.get_by_role('button', name='Aktifkan kamera', exact=True)
        camera.click()
        expect(page.locator('#setup-camera-toggle')).to_have_attribute('aria-pressed', 'true')
        page.wait_for_function('document.querySelector("#setup-camera").videoWidth > 0')
        microphone = page.get_by_role('button', name='Aktifkan mikrofon', exact=True)
        microphone.click()
        expect(page.locator('#setup-mic-toggle')).to_have_attribute('aria-pressed', 'true')
        page.get_by_role('button', name='Mirror kamera', exact=True).focus()
        page.keyboard.press('Space')
        expect(page.locator('#setup-mirror-toggle')).to_have_attribute('aria-pressed', 'true')
        assert page.locator('#setup-camera').evaluate('(v) => getComputedStyle(v).transform.startsWith("matrix(-1")')
        assert page.locator('.setup-header .brand-symbol').evaluate('(v) => getComputedStyle(v).transform === "none"')
        page.get_by_role('button', name='Buka fullscreen', exact=True).click()
        page.wait_for_function('document.fullscreenElement?.id === "setup-preview-panel"')
        page.get_by_role('button', name='Keluar fullscreen', exact=True).click()
        page.wait_for_function('!document.fullscreenElement')
        page.get_by_role('button', name='Matikan kamera', exact=True).click()
        expect(page.locator('#setup-camera-toggle')).to_have_attribute('aria-pressed', 'false')
        expect(page.locator('#setup-mic-toggle')).to_have_attribute('aria-pressed', 'true')

        page.locator('#single-personas .setup-persona:has(input[value="user"])').click()
        expect(page.locator('#setup-persona-description')).to_contain_text('Andi')
        page.locator('[data-select="language"] [role=combobox]').click()
        page.get_by_role('option', name='Bahasa Inggris', exact=True).click()
        page.locator('.setup-question-choice:has(input[value="5"])').click()
        page.get_by_role('button', name='Siapkan wawancara', exact=True).click()
        expect(page.locator('#setup-context')).to_have_attribute('open', '')
        assert submissions == [], 'Invalid form must not submit'

        fields = {'candidate_name': 'Kandidat Uji UI', 'age': '28',
                  'job_role': 'Product Designer', 'industry': 'Teknologi',
                  'job_description': 'Melakukan riset pengguna dan merancang produk digital yang mudah digunakan.',
                  'cv_text': 'Pengalaman merancang produk, melakukan riset pengguna, dan bekerja bersama tim. ' * 5}
        for name, value in fields.items():
            page.locator(f'[name={name}]').fill(value)
        page.locator('[data-select="level"] [role=combobox]').click()
        page.get_by_role('option', name='Middle', exact=True).click()
        page.locator('[data-select="career_stage"] [role=combobox]').click()
        page.get_by_role('option', name='Sudah bekerja', exact=True).click()
        page.locator('[name=consent]').check()
        expect(page.locator('#setup-preview-name')).to_have_text('Kandidat Uji UI')
        page.get_by_role('button', name='Siapkan wawancara', exact=True).click()
        expect(page.locator('#form-error')).to_contain_text('Respons uji')
        expect(page.get_by_role('button', name='Siapkan wawancara', exact=True)).to_be_enabled()
        assert len(submissions) == 1
        assert submissions[0]['question_count'] == '5'
        assert submissions[0]['interviewer'] == 'user'
        assert submissions[0]['language'] == 'en'
        assert submissions[0]['consent'] == 'true'
        assert submissions[0]['career_stage'] == 'experienced'
        assert submissions[0]['interview_mode'] == 'single'
        assert 'panel' not in submissions[0]
        assert all(submissions[0][name] == value for name, value in fields.items())

        page.locator('[data-select="interview_mode"] [role=combobox]').click()
        page.get_by_role('option', name='Panel · 2–3 pewawancara', exact=True).click()
        page.locator('[name=panel][value=user]').uncheck()
        page.get_by_role('button', name='Siapkan wawancara', exact=True).click()
        assert len(submissions) == 1, 'A one-person panel must not reach the API'
        assert page.locator('[name=panel][value=hr]').evaluate('el => !el.checkValidity()')
        page.locator('[name=panel][value=manager]').check()
        page.get_by_role('button', name='Siapkan wawancara', exact=True).click()
        expect(page.get_by_role('button', name='Siapkan wawancara', exact=True)).to_be_enabled()
        assert submissions[-1]['panel'] == ['hr', 'manager']
        assert submissions[-1]['interviewer'] == 'user'
        assert submissions[-1]['career_stage'] == 'experienced'
        page.locator('[name=panel][value=user]').check()
        page.get_by_role('button', name='Siapkan wawancara', exact=True).click()
        expect(page.get_by_role('button', name='Siapkan wawancara', exact=True)).to_be_enabled()
        assert submissions[-1]['panel'] == ['hr', 'user', 'manager']
        page.locator('[data-select="interview_mode"] [role=combobox]').click()
        page.get_by_role('option', name='Satu pewawancara', exact=True).click()
        assert page.evaluate('new FormData(document.querySelector("#session-form")).getAll("panel")') == []

        for width in (320, 768, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Expanded form overflows at {width}'
        page.evaluate('window.dispatchEvent(new PageTransitionEvent("pagehide"))')
        expect(page.locator('#setup-mic-toggle')).to_have_attribute('aria-pressed', 'false')
        expect(page.locator('#setup-camera-toggle')).to_have_attribute('aria-pressed', 'false')
        assert page.evaluate('window.__deviceTracks.every(track => track.readyState === "ended")')

        page.evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow"))')
        page.evaluate('''async () => {
          window.__pendingStream = await navigator.mediaDevices.getUserMedia({video:true});
          navigator.mediaDevices.getUserMedia = () => new Promise(resolve => {window.__grantDevice = resolve;});
        }''')
        page.get_by_role('button', name='Aktifkan kamera', exact=True).click()
        page.wait_for_function('typeof window.__grantDevice === "function"')
        page.evaluate('''() => {
          window.dispatchEvent(new PageTransitionEvent('pagehide'));
          window.dispatchEvent(new PageTransitionEvent('pageshow'));
          window.__grantDevice(window.__pendingStream);
        }''')
        page.wait_for_function('window.__pendingStream.getTracks().every(track => track.readyState === "ended")', timeout=3000)
        expect(page.locator('#setup-camera-toggle')).to_have_attribute('aria-pressed', 'false')

        page.add_init_script('navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError"))')
        page.reload()
        page.get_by_role('button', name='Aktifkan kamera', exact=True).click()
        expect(page.locator('#setup-device-error')).to_be_visible()
        expect(page.get_by_role('button', name='Aktifkan kamera', exact=True)).to_be_enabled()
        page.set_viewport_size({'width': 1440, 'height': 768})
        page.locator('#setup-preview-panel').evaluate('(panel) => {panel.scrollTop = panel.scrollHeight;}')
        bounds = page.evaluate('''() => {
          const shell=document.querySelector('.setup-shell').getBoundingClientRect();
          const privacy=document.querySelector('.setup-privacy').getBoundingClientRect();
          const actions=document.querySelector('.setup-actions').getBoundingClientRect();
          return {shellBottom:shell.bottom,privacyBottom:privacy.bottom,actionsBottom:actions.bottom};
        }''')
        assert bounds['privacyBottom'] <= bounds['shellBottom'], bounds
        assert bounds['actionsBottom'] <= bounds['shellBottom'], bounds
        assert not failures, failures
        browser.close()
    print('PASS: responsive setup, synthetic devices, independent toggles, mirror/fullscreen, validation, payload/error recovery, cleanup and denied permissions. No provider calls.')


if __name__ == '__main__':
    main()
