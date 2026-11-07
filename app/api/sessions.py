import asyncio
import json
import re
from datetime import timedelta
from uuid import uuid4
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, update
from app.db import get_db, SessionLocal
from app.deps import current_user, owned_session
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, SessionCompetency, now
from app.ai import speech, orchestrator
from app.ai.assessment import snapshot
from app.ai.blueprint import forbidden_hr
from app.ai import guidebook, memory
from app.ai.scoring import aggregate, label, coverage
from app.config import settings
from app.jobs import enqueue
from app.services.text import validate_text, extract_pdf
from app.services.interview import state, turns, public_question, session_item
from app.storage import safe_audio_path
from app.log import emit, failure_fields, session_var, question_var, request_var
from app.services.locks import local_lock
from app.ai.errors import ProviderError
from app.services.events import record, checkpoint
from app.services.voice_capture import verify as verify_capture
from app.graphs.policy import enabled as graph_enabled, snapshot as orchestration_snapshot, aggregation_version, UnsupportedGraphVersion

router = APIRouter()


@router.post('/api/sessions')
async def create_session(candidate_name: str = Form(..., min_length=2, max_length=120), gender: Literal['male', 'female'] = Form(...),
    age: int = Form(..., ge=15, le=80), job_role: str = Form(..., min_length=2, max_length=150),
    level: Literal['junior', 'middle', 'senior', 'manager'] = Form(...), job_description: str = Form(...),
    industry: str = Form(..., min_length=2, max_length=80), company: str = Form('', max_length=150),
    question_count: int = Form(7), interviewer: Literal['hr', 'user', 'manager'] = Form(...),
    panel: list[str] = Form([]), career_stage: Literal['auto', 'student', 'fresh_graduate', 'experienced', 'career_switcher'] = Form('auto'),
    language: Literal['id', 'en'] = Form('id'), consent: bool = Form(...), use_last_cv: bool = Form(False), use_job_rubric: bool = Form(False),
    cv_text: str = Form(''), cv_pdf: Optional[UploadFile] = File(None), user=Depends(current_user), db=Depends(get_db)):
    if not consent or question_count not in (3, 5, 7):
        raise HTTPException(422, 'Persetujuan wajib; jumlah pertanyaan harus 3, 5, atau 7.')
    roles = panel or [interviewer]
    if (panel and len(panel) < 2) or len(roles) > 3 or len(set(roles)) != len(roles) or any(p not in ('hr', 'user', 'manager') for p in roles):
        raise HTTPException(422, 'Panel harus berisi maksimal tiga persona berbeda: HR, User, Manager.')
    interviewer = roles[0]
    try:
        assessment = snapshot(interviewer, roles, job_role=job_role, use_job_rubric=use_job_rubric)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    cv = user.last_cv_text if use_last_cv else cv_text
    if cv_pdf and cv_pdf.filename:
        cv = await asyncio.to_thread(extract_pdf, await cv_pdf.read(5 * 1024 * 1024 + 1))
    cv = validate_text(cv or '', 'CV')
    jd = validate_text(job_description, 'JD')
    try:
        for persona in roles:
            speech.require_credentials(persona)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    # Serialize creation per user in production so the hourly quota cannot race.
    from app.models import User
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = await db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.user_id == user.id, InterviewSession.created_at >= now() - timedelta(hours=1)))
    if count >= settings.max_sessions_per_hour:
        raise HTTPException(429, f'Maksimal {settings.max_sessions_per_hour} sesi per jam. Coba lagi nanti.')
    session = InterviewSession(user_id=user.id, candidate_name=candidate_name, gender=gender, age=age,
        job_role=job_role, level=level, industry=industry, company=company, job_description=jd, cv_text=cv,
        interviewer=interviewer, question_count=question_count, answer_seconds=settings.answer_seconds_for(level),
        max_followups=settings.followups_for(question_count),
        script={'settings': {'language': language, 'retry_limit': settings.retry_limit, 'panel': roles,
                            'career_stage': career_stage, 'dynamic_questions': True,
                            'streaming_voice': settings.realtime_voice_enabled,
                            'interruption_policy': 'retry_or_skip', 'evidence_policy': memory.VERSION},
                'guidebook': guidebook.snapshot(), 'assessment': assessment,
                'runtime': {'orchestration_version': memory.VERSION, 'model_fast': settings.model_fast,
                            'model_deep': settings.model_deep, 'stt_model': settings.stt_model,
                            **orchestration_snapshot(settings.orchestration_engine)}})
    db.add(session)
    user.last_cv_text = cv
    await db.flush()
    await record(db, session, 'created', 'session_created', {'memory_version': memory.VERSION})
    for key, weight in assessment['weights'].items():
        db.add(SessionCompetency(session_id=session.id, competency=key, weight=weight))
    await db.commit()
    try:
        await enqueue('prepare_session', session.id)
    except Exception:
        session.status = 'failed'
        session.error_message = 'Antrean tidak tersedia. Periksa Redis dan worker.'
        await db.commit()
        raise HTTPException(503, session.error_message)
    return {'session_id': session.uuid, 'status': session.status}


