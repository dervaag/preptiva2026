"""End-to-end UI for an opt-in EM rubric, with synthetic text and injected providers."""
import asyncio
import json
import os
from pathlib import Path
import socket
import threading
import time
import browser_smoke as fixture
from app.ai import speech,orchestrator
from app.config import settings
from playwright.sync_api import sync_playwright


async def generate(context,slots,history):
    return {'intro':'Selamat datang.','closing':'Terima kasih.','questions':[
        {'slot':slot['slot'],'category':slot['competencies'][0],
         'question_text':f'Bagaimana pengalaman Anda dalam {context["job_competencies"][slot["competencies"][0]]["name"].lower()}?',
         'competencies':slot['competencies'],'expected_points':['Kontribusi pribadi dan hasil'],'anchor_id':'cv1'} for slot in slots]}

async def tts(*args,**kwargs):return None
async def adapt(context):return context['planned_question']
async def evaluate(context):
    key=context['competencies'][0];quote=context['source_turns'][0]['transcript'];anchor=context['competency_definitions'][key]['levels']['4']['id']
    return {'competency_scores':{key:{'score':4,'evidence':[quote],'evidence_sufficiency':'sufficient','indicators_met':[anchor],
        'indicator_evidence':[{'indicator_id':anchor,'quote':quote}],'next_level_gap':'Hasil peninjauan setelah tindakan belum dijelaskan.'}},
        'star':{},'feedback':{'strengths':[],'improvements':[],'better_answer_tip':'Tambahkan bukti hasil.'}}


def main():
    from app import storage
    storage.ROOT=Path(fixture.temporary.name)
    artifacts=Path(os.environ.get('PREPTIVA_BROWSER_ARTIFACTS', str(Path(fixture.temporary.name)/'artifacts')))
    artifacts.mkdir(parents=True,exist_ok=True)
    settings.realtime_voice_enabled=False
    speech.require_credentials=lambda persona:None;speech.optional_synthesize=tts
    orchestrator.parse_documents=fixture.parse;orchestrator.generate_set=generate
    orchestrator.adapt_question=adapt;orchestrator.respond=fixture.respond
    orchestrator.evaluate=evaluate;orchestrator.summarize=fixture.summarize
    asyncio.run(fixture.seed())
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=fixture.uvicorn.Server(fixture.uvicorn.Config(fixture.app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    report={'ok':False,'synthetic':True,'paid_api_calls':False,'human_validation':False};errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
            def choose(name,value):
                page.locator(f'[data-select="{name}"] [role=combobox]').click()
                page.locator(f'#setup-select-{name}-menu [role=option][data-value="{value}"]').click()
            page.goto(f'http://127.0.0.1:{port}/login')
            page.locator('[name=email]').fill('demo@interview.local');page.locator('[name=password]').fill('demo1234')
            page.get_by_role('button',name='Masuk',exact=True).click();page.wait_for_url('**/dashboard')
            page.goto(f'http://127.0.0.1:{port}/simulasi/baru')
            page.locator('#setup-context > summary').click()
            page.locator('[name=job_role]').fill('Engineering Manager')
            page.locator('label:has(input[name=interviewer][value=manager])').click()
            option=page.locator('[name=use_job_rubric]');assert option.is_visible() and not option.is_checked()
            option.check();page.locator('[name=job_role]').fill('Product Manager');assert not option.is_checked() and option.is_disabled()
            page.locator('[name=job_role]').fill('Engineering Manager');option.check()
            choose('interview_mode','panel');assert not option.is_checked() and option.is_disabled()
            choose('interview_mode','single');option.check()
            page.locator('label:has(input[name=interviewer][value=hr])').click();assert not option.is_checked() and option.is_disabled()
            page.locator('label:has(input[name=interviewer][value=manager])').click();option.check()
            page.locator('#session-form').evaluate('form => form.reset()')
            assert not option.is_checked() and option.is_disabled() and not option.is_visible()
            assert page.locator('[name=interview_mode]').input_value()=='single'
            page.locator('[name=job_role]').fill('Engineering Manager')
            page.locator('label:has(input[name=interviewer][value=manager])').click();option.check()
            page.locator('[name=cv_text]').fill('Saya memimpin proyek engineering, meninjau risiko migrasi layanan, mengembangkan anggota tim, dan menyelaraskan prioritas dengan tim produk. '*3)
            choose('career_stage','experienced');choose('level','manager')
            page.locator('[name=industry]').fill('Technology');page.locator('[name=job_description]').fill('Mengembangkan tim engineering, meninjau keputusan teknis, dan mengelola prioritas bersama stakeholder.')
            page.locator('.setup-question-choice:has(input[value="5"])').click();page.locator('[name=consent]').check()
            page.get_by_role('button',name='Siapkan wawancara').click();page.wait_for_url('**/ruang')
            sid=page.url.split('/sesi/')[1].split('/')[0]
            try:
                page.wait_for_function("document.querySelector('#room-status').textContent==='SIAP DIMULAI'")
            except Exception:
                report.update(page_errors=errors,room_status=page.locator('#room-status').inner_text(),
                    room_error=page.locator('#room-error').inner_text(),
                    session_state=page.evaluate('async path => (await fetch(path)).json()',f'/api/sessions/{sid}/state'))
                page.screenshot(path=str(artifacts/'em-rubric-room-failure.png'),full_page=True)
                raise
            page.locator('#text-mode').check();page.locator('#focus-check').check();page.locator('#start').click()
            for turn in range(1,6):
                page.wait_for_function("number => document.querySelector('#question-progress').textContent.includes(number+' / 5')",arg=str(turn))
                page.locator('#text-answer').fill('Contoh sintetis untuk uji perangkat lunak. Saya membandingkan dua pilihan, meminta masukan tim, menjelaskan risiko, dan menetapkan peninjauan bersama stakeholder.')
                page.locator('#send-text').click()
            page.wait_for_url('**/hasil',timeout=30000);page.wait_for_selector('.rubric-notice')
            assert 'draf' in page.locator('.rubric-notice').inner_text().lower()
            assert page.locator('.competency').count()==5
            for element in page.locator('.review-item > summary').all():element.click()
            for element in page.locator('.result-evidence > summary').all():element.click()
            assert page.locator('.indicator-chain').count()==5
            assert page.get_by_text('Hasil peninjauan setelah tindakan belum dijelaskan.',exact=True).count()==5
            page.locator('.indicator-sources summary').first.click()
            assert page.locator('.indicator-sources a').first.get_attribute('href').startswith('https://')
            for width in (390,768,1440):
                page.set_viewport_size({'width':width,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            page.screenshot(path=str(artifacts/'em-rubric-result.png'),full_page=True)
            data=page.evaluate('async path => (await fetch(path)).json()',f'/api/sessions/{sid}/result')
            assert data['assessment']['profile_id']=='engineering_manager_manager' and data['assessment']['validated'] is False
            assert data['coverage']['weighted_percent']==100
            assert not errors,errors
            report.update(ok=True,opt_in_scope=True,five_competencies=True,indicator_evidence_gap_sources=True,legacy_general_untouched=True,responsive_widths=[390,768,1440])
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=10)
        (artifacts/'em-rubric-browser-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
