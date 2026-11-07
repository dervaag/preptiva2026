"""Isolated meeting-room UI checks with fake providers and synthetic devices."""
import argparse
import asyncio
from pathlib import Path
import socket
import threading
import time

import browser_smoke as fixture
from playwright.sync_api import expect, sync_playwright


async def tts(text, persona, uuid, name, live=False):
    (fixture.audio_dir(uuid) / name).write_bytes(fixture.wav(.8))
    return f'/api/sessions/{uuid}/audio/{name}'


async def respond(context):
    await asyncio.sleep(.7)
    if context['allow_followup'] and context['question'].startswith('Ceritakan'):
        return {'action':'follow_up','response_text':'Apa dampak kontribusi pribadi Anda?'}
    return {'action':'next','response_text':'Terima kasih atas jawaban Anda.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots-dir',type=Path)
    args=parser.parse_args()
    from app import storage
    storage.ROOT=Path(fixture.temporary.name)
    fixture.speech.require_credentials=lambda persona: None
    fixture.speech.synthesize=tts
    fixture.speech.transcribe=fixture.transcribe
    fixture.orchestrator.parse_documents=fixture.parse
    fixture.orchestrator.build_questions=fixture.questions
    fixture.orchestrator.respond=respond
    fixture.orchestrator.evaluate=fixture.evaluate
    fixture.orchestrator.summarize=fixture.summarize
    asyncio.run(fixture.seed())
    mic=Path(fixture.temporary.name)/'room-mic.wav'
    mic.write_bytes(fixture.wav(8))
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=fixture.uvicorn.Server(fixture.uvicorn.Config(fixture.app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',f'--use-file-for-fake-audio-capture={mic}'])
            context=browser.new_context(permissions=['camera','microphone'],viewport={'width':1440,'height':900})
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/dev-login')
            created=page.request.post(f'http://127.0.0.1:{port}/api/sessions',multipart={
                'candidate_name':'Kandidat Uji','gender':'male','age':'28','job_role':'Product Designer','level':'middle','industry':'Technology',
                'job_description':'Design accessible user experiences through research and product experiments.',
                'cv_text':'Pengalaman riset produk dan kolaborasi bersama tim untuk mengukur dampak. '*8,
                'question_count':'3','interviewer':'hr','language':'id','consent':'true'})
            assert created.ok,created.text()
            sid=created.json()['session_id']
            base=f'http://127.0.0.1:{port}/api/sessions/{sid}'
            mobile_devices=[
                ('phone','Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1',390,844),
                ('tablet','Mozilla/5.0 (Linux; Android 15; Tablet) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36',820,1180),
                ('ipad-desktop','Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15',1024,768),
            ]
            for name,user_agent,width,height in mobile_devices:
                mobile=browser.new_context(storage_state=context.storage_state(),user_agent=user_agent,viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
                mobile_page=mobile.new_page();mobile_page.on('pageerror',lambda error:errors.append(str(error)))
                if name=='ipad-desktop':
                    mobile_page.add_init_script("Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});")
                mobile_page.goto(f'http://127.0.0.1:{port}/sesi/{sid}/ruang')
                expect(mobile_page.locator('#preflight')).to_be_visible()
                expect(mobile_page.locator('#device-requirement')).to_be_visible()
                expect(mobile_page.locator('#start')).to_be_disabled()
                expect(mobile_page.locator('#devices')).to_be_disabled()
                assert mobile_page.locator('#camera').evaluate('(el)=>el.srcObject===null')
                if args.screenshots_dir and name=='phone':
                    args.screenshots_dir.mkdir(parents=True,exist_ok=True)
                    mobile_page.screenshot(path=str(args.screenshots_dir/'device-mobile-blocked.png'))
                rejected=mobile_page.request.post(base+'/start',headers={'X-Preptiva-Device':'mobile'} if name=='ipad-desktop' else {})
                assert rejected.status==403,(name,rejected.text())
                mobile.close()
            assert page.request.get(base+'/state').json()['status']=='ready'
            page.goto(f'http://127.0.0.1:{port}/sesi/{sid}/ruang')
            expect(page.locator('#meeting-room')).to_be_visible(timeout=3000)
            expect(page.locator('#preflight')).to_be_visible()
            expect(page.locator('#start')).to_be_disabled()
            for width in (320,390,768,1024,1440):
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                box=page.locator('#preflight').bounding_box()
                assert box and box['x']>=0 and box['x']+box['width']<=width
            for width,height in ((320,480),(720,390),(1024,390)):
                page.set_viewport_size({'width':width,'height':height})
                box=page.locator('#preflight').bounding_box()
                assert box and box['y']>=0 and box['y']+box['height']<=height
                page.keyboard.press('Escape')
                page.mouse.move(5,height//2);page.mouse.wheel(0,2400);page.wait_for_timeout(150)
                for selector in ('#mic-toggle','#open-preflight'):
                    control=page.locator(selector).bounding_box()
                    assert control and control['y']>=0 and control['y']+control['height']<=height,(width,height,selector,control)
                chat=page.locator('#chat-panel').bounding_box()
                toolbar=page.locator('.meeting-toolbar').bounding_box()
                assert chat and toolbar and chat['y']+chat['height']<=toolbar['y'],(width,height,'chat overlaps toolbar')
                page.locator('#open-preflight').click()
            page.set_viewport_size({'width':1440,'height':900})
            if args.screenshots_dir:
                args.screenshots_dir.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(args.screenshots_dir/'preflight-desktop.png'))
            page.locator('#devices').click()
            page.locator('#test-sound').click()
            page.locator('#camera-check').check()
            page.locator('#speaker-check').check()
            page.locator('#focus-check').check()
            expect(page.locator('#start')).to_be_enabled(timeout=15000)
            page.locator('#start').click()
            for number in ('3','2','1'):
                expect(page.locator('#countdown-number')).to_have_text(number)
            page.wait_for_function('document.querySelector("#room-countdown").hidden')
            page.wait_for_function('document.querySelector("#room-stage").dataset.speaking === "true"')
            assert page.locator('#interviewer-avatar').evaluate('(el)=>getComputedStyle(el).backgroundImage.includes("rina-sprite")')
            page.wait_for_function('!document.querySelector("#record-controls").hidden && !document.querySelector("#record").hidden')
            expect(page.locator('#chat-log .chat-message--ai')).not_to_have_count(0)
            page.locator('#captions-toggle').click()
            expect(page.locator('#captions-toggle')).to_have_attribute('aria-pressed','true')
            page.locator('#chat-toggle').click()
            expect(page.locator('#chat-panel')).to_be_hidden()
            expect(page.locator('#record')).to_be_visible()
            page.locator('#chat-toggle').click()
            if args.screenshots_dir:
                page.screenshot(path=str(args.screenshots_dir/'room-desktop.png'))
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(args.screenshots_dir/'room-mobile.png'),full_page=True)
                page.set_viewport_size({'width':1440,'height':900})
            for turn_index in range(4):
                page.wait_for_function('!document.querySelector("#record-controls").hidden && !document.querySelector("#record").hidden')
                page.locator('#record').click();page.wait_for_timeout(600);page.locator('#record').click()
                page.locator('#send').click()
                if turn_index==0:
                    expect(page.locator('#chat-activity')).to_be_visible()
                    expect(page.locator('#chat-log .chat-message--candidate')).to_have_count(1)
                    expect(page.locator('#chat-log .chat-message--ai').last).to_contain_text('Apa dampak kontribusi pribadi Anda?')
                    expect(page.locator('#chat-activity')).to_be_hidden()
                    expect(page.locator('#record')).to_be_visible()
                    page.wait_for_timeout(200)
                    candidate=page.locator('#chat-log .chat-message--candidate .chat-message-body')
                    interviewer=page.locator('#chat-log .chat-message--ai .chat-message-body').last
                    assert candidate.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(23, 101, 232)'
                    assert interviewer.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(255, 255, 255)'
                    assert candidate.bounding_box()['x']>interviewer.bounding_box()['x']
                    expect(page.locator('#chat-log .chat-message--ai').nth(1)).to_have_attribute('data-continuation','true')
                    page.emulate_media(reduced_motion='reduce')
                    assert candidate.locator('..').evaluate('(el)=>getComputedStyle(el).animationName')=='none'
                    page.emulate_media(reduced_motion='no-preference')
                    if args.screenshots_dir:
                        page.screenshot(path=str(args.screenshots_dir/'chat-room-desktop.png'))
                        page.locator('#chat-panel').screenshot(path=str(args.screenshots_dir/'chat-conversation.png'))
                    page.set_viewport_size({'width':768,'height':650})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    assert candidate.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
                    page.set_viewport_size({'width':1440,'height':900})
            page.wait_for_url('**/hasil',timeout=30000)
            page.wait_for_selector('.score-number')
            assert (page.request.get(base+'/state').json())['status']=='done'
            result=page.request.get(base+'/result').json()
            assert len(result['items'])==4
            assert not errors,errors
            browser.close()
            print('PASS: white/blue alternating chat, grouping, live processing state, reduced motion, narrow layout, desktop device verification and four-turn follow-up flow through results. Mobile remains blocked. No paid providers.')
    finally:
        server.should_exit=True;thread.join(timeout=10)


if __name__=='__main__':main()
