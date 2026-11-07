"""Chrome regression for text/voice switching; isolated data and synthetic providers.

Run: .venv/bin/python tests/voice_mode_browser_smoke.py
No real account, microphone, or paid provider is used.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import threading
import time

import browser_smoke as fixture
from app import storage
from app.ai import orchestrator, speech
from playwright.sync_api import sync_playwright


def main():
    storage.ROOT = Path(fixture.temporary.name) / 'storage'
    artifacts = Path(os.environ.get('PREPTIVA_BROWSER_ARTIFACTS', str(Path(fixture.temporary.name) / 'artifacts')))
    artifacts.mkdir(parents=True, exist_ok=True)
    speech.require_credentials = lambda persona: None
    speech.synthesize = fixture.tts
    speech.transcribe = fixture.transcribe
    orchestrator.parse_documents = fixture.parse
    orchestrator.build_questions = fixture.questions
    orchestrator.respond = fixture.respond
    orchestrator.adapt_question = fixture.adapt
    orchestrator.evaluate = fixture.evaluate
    orchestrator.summarize = fixture.summarize
    asyncio.run(fixture.seed())
    mic = Path(fixture.temporary.name) / 'microphone.wav'
    mic.write_bytes(fixture.wav(5))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = fixture.uvicorn.Server(fixture.uvicorn.Config(
        fixture.app, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    assert server.started, 'Isolated preview server did not start.'
    errors = []
    report = {'ok': False, 'synthetic': True, 'paid_api_calls': False}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True, args=[
                '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
                f'--use-file-for-fake-audio-capture={mic}'])
            context = browser.new_context(permissions=['camera', 'microphone'],
                                          viewport={'width': 1440, 'height': 1100})
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script("localStorage.setItem('preptiva-ui-language', 'id')")
            page.goto(f'http://127.0.0.1:{port}/login')
            page.locator('[name=email]').fill('demo@interview.local')
            page.locator('[name=password]').fill('demo1234')
            page.get_by_role('button', name='Masuk', exact=True).click()
            page.wait_for_url('**/dashboard')
            page.goto(f'http://127.0.0.1:{port}/simulasi/baru')
            page.locator('#setup-context > summary').click()
            page.locator('[name=cv_pdf]').set_input_files(fixture.cv_pdf(
                'Lulusan baru Akuntansi. Proyek kuliah koperasi kampus dan organisasi mahasiswa. ' * 4))
            page.locator('#setup-select-career_stage-trigger').click()
            page.locator('#setup-select-career_stage-menu [data-value="fresh_graduate"]').click()
            page.locator('[name=job_role]').fill('Accountant')
            page.locator('[name=industry]').fill('Finance')
            page.locator('[name=job_description]').fill(
                'Prepare accurate reports and coordinate financial information with colleagues.')
            page.locator('.setup-question-choice:has(input[value="3"])').click()
            page.locator('#setup-select-interview_mode-trigger').click()
            page.locator('#setup-select-interview_mode-menu [data-value="panel"]').click()
            page.locator('label:has(input[name=panel][value=manager])').click()
            page.locator('[name=consent]').check()
            page.get_by_role('button', name='Siapkan wawancara').click()
            page.wait_for_url('**/ruang')
            sid = page.url.split('/sesi/')[1].split('/')[0]
            page.wait_for_function("document.querySelector('#room-status').textContent === 'SIAP DIMULAI'")
            assert page.locator('#voice-mode').is_checked()
            assert not page.locator('#text-mode').is_checked()
            page.evaluate('''() => {
                const real = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                window.voicePermission = 'deny'; window.voicePermissionCalls = 0;
                navigator.mediaDevices.getUserMedia = constraints => {
                    window.voicePermissionCalls++;
                    const obtain = async () => {
                        const stream = await real(constraints);
                        window.voiceTestStream = stream;
                        return stream;
                    };
                    if (window.voicePermission === 'deny')
                        return Promise.reject(new DOMException('Synthetic permission denial', 'NotAllowedError'));
                    if (window.voicePermission === 'defer')
                        return new Promise((resolve, reject) => {
                            window.resolveVoicePermission = () => obtain().then(resolve, reject);
                        });
                    return obtain();
                };
            }''')
            page.locator('#text-mode').evaluate('(el) => { el.checked = true; el.dispatchEvent(new Event("change", {bubbles: true})); }')
            page.locator('#focus-check').check()
            page.locator('#start').click()
            page.wait_for_selector('#text-answer-area')
            assert page.evaluate('window.voicePermissionCalls') == 0
            assert page.locator('.panel-member').count() == 3
            draft = 'Draf jawaban sintetis yang perlu tetap tersedia setelah mengganti mode.'
            page.locator('#text-answer').fill(draft)
            page.locator('#use-voice').click()
            page.wait_for_selector('#room-error')
            assert page.locator('#text-answer-area').is_visible()
            assert page.locator('#text-answer').input_value() == draft
            assert not page.locator('#send-text').is_disabled()
            assert page.locator('#text-mode').is_checked()
            report['denied_permission_preserves_text'] = True

            page.evaluate("window.voicePermission = 'allow'")
            page.locator('#use-voice').click()

            def voice_ready():
                page.wait_for_function("!document.querySelector('#record-controls').hidden && !document.querySelector('#record').hidden && !document.querySelector('#record').disabled")

            voice_ready()
            assert page.locator('#voice-mode').is_checked()
            assert not page.locator('#text-mode').is_checked()
            assert page.locator('#text-answer-area').is_hidden()
            assert 'suara' in page.locator('#answer-mode-status').inner_text().lower()
            assert 'MEREKAM' not in page.locator('#room-status').inner_text()
            report['voice_requires_explicit_record_click'] = True
            page.locator('#use-text').click()
            assert page.locator('#text-answer').input_value() == draft
            assert page.locator('#text-mode').is_checked()
            page.locator('#use-voice').click()
            voice_ready()
            for width in (390, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 1000})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            report['mode_switch_preserves_draft'] = True

            def record_and_send():
                page.locator('#record').click()
                page.wait_for_function("document.querySelector('#room-status').textContent === 'MEREKAM'")
                page.wait_for_timeout(650)
                page.locator('#record').click()
                page.wait_for_selector('#send')
                page.locator('#send').click()

            record_and_send()
            page.wait_for_function("document.querySelector('#question-progress').textContent.includes('2 / 3')")
            voice_ready()
            assert page.locator('#voice-mode').is_checked()
            assert page.locator('#interviewer-name').inner_text() == 'Andi'
            page.locator('#use-text').click()
            page.locator('#text-answer').fill('Saya mengukur hasil eksperimen dan meningkatkan hasil sebesar 35 persen.')
            page.locator('#send-text').click()
            page.wait_for_function("document.querySelector('#question-progress').textContent.includes('3 / 3')")
            page.wait_for_selector('#text-answer-area')
            assert page.locator('#text-mode').is_checked()
            assert page.locator('#interviewer-name').inner_text() == 'Hendra'
            page.locator('#text-answer').fill(draft)
            # Expire only this fixture's microphone, then delay the next permission result.
            page.evaluate("window.voiceTestStream.getTracks().forEach(track => track.stop()); window.voicePermission = 'defer'")
            page.locator('#use-voice').click()
            page.wait_for_function("typeof window.resolveVoicePermission === 'function'")
            page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true}); document.dispatchEvent(new Event('visibilitychange')); Object.defineProperty(document,'hidden',{configurable:true,value:false});")
            page.wait_for_function("!document.querySelector('#retry-question').disabled")
            page.evaluate('window.resolveVoicePermission()')
            page.wait_for_timeout(350)
            assert page.locator('#interruption').is_visible()
            assert page.locator('#record-controls').is_hidden()
            assert page.locator('#text-answer-area').is_hidden()
            assert page.locator('#text-mode').is_checked()
            assert page.locator('#answer-timer').inner_text() == '00:00'
            assert page.evaluate("window.voiceTestStream.getTracks().every(track => track.readyState === 'ended')")
            report['late_permission_cannot_override_interruption'] = True

            page.locator('#retry-question').click()
            page.wait_for_selector('#text-answer-area')
            page.evaluate("window.voicePermission = 'allow'")
            page.locator('#use-voice').click()
            voice_ready()
            record_and_send()
            page.wait_for_url('**/hasil', timeout=30000)
            page.wait_for_selector('.score-number')
            result = page.evaluate('async path => (await fetch(path)).json()', f'/api/sessions/{sid}/result')
            assert [item['input_mode'] for item in result['items']] == ['audio', 'text', 'audio']
            assert len(result['panel_results']) == 3
            assert not errors, errors
            report.update(ok=True, audio_text_audio_panel_results=True, responsive_widths=[390, 768, 1440])
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        (artifacts / 'voice-mode-browser-smoke.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