@router.get('/api/sessions')
async def list_sessions(user=Depends(current_user), db=Depends(get_db)):
    items = (await db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id).order_by(InterviewSession.created_at.desc()))).all()
    return {'items': [session_item(s) for s in items]}


@router.get('/api/sessions/{sid}/state')
async def session_state(session=Depends(owned_session), db=Depends(get_db)):
    return await state(db, session)


@router.post('/api/sessions/{sid}/start')
async def start(request: Request, session=Depends(owned_session), db=Depends(get_db)):
    user_agent = request.headers.get('user-agent', '').lower()
    platform = request.headers.get('sec-ch-ua-platform', '').strip().strip('"').lower()
    mobile = any(token in user_agent for token in ('android', 'iphone', 'ipad', 'ipod', 'mobile', 'iemobile', 'opera mini', 'silk', 'kindle', 'blackberry', 'webos'))
    if mobile or platform in ('android', 'ios') or request.headers.get('sec-ch-ua-mobile') == '?1' or request.headers.get('x-preptiva-device') == 'mobile':
        raise HTTPException(403, 'Wawancara wajib menggunakan PC atau laptop. HP dan tablet tidak didukung.')
    if session.status not in ('ready', 'running'):
        raise HTTPException(409, 'Sesi belum siap atau telah berakhir.')
    changed = await db.execute(update(InterviewSession).where(InterviewSession.id == session.id, InterviewSession.status == 'ready').values(status='running', started_at=now()))
    if changed.rowcount:
        await record(db, session, 'started', 'session_started')
    await db.commit()
    return {'status': 'running'}


async def process_answer(sid, owner_id, question_id, *args, **kwargs):
    session_token = session_var.set(sid)
    question_token = question_var.set(question_id)
    try:
        return await _dispatch_answer(sid, owner_id, question_id, *args, **kwargs)
    except Exception as exc:
        emit('answer_failed', **failure_fields(exc))
        if isinstance(exc, (HTTPException, UnsupportedGraphVersion)):
            raise
        if isinstance(exc, orchestrator.ModelOutputError):
            raise HTTPException(502, 'Respons AI belum memenuhi aturan wawancara. Coba kirim ulang jawaban yang sama.') from exc
        raise HTTPException(500, 'Pemrosesan gagal. Coba kirim ulang jawaban yang sama.') from exc
    finally:
        question_var.reset(question_token)
        session_var.reset(session_token)


async def _dispatch_answer(sid, *args, **kwargs):
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
        use_graph = session is not None and graph_enabled(session)
    if use_graph:
        from app.graphs.turn import process
        from app.graphs.runtime import GraphOperationUncertain, GraphBusy
        try:
            return await process(sid, *args, **kwargs)
        except GraphOperationUncertain as exc:
            raise HTTPException(409, 'Status pemrosesan sebelumnya belum dapat dipastikan. Jawaban tetap tersimpan; hubungi pengelola untuk melanjutkan.') from exc
        except GraphBusy as exc:
            raise HTTPException(409, 'Jawaban masih diproses. Tunggu sebentar, lalu kirim ulang jawaban yang sama.') from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, 'Waktu tunggu AI habis. Kirim ulang jawaban yang sama; bagian yang sudah tersimpan akan digunakan kembali.') from exc
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc
    async with local_lock(('answer', sid)):
        try:
            return await _process_answer(sid, *args, **kwargs)
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, 'Waktu tunggu tanggapan AI habis. Coba kirim ulang jawaban yang sama.') from exc
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc


async def _process_answer(sid, owner_id, question_id, content, filename, duration_ms, retry_count, think_ms, timed_out, events=None, skip=False, interruption_id=None, text_answer=None, capture_token=None, corrected_transcript=None):
    # Row lock spans provider work: one turn at a time, also across web processes in PostgreSQL.
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid, InterviewSession.user_id == owner_id).with_for_update())
        if not session or session.status != 'running':
            raise HTTPException(409, 'Sesi tidak aktif.')
        questions, answers = await turns(db, session)
        existing = next((a for a in answers if a.question_id == question_id), None)
        if existing:
            return existing.result_payload
        retry_limit = session.script.get('settings', {}).get('retry_limit', 2)
        capture = verify_capture(capture_token, session, question_id) if capture_token else None
        if capture:
            duration_ms = capture['duration_ms']
        if retry_count > retry_limit:
            raise HTTPException(422, f'Maksimal {retry_limit} kali rekam ulang untuk sesi ini.')
        # Allow a small browser scheduling/encoder delay at the time limit.
        if duration_ms > (session.answer_seconds + 2) * 1000:
            raise HTTPException(422, f'Durasi jawaban melebihi batas sesi ({session.answer_seconds} detik).')
        answered = {a.question_id for a in answers}
        current = next((q for q in questions if q.id not in answered), None)
        if not current or current.id != question_id:
            raise HTTPException(409, 'Jawab pertanyaan aktif terlebih dahulu.')
        interrupted = session.script.get('checkpoint', {})
        if interrupted.get('phase') == 'interrupted':
            if not skip or interruption_id != interrupted.get('interruption_id'):
                raise HTTPException(409, 'Pertanyaan terhenti. Pilih Retry atau Next.')
        elif skip:
            raise HTTPException(409, 'Pertanyaan tidak sedang terhenti.')
        transcript = ('' if skip else (corrected_transcript if corrected_transcript is not None else capture['transcript']) if capture
                      else text_answer if text_answer is not None else await speech.transcribe(content, filename, session.script['settings']['language']))
        if not transcript and not skip:
            raise HTTPException(422, 'Ucapan tidak terdeteksi. Rekam ulang jawaban.')
        if events:
            await events.put({'type': 'transcript', 'transcript': transcript})
        allow = current.kind == 'main' and sum(q.kind != 'main' for q in questions) < session.max_followups
        is_last = current.main_order == session.question_count
        persona = guidebook.speaker(session, current.main_order)
        conversation = memory.dialogue(session, questions, answers, current, transcript)
        context_packet = memory.packet(session, conversation, current, persona)
        deadline = asyncio.get_running_loop().time() + settings.respond_timeout_sec
        response = {'action': 'next', 'response_text': 'Pertanyaan dilewati.' if session.script['settings']['language'] == 'id' else 'Question skipped.'} if skip else await asyncio.wait_for(orchestrator.respond({**guidebook.context_for(session, persona),
            'question': current.question_text, 'context_packet': context_packet,
            'expected_points': current.expected_points, 'interviewer': persona, 'job_role': session.job_role,
            'language': session.script['settings']['language'], 'allow_followup': allow, 'is_last': is_last}),
            timeout=settings.respond_timeout_sec)
        action = response['action']
        text = response['response_text']
        if action != 'next' and (not allow or (persona == 'hr' and forbidden_hr(text))):
            action = 'next'
            text = 'Terima kasih atas jawaban Anda.' if session.script['settings']['language'] == 'id' else 'Thank you for your answer.'
        if action == 'next':
            # Avoid leaving a second, untracked question in a transition.
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s for s in sentences if '?' not in s and not re.search(r'(pertanyaan (berikut|selanjut)|next question|let.s move|mari (lanjut|beralih))', s, re.I)]
            text = ' '.join(sentences).strip() or ('Terima kasih.' if session.script['settings']['language'] == 'id' else 'Thank you.')
        audio_name = f'r_{uuid4().hex}.mp3'
        streaming_voice = session.script.get('settings', {}).get('streaming_voice', False)
        audio_url = None if skip or streaming_voice else await speech.optional_synthesize(text, persona, sid, audio_name, live=True,
            timeout=min(settings.tts_live_timeout_sec, max(0, deadline - asyncio.get_running_loop().time())))
        # A close request must win if the user leaves during STT/LLM/TTS.
        await db.refresh(session)
        if session.status != 'running':
            raise HTTPException(409, 'Sesi telah ditutup.')
        follow = None
        next_q = None
        if action != 'next':
            follow = InterviewQuestion(session_id=session.id, kind='follow_up', main_order=current.main_order,
                parent_question_id=current.id, slot=current.slot, category=current.category, question_text=text,
                expected_points=current.expected_points, competencies=current.competencies, audio_file=audio_name if audio_url else None)
            db.add(follow)
            await db.flush()
        else:
            next_q = next((q for q in questions if q.kind == 'main' and q.main_order == current.main_order + 1), None)
            if next_q and session.script.get('settings', {}).get('dynamic_questions'):
                next_persona = guidebook.speaker(session, next_q.main_order)
                planned = {key: getattr(next_q, key) for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies')}
                dynamic_context = {**guidebook.context_for(session, next_persona), 'planned_question': planned,
                    'intent': session.script.get('question_plan', {}).get(str(next_q.main_order), {}),
                    'context_packet': memory.packet(session, conversation, next_q, next_persona),
                    'asked_questions': [item['question'] for item in conversation]}
                # Skipping supplies no new answer to adapt to; the grounded plan remains usable during outages.
                revised = planned if skip else await asyncio.wait_for(orchestrator.adapt_question(dynamic_context),
                    timeout=max(0, deadline - asyncio.get_running_loop().time()))
                revised_audio = f'q{next_q.main_order}_{uuid4().hex}.mp3'
                revised_url = None if streaming_voice else await speech.optional_synthesize(revised['question_text'], next_persona, sid, revised_audio, live=True,
                    timeout=min(settings.tts_live_timeout_sec, max(0, deadline - asyncio.get_running_loop().time())))
                # Do not commit an adaptation if the candidate has closed the room meanwhile.
                await db.refresh(session)
                if session.status != 'running':
                    raise HTTPException(409, 'Sesi telah ditutup.')
                for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies'):
                    setattr(next_q, key, revised[key])
                next_q.audio_file = revised_audio if revised_url else None
                provenance = {**session.script.get('question_provenance', {}), str(next_q.main_order): {
                    'anchor_id': revised.get('anchor_id', ''), 'adapted_after_question_id': current.id,
                    'conversation_turns': len(conversation), 'interviewer': next_persona,
                    'source_refs': revised.get('source_refs', [])}}
                session.script = {**session.script, 'question_provenance': provenance}
        last = action == 'next' and next_q is None
        answer = InterviewAnswer(question_id=question_id, transcript=transcript, duration_sec=duration_ms / 1000,
            wpm=0 if text_answer is not None else round(len(transcript.split()) / max(duration_ms / 60000, .01)),
            filler_count=len(re.findall(r'\b(um|uh|eh|eee|hmm)\b', transcript, re.I)),
            retry_count=retry_count, timed_out=timed_out, think_sec=think_ms / 1000, response_action=action, response_text=text)
        db.add(answer)
        await db.flush()
        if streaming_voice and not skip:
            audio_url = f'/api/sessions/{sid}/speech/response/{answer.id}'
        result = {'answer_id': answer.id, 'transcript': transcript, 'action': action, 'response_text': text,
            'turn_id': f'q{current.id}', 'skipped': skip, 'input_mode': 'realtime' if capture else 'text' if text_answer is not None else 'skipped' if skip else 'audio',
            'source_refs': response.get('source_refs', []),
            'response_interviewer': persona,
            'response_audio_url': audio_url, 'follow_up_question': public_question(follow, session),
            'next_question': public_question(next_q, session), 'is_last': last, 'closing': session.script['closing'] if last else None}
        answer.result_payload = result
        if capture:
            answer.result_payload = {**result, 'original_transcript':capture['transcript'], 'transcript_corrected':transcript != capture['transcript'],
                'capture_model':capture['model'], 'capture_item_ids':capture['item_ids']}
            if transcript != capture['transcript']:
                await record(db, session, f'corrected:{current.id}', 'transcript_corrected', {'question_id':current.id,'answer_id':answer.id})
        target = follow or next_q
        checkpoint(session, 'closing' if last else 'question_ready', target,
                   active_panelist=guidebook.speaker(session, target.main_order) if target else persona,
                   remaining_seconds=session.answer_seconds if target else 0, interruption_id=None)
        await record(db, session, f'answer:{current.id}', 'question_skipped' if skip else 'answer_completed',
                     {'turn_id': f'q{current.id}', 'question_id': current.id, 'answer_id': answer.id,
                      'source_refs': response.get('source_refs', []), 'memory_version': memory.VERSION})
        if target and guidebook.speaker(session, target.main_order) != persona:
            await record(db, session, f'handoff:{current.id}', 'panelist_handoff',
                         {'from': persona, 'to': guidebook.speaker(session, target.main_order), 'question_id': target.id})
        await db.commit()
        return answer.result_payload


@router.post('/api/sessions/{sid}/answers')
async def answer(sid: str, request: Request, question_id: int = Form(...), audio: Optional[UploadFile] = File(None),
    text_answer: Optional[str] = Form(None, min_length=1, max_length=8000),
    capture_token: Optional[str] = Form(None, max_length=50000), corrected_transcript: Optional[str] = Form(None, min_length=1, max_length=8000),
    duration_ms: int = Form(..., ge=100, le=302000), retry_count: int = Form(0, ge=0, le=10),
    think_ms: int = Form(0, ge=0, le=3600000), timed_out: bool = Form(False), stream: bool = False,
    session=Depends(owned_session)):
    if session.status != 'running':
        raise HTTPException(409, 'Sesi tidak aktif.')
    if sum(x is not None for x in (text_answer, audio, capture_token)) != 1 or (text_answer is not None and not text_answer.strip()):
        raise HTTPException(422, 'Kirim salah satu: audio atau jawaban teks yang terisi.')
    if corrected_transcript is not None and (not capture_token or not corrected_transcript.strip()):
        raise HTTPException(422, 'Koreksi memerlukan transkrip realtime yang valid.')
    content = await audio.read(25 * 1024 * 1024 + 1) if audio else b''
    if text_answer is None and capture_token is None and (not content or len(content) > 25 * 1024 * 1024):
        raise HTTPException(413, 'Audio wajib diisi dan maksimal 25 MB.')
    extension = ((audio.filename or '') if audio else '').rsplit('.', 1)[-1].lower()
    if text_answer is None and capture_token is None and extension not in ('webm', 'ogg', 'mp4', 'm4a', 'mp3', 'wav'):
        raise HTTPException(422, 'Format audio tidak didukung.')
    args = (sid, session.user_id, question_id, content, f'answer.{extension}', duration_ms, retry_count, think_ms, timed_out)
    if not stream:
        return await process_answer(*args, text_answer=text_answer, capture_token=capture_token, corrected_transcript=corrected_transcript)
    async def generate():
        queue = asyncio.Queue()
        task = asyncio.create_task(process_answer(*args, events=queue, text_answer=text_answer, capture_token=capture_token, corrected_transcript=corrected_transcript))
        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(queue.get(), 1)
                except asyncio.TimeoutError:
                    event = {'type': 'pending'}
                yield json.dumps(event, ensure_ascii=False) + '\n'
            while not queue.empty():
                yield json.dumps(await queue.get(), ensure_ascii=False) + '\n'
            yield json.dumps({'type': 'result', **await task}, ensure_ascii=False) + '\n'
        except Exception as exc:
            yield json.dumps({'type': 'error', 'message': exc.detail if isinstance(exc, HTTPException) else 'Pemrosesan gagal. Coba kirim ulang.',
                              'request_id': request_var.get()}) + '\n'
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(generate(), media_type='application/x-ndjson', headers={'X-Accel-Buffering':'no', 'Cache-Control':'no-store'})


class Interruption(BaseModel):
    question_id: int
    reason: Literal['tab_hidden', 'offline', 'reload', 'device_lost'] = 'reload'


@router.post('/api/sessions/{sid}/interrupt')
async def interrupt(sid: str, data: Interruption, session=Depends(owned_session)):
    async with local_lock(('answer', sid)), SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.id == session.id).with_for_update())
        if session.status != 'running':
            raise HTTPException(409, 'Sesi tidak aktif.')
        questions, answers = await turns(db, session)
        answered = {a.question_id for a in answers}
        current = next((q for q in questions if q.id not in answered), None)
        if not current or current.id != data.question_id:
            return {'already_completed': True, 'state': await state(db, session)}
        prior = session.script.get('checkpoint', {})
        if prior.get('phase') != 'interrupted' or prior.get('question_id') != current.id:
            event_id = uuid4().hex
            session.script = {**session.script, 'voice_lease': {}}
            checkpoint(session, 'interrupted', current, remaining_seconds=0,
                       active_panelist=guidebook.speaker(session, current.main_order), interruption_id=event_id)
            if graph_enabled(session):
                from app.models import GraphTurnInput
                await db.execute(update(GraphTurnInput).where(GraphTurnInput.session_id == session.id,
                    GraphTurnInput.question_id == current.id, GraphTurnInput.status == 'pending').values(status='superseded'))
            await record(db, session, f'interrupt:{event_id}', 'question_interrupted',
                         {'question_id': current.id, 'reason': data.reason})
            await db.commit()
        return {'already_completed': False, 'state': await state(db, session)}


