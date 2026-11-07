import asyncio
import json
import re
from datetime import timedelta
from uuid import uuid4
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, func, update
from app.db import get_db, SessionLocal
from app.deps import current_user, owned_session
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, SessionCompetency, now
from app.ai import speech, orchestrator
from app.ai.assessment import snapshot
from app.ai.blueprint import forbidden_hr
from app.ai.scoring import aggregate, label
from app.config import settings
from app.jobs import enqueue
from app.services.text import validate_text, extract_pdf
from app.services.interview import state, turns, public_question, session_item
from app.storage import safe_audio_path
from app.log import emit
from app.services.locks import local_lock
from app.ai.errors import ProviderError

router = APIRouter()


@router.post('/api/sessions')
async def create_session(candidate_name: str = Form(..., min_length=2, max_length=120), gender: Literal['male', 'female'] = Form(...),
    age: int = Form(..., ge=15, le=80), job_role: str = Form(..., min_length=2, max_length=150),
    level: Literal['junior', 'middle', 'senior', 'manager'] = Form(...), job_description: str = Form(...),
    industry: str = Form(..., min_length=2, max_length=80), company: str = Form('', max_length=150),
    question_count: int = Form(7), interviewer: Literal['hr', 'user', 'manager'] = Form(...),
    language: Literal['id', 'en'] = Form('id'), consent: bool = Form(...), use_last_cv: bool = Form(False),
    cv_text: str = Form(''), cv_pdf: Optional[UploadFile] = File(None), user=Depends(current_user), db=Depends(get_db)):
    if not consent or question_count not in (3, 5, 7):
        raise HTTPException(422, 'Persetujuan wajib; jumlah pertanyaan harus 3, 5, atau 7.')
    cv = user.last_cv_text if use_last_cv else cv_text
    if cv_pdf and cv_pdf.filename:
        cv = await asyncio.to_thread(extract_pdf, await cv_pdf.read(5 * 1024 * 1024 + 1))
    cv = validate_text(cv or '', 'CV')
    jd = validate_text(job_description, 'JD')
    try:
        speech.require_credentials(interviewer)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    # Serialize creation per user in production so the hourly quota cannot race.
    from app.models import User
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = await db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.user_id == user.id, InterviewSession.created_at >= now() - timedelta(hours=1)))
    if count >= settings.max_sessions_per_hour:
        raise HTTPException(429, f'Maksimal {settings.max_sessions_per_hour} sesi per jam. Coba lagi nanti.')
    assessment = snapshot(interviewer)
    session = InterviewSession(user_id=user.id, candidate_name=candidate_name, gender=gender, age=age,
        job_role=job_role, level=level, industry=industry, company=company, job_description=jd, cv_text=cv,
        interviewer=interviewer, question_count=question_count, answer_seconds=settings.answer_seconds_for(level),
        max_followups=settings.followups_for(question_count),
        script={'settings': {'language': language, 'retry_limit': settings.retry_limit}, 'assessment': assessment})
    db.add(session)
    user.last_cv_text = cv
    await db.flush()
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
    await db.execute(update(InterviewSession).where(InterviewSession.id == session.id, InterviewSession.status == 'ready').values(status='running', started_at=now()))
    await db.commit()
    return {'status': 'running'}


async def process_answer(sid, *args, **kwargs):
    async with local_lock(('answer', sid)):
        try:
            return await _process_answer(sid, *args, **kwargs)
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, 'Waktu tunggu tanggapan AI habis. Coba kirim ulang jawaban yang sama.') from exc
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc


