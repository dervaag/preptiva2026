"""Verify public WSS -> Kiri -> OpenAI ready handshake; sends no audio and invokes no LLM/TTS.
Creates and deletes only a dedicated synthetic account/session. Requires --check-provider.
"""
import argparse
import json
from pathlib import Path
import secrets
from uuid import uuid4
from playwright.sync_api import sync_playwright
from kiri_smoke import container_python

ROOT=Path(__file__).resolve().parents[1]


def main(url):
    email='voice-check-'+uuid4().hex+'@example.com'
    password=secrets.token_hex(20)
    report={'ok':False,'url':url,'provider_handshake':False,'audio_sent':False,'llm_tts_calls':False}
    created=False
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            page=browser.new_page();page.goto(url+'/login')
            if page.title()=='You are about to visit a shared site':
                page.get_by_text('Continue to site',exact=True).click();page.wait_for_selector('[name=email]')
            response=page.evaluate('''async data => {const response=await fetch('/api/auth/register',{
                method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});return response.status;}''',
                {'name':'Synthetic Voice Check','email':email,'password':password,'password_confirm':password,'gender':'male','age':28,'agree':True})
            assert response==200,response
            created=True
            source='''
import asyncio,json
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User,InterviewSession,InterviewQuestion
from app.ai.assessment import snapshot
async def run():
    async with SessionLocal() as db:
        user=await db.scalar(select(User).where(User.email==EMAIL))
        assert user is not None
        session=InterviewSession(user_id=user.id,candidate_name='Synthetic Voice Check',gender='male',age=28,job_role='Manager',level='manager',industry='Technology',job_description='Synthetic transport check.',cv_text='Synthetic transport check.',interviewer='hr',status='running',question_count=3,answer_seconds=30,script={'settings':{'language':'id','panel':['hr'],'streaming_voice':True},'assessment':snapshot('hr')})
        db.add(session);await db.flush()
        question=InterviewQuestion(session_id=session.id,main_order=1,slot='opening',question_text='Synthetic transport check.',competencies=['communication'])
        db.add(question);await db.commit()
        print(json.dumps({'sid':session.uuid,'qid':question.id}))
asyncio.run(run())
'''.replace('EMAIL',repr(email))
            fixture=json.loads(container_python(source))
            page.goto(url+'/sesi/'+fixture['sid']+'/ruang')
            page.wait_for_function("document.querySelector('#room-status').textContent === 'SIAP DIMULAI'")
            assert page.locator('#voice-mode').is_checked()
            assert page.locator('#text-mode').get_attribute('type') == 'radio'
            assert page.locator('#use-voice').count() == 1
            page.locator('#text-mode').check()
            assert not page.locator('#voice-mode').is_checked()
            report['answer_mode_choices']=True
            status=page.evaluate('''data => new Promise(resolve => {
                const socket=new WebSocket(`wss://${location.host}/api/sessions/${data.sid}/voice/${data.qid}`);
                const timer=setTimeout(()=>{socket.close();resolve('timeout')},25000);
                socket.onmessage=event=>{const message=JSON.parse(event.data);clearTimeout(timer);socket.close();resolve(message.type)};
                socket.onerror=()=>{clearTimeout(timer);resolve('socket_error')};
                socket.onclose=event=>{clearTimeout(timer);resolve('closed_'+event.code)};
            })''',fixture)
            assert status=='ready',status
            report['provider_handshake']=True
            page.wait_for_timeout(1000)
            browser.close();report['ok']=True
    finally:
        if created:
            cleanup='''
import asyncio
from sqlalchemy import select,delete
from app.db import SessionLocal
from app.models import User,InterviewSession
async def run():
    async with SessionLocal() as db:
        user=await db.scalar(select(User).where(User.email==EMAIL))
        assert user is not None
        await db.execute(delete(InterviewSession).where(InterviewSession.user_id==user.id))
        await db.execute(delete(User).where(User.id==user.id,User.email==EMAIL))
        await db.commit()
        print('cleaned')
asyncio.run(run())
'''.replace('EMAIL',repr(email))
            report['synthetic_data_cleaned']=container_python(cleanup)=='cleaned'
        (ROOT/'artifacts/kiri-voice-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--check-provider',action='store_true')
    args=parser.parse_args()
    if not args.check_provider:parser.error('--check-provider is required to contact the configured OpenAI endpoint.')
    main(args.url.rstrip('/'))