class Recovery(BaseModel):
    question_id: int
    interruption_id: str
    action: Literal['retry', 'next']


@router.post('/api/sessions/{sid}/recover')
async def recover(sid: str, data: Recovery, session=Depends(owned_session)):
    if data.action == 'next':
        return await process_answer(sid, session.user_id, data.question_id, b'', '', 0, 0, 0, True,
                                    skip=True, interruption_id=data.interruption_id)
    async with local_lock(('answer', sid)), SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.id == session.id).with_for_update())
        previous = session.script.get('checkpoint', {})
        if session.status != 'running':
            raise HTTPException(409, 'Sesi tidak aktif.')
        if previous.get('recovered_interruption_id') == data.interruption_id and previous.get('question_id') == data.question_id:
            return await state(db, session)
        if previous.get('phase') != 'interrupted' or previous.get('interruption_id') != data.interruption_id or previous.get('question_id') != data.question_id:
            raise HTTPException(409, 'Status pertanyaan sudah berubah. Muat ulang status sesi.')
        question = await db.get(InterviewQuestion, data.question_id)
        checkpoint(session, 'question_ready', question, remaining_seconds=session.answer_seconds,
                   interruption_id=None, recovered_interruption_id=data.interruption_id)
        await record(db, session, f'retry:{data.interruption_id}', 'question_retried', {'question_id': question.id})
        await db.commit()
        return await state(db, session)