async def _process_answer(sid, owner_id, question_id, content, filename, duration_ms, retry_count, think_ms, timed_out, events=None):
    # Row lock spans provider work: one turn at a time, also across web processes in PostgreSQL.
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid, InterviewSession.user_id == owner_id).with_for_update())
        if not session or session.status != 'running':
            raise HTTPException(409, 'Sesi tidak aktif.')
        retry_limit = session.script.get('settings', {}).get('retry_limit', 2)
        if retry_count > retry_limit:
            raise HTTPException(422, f'Maksimal {retry_limit} kali rekam ulang untuk sesi ini.')
        # Allow a small browser scheduling/encoder delay at the time limit.
        if duration_ms > (session.answer_seconds + 2) * 1000:
            raise HTTPException(422, f'Durasi jawaban melebihi batas sesi ({session.answer_seconds} detik).')
        questions, answers = await turns(db, session)
        existing = next((a for a in answers if a.question_id == question_id), None)
        if existing:
            return existing.result_payload
        answered = {a.question_id for a in answers}
        current = next((q for q in questions if q.id not in answered), None)
        if not current or current.id != question_id:
            raise HTTPException(409, 'Jawab pertanyaan aktif terlebih dahulu.')
        transcript = await speech.transcribe(content, filename, session.script['settings']['language'])
        if not transcript:
            raise HTTPException(422, 'Ucapan tidak terdeteksi. Rekam ulang jawaban.')
        if events:
            await events.put({'type': 'transcript', 'transcript': transcript})
        group = [a.transcript for a in answers if any(q.id == a.question_id and q.main_order == current.main_order for q in questions)] + [transcript]
        allow = current.kind == 'main' and sum(q.kind != 'main' for q in questions) < session.max_followups
        is_last = current.main_order == session.question_count
        deadline = asyncio.get_running_loop().time() + settings.respond_timeout_sec
        response = await asyncio.wait_for(orchestrator.respond({'question': current.question_text, 'transcripts': group,
            'expected_points': current.expected_points, 'interviewer': session.interviewer, 'job_role': session.job_role,
            'language': session.script['settings']['language'], 'allow_followup': allow, 'is_last': is_last}),
            timeout=settings.respond_timeout_sec)
        action = response['action']
        text = response['response_text']
        if action != 'next' and (not allow or (session.interviewer == 'hr' and forbidden_hr(text))):
            action = 'next'
            text = 'Terima kasih atas jawaban Anda.' if session.script['settings']['language'] == 'id' else 'Thank you for your answer.'
        if action == 'next':
            # Avoid leaving a second, untracked question in a transition.
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s for s in sentences if '?' not in s and not re.search(r'(pertanyaan (berikut|selanjut)|next question|let.s move|mari (lanjut|beralih))', s, re.I)]
            text = ' '.join(sentences).strip() or ('Terima kasih.' if session.script['settings']['language'] == 'id' else 'Thank you.')
        audio_name = f'r_{uuid4().hex}.mp3'
        audio_url = await asyncio.wait_for(speech.synthesize(text, session.interviewer, sid, audio_name, live=True),
            timeout=max(0, deadline - asyncio.get_running_loop().time()))
        # A close request must win if the user leaves during STT/LLM/TTS.
        await db.refresh(session)
        if session.status != 'running':
            raise HTTPException(409, 'Sesi telah ditutup.')
        follow = None
        next_q = None
        if action != 'next':
            follow = InterviewQuestion(session_id=session.id, kind='follow_up', main_order=current.main_order,
                parent_question_id=current.id, slot=current.slot, category=current.category, question_text=text,
                expected_points=current.expected_points, competencies=current.competencies, audio_file=audio_name)
            db.add(follow)
            await db.flush()
        else:
            next_q = next((q for q in questions if q.kind == 'main' and q.main_order == current.main_order + 1), None)
        last = action == 'next' and next_q is None
        answer = InterviewAnswer(question_id=question_id, transcript=transcript, duration_sec=duration_ms / 1000,
            wpm=round(len(transcript.split()) / max(duration_ms / 60000, .01)),
            filler_count=len(re.findall(r'\b(um|uh|eh|eee|hmm)\b', transcript, re.I)),
            retry_count=retry_count, timed_out=timed_out, think_sec=think_ms / 1000, response_action=action, response_text=text)
        db.add(answer)
        await db.flush()
        result = {'answer_id': answer.id, 'transcript': transcript, 'action': action, 'response_text': text,
            'response_audio_url': audio_url, 'follow_up_question': public_question(follow, session),
            'next_question': public_question(next_q, session), 'is_last': last, 'closing': session.script['closing'] if last else None}
        answer.result_payload = result
        await db.commit()
        return result