@router.post('/api/sessions/{sid}/finish')
async def finish(session=Depends(owned_session), db=Depends(get_db)):
    if session.status in ('done', 'scoring'):
        return {'status': session.status}
    if session.status not in ('running', 'evaluation_failed'):
        raise HTTPException(409, 'Sesi tidak aktif.')
    questions, answers = await turns(db, session)
    if not questions or len(answers) != len(questions):
        raise HTTPException(409, 'Selesaikan seluruh pertanyaan terlebih dahulu.')
    changed = await db.execute(update(InterviewSession).where(InterviewSession.id == session.id,
        InterviewSession.status.in_(['running', 'evaluation_failed'])).values(status='scoring', error_message=None))
    if changed.rowcount:
        await record(db, session, 'evaluation_requested:' + uuid4().hex, 'evaluation_requested')
    await db.commit()
    if changed.rowcount:
        try:
            await enqueue('finalize_session', session.id)
        except Exception:
            await db.execute(update(InterviewSession).where(InterviewSession.id == session.id, InterviewSession.status == 'scoring').values(
                status='evaluation_failed', error_message='Antrean penilaian tidak tersedia; coba nilai ulang.'))
            await db.commit()
            raise HTTPException(503, 'Antrean penilaian tidak tersedia.')
    return {'status': 'scoring'}


@router.post('/api/sessions/{sid}/retry-preparation')
async def retry_preparation(session=Depends(owned_session), db=Depends(get_db)):
    if not graph_enabled(session) or session.status not in ('preparation_failed', 'preparing'):
        raise HTTPException(409, 'Persiapan sesi tidak dapat diulang.')
    if session.status == 'preparing':
        return {'status': session.status}
    changed = await db.execute(update(InterviewSession).where(InterviewSession.id == session.id,
        InterviewSession.status == 'preparation_failed').values(status='preparing', error_message=None))
    await db.commit()
    if changed.rowcount:
        try:
            await enqueue('prepare_session', session.id)
        except Exception:
            await db.execute(update(InterviewSession).where(InterviewSession.id == session.id,
                InterviewSession.status == 'preparing').values(status='preparation_failed', error_message='Antrean belum tersedia. Coba siapkan ulang.'))
            await db.commit()
            raise HTTPException(503, 'Antrean belum tersedia.')
    return {'status': 'preparing'}


@router.post('/api/sessions/{sid}/close')
async def close(session=Depends(owned_session), db=Depends(get_db)):
    async def commit_close():
        changed = await db.execute(update(InterviewSession).where(InterviewSession.id == session.id,
            InterviewSession.status.in_(['preparing', 'preparation_failed', 'ready', 'running'])).values(
                status='failed', error_message='Sesi diakhiri oleh pengguna.', finished_at=now()))
        if changed.rowcount:
            await record(db, session, 'cancelled', 'session_cancelled')
        await db.commit()
    if graph_enabled(session):
        async with local_lock(('answer', session.uuid)):
            await commit_close()
    else:
        # Legacy holds its answer lock during provider work; close must be able
        # to mark the session before the provider returns and refreshes it.
        await commit_close()
    return {'ok': True}