@router.post('/api/sessions/{sid}/answers')
async def answer(sid: str, request: Request, question_id: int = Form(...), audio: UploadFile = File(...),
    duration_ms: int = Form(..., ge=100, le=302000), retry_count: int = Form(0, ge=0, le=10),
    think_ms: int = Form(0, ge=0, le=3600000), timed_out: bool = Form(False), stream: bool = False,
    session=Depends(owned_session)):
    if session.status != 'running':
        raise HTTPException(409, 'Sesi tidak aktif.')
    content = await audio.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, 'Audio wajib diisi dan maksimal 25 MB.')
    extension = (audio.filename or '').rsplit('.', 1)[-1].lower()
    if extension not in ('webm', 'ogg', 'mp4', 'm4a', 'mp3', 'wav'):
        raise HTTPException(422, 'Format audio tidak didukung.')
    args = (sid, session.user_id, question_id, content, f'answer.{extension}', duration_ms, retry_count, think_ms, timed_out)
    if not stream:
        return await process_answer(*args)
    async def generate():
        queue = asyncio.Queue()
        task = asyncio.create_task(process_answer(*args, events=queue))
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
            emit('answer_failed', error_type=type(exc).__name__)
            yield json.dumps({'type': 'error', 'message': exc.detail if isinstance(exc, HTTPException) else 'Pemrosesan gagal. Coba kirim ulang.'}) + '\n'
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(generate(), media_type='application/x-ndjson', headers={'X-Accel-Buffering':'no', 'Cache-Control':'no-store'})


@router.post('/api/sessions/{sid}/finish')
async def finish(session=Depends(owned_session), db=Depends(get_db)):
    if session.status in ('done', 'scoring'):
        return {'status': session.status}
    if session.status != 'running':
        raise HTTPException(409, 'Sesi tidak aktif.')
    questions, answers = await turns(db, session)
    if not questions or len(answers) != len(questions):
        raise HTTPException(409, 'Selesaikan seluruh pertanyaan terlebih dahulu.')
    changed = await db.execute(update(InterviewSession).where(InterviewSession.id == session.id, InterviewSession.status == 'running').values(status='scoring'))
    await db.commit()
    if changed.rowcount:
        try:
            await enqueue('finalize_session', session.id)
        except Exception:
            from app.worker.tasks import fail
            await fail(session.id, 'Antrean penilaian')
            raise HTTPException(503, 'Antrean penilaian tidak tersedia.')
    return {'status': 'scoring'}


@router.post('/api/sessions/{sid}/close')
async def close(session=Depends(owned_session), db=Depends(get_db)):
    await db.execute(update(InterviewSession).where(InterviewSession.id == session.id,
        InterviewSession.status.in_(['ready', 'running'])).values(status='failed', error_message='Sesi ditutup karena halaman ditinggalkan.', finished_at=now()))
    await db.commit()
    return {'ok': True}


@router.get('/api/sessions/{sid}/result')
async def result(session=Depends(owned_session), db=Depends(get_db)):
    if session.status != 'done':
        raise HTTPException(409, 'Hasil belum tersedia.')
    questions, answers = await turns(db, session)
    _, competencies = aggregate([a.competency_scores for a in answers], session.script['assessment']['weights'])
    previous = await db.scalar(select(InterviewSession).where(InterviewSession.user_id == session.user_id,
        InterviewSession.job_role == session.job_role, InterviewSession.status == 'done',
        InterviewSession.finished_at < session.finished_at).order_by(InterviewSession.finished_at.desc()).limit(1))
    previous_score = previous.total_score if previous else None
    by_id = {a.question_id: a for a in answers}
    return {'session_id': session.uuid, 'status': 'done', 'job_role': session.job_role, 'level': session.level,
        'total_score': session.total_score, 'label': label(session.total_score), 'previous_score': previous_score,
        'delta': round(session.total_score - previous_score, 2) if previous_score is not None and session.total_score is not None else None,
        'competencies': competencies, 'unmeasured': [c['key'] for c in competencies if c['score'] is None],
        'review': session.review, 'star_summary': session.star_summary,
        'assessment': {k: session.script['assessment'][k] for k in ('version','sha256','validated')},
        'items': [{**public_question(q, session), 'transcript': by_id[q.id].transcript,
                   'feedback': by_id[q.id].feedback, 'competency_scores': by_id[q.id].competency_scores,
                   'wpm': by_id[q.id].wpm, 'filler_count': by_id[q.id].filler_count} for q in questions if q.id in by_id]}


@router.get('/api/sessions/{sid}/audio/{name}')
async def audio_file(name: str, session=Depends(owned_session)):
    path = safe_audio_path(session.uuid, name)
    if not path:
        raise HTTPException(404, 'Audio tidak ditemukan.')
    return FileResponse(path, media_type='audio/mpeg', headers={'Cache-Control':'private, max-age=3600'})