@router.get('/api/sessions/{sid}/result')
async def result(session=Depends(owned_session), db=Depends(get_db)):
    if session.status != 'done':
        raise HTTPException(409, 'Hasil belum tersedia.')
    questions, answers = await turns(db, session)
    _, competencies = aggregate([a.competency_scores for a in answers], session.script['assessment']['weights'], session.script['assessment'])
    from app.graphs.panel_scoring import result_data
    graph_result = result_data(session) if graph_enabled(session) else None
    if graph_result:
        competencies = graph_result['competencies']
    candidates = (await db.scalars(select(InterviewSession).where(InterviewSession.user_id == session.user_id,
        InterviewSession.job_role == session.job_role, InterviewSession.status == 'done',
        InterviewSession.finished_at < session.finished_at).order_by(InterviewSession.finished_at.desc()).limit(20))).all()
    previous = next((s for s in candidates if s.level == session.level and
        sorted(guidebook.panel_roles(s)) == sorted(guidebook.panel_roles(session)) and
        s.script.get('guidebook', {}).get('sha256') == session.script.get('guidebook', {}).get('sha256') and
        s.script.get('settings', {}).get('evidence_policy') == session.script.get('settings', {}).get('evidence_policy') and
        aggregation_version(s) == aggregation_version(session) and
        s.script.get('assessment', {}).get('sha256') == session.script['assessment'].get('sha256')), None)
    previous_score = previous.total_score if previous else None
    by_id = {a.question_id: a for a in answers}
    from app.ai.scoring import WEIGHTS
    panel_results = []
    for persona in guidebook.panel_roles(session):
        weights = session.script['assessment'].get('persona_weights', {}).get(persona, WEIGHTS[persona])
        scores = [by_id[q.id].competency_scores for q in questions if q.kind == 'main' and q.id in by_id
                  and guidebook.speaker(session, q.main_order) == persona]
        score, measured = aggregate(scores, weights, session.script['assessment'])
        panel_results.append({'interviewer': persona, 'total_score': score, 'competencies': measured})
    if graph_result:
        panel_results = graph_result['panel_results']
    return {'session_id': session.uuid, 'status': 'done', 'job_role': session.job_role, 'level': session.level,
        'panel_results': panel_results,
        'aggregation_policy': session.script.get('runtime', {}).get('aggregation_policy'),
        'coverage': coverage(competencies) if session.script.get('settings', {}).get('evidence_policy') else None,
        'total_score': session.total_score, 'label': label(session.total_score), 'previous_score': previous_score,
        'delta': round(session.total_score - previous_score, 2) if previous_score is not None and session.total_score is not None else None,
        'competencies': competencies, 'unmeasured': [c['key'] for c in competencies if c['score'] is None],
        'review': session.review, 'star_summary': session.star_summary,
        'assessment': {k: session.script['assessment'][k] for k in ('version','sha256','validated','profile_id','title','scope','status','job_reviewed_by_human') if k in session.script['assessment']},
        'items': [{**public_question(q, session), 'transcript': by_id[q.id].transcript,
                   'feedback': by_id[q.id].feedback, 'competency_scores': by_id[q.id].competency_scores,
                   'skipped': by_id[q.id].result_payload.get('skipped', False),
                   'input_mode': by_id[q.id].result_payload.get('input_mode', 'audio'),
                   'wpm': by_id[q.id].wpm, 'filler_count': by_id[q.id].filler_count} for q in questions if q.id in by_id]}


@router.get('/api/sessions/{sid}/audio/{name}')
async def audio_file(name: str, session=Depends(owned_session)):
    path = safe_audio_path(session.uuid, name)
    if not path:
        raise HTTPException(404, 'Audio tidak ditemukan.')
    return FileResponse(path, media_type='audio/mpeg', headers={'Cache-Control':'private, max-age=3600'})
