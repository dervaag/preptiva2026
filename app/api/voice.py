import asyncio
import json
import time
from datetime import timedelta
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.ai import realtime, speech, guidebook
from app.config import settings
from app.db import SessionLocal, get_db
from app.deps import owned_session
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, now
from app.services.interview import turns
from app.services.events import record
from app.services.voice_capture import seal
from app.log import emit
from app.services.auth_sessions import resolve_user
from app.services.http_security import trusted_browser_origin
from app.storage import SessionStorageDeleted

router = APIRouter()


def same_origin(socket):
    return (socket.headers.get('sec-fetch-site') != 'cross-site'
            and trusted_browser_origin(socket, socket.headers.get('origin', '')))


async def check_turn(db, sid, owner, qid):
    session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid,
        InterviewSession.user_id == owner).with_for_update())
    if not session or session.status != 'running' or session.script.get('checkpoint', {}).get('phase') == 'interrupted':
        raise ValueError('Pertanyaan tidak aktif.')
    questions, answers = await turns(db, session)
    answered = {a.question_id for a in answers}
    current = next((q for q in questions if q.id not in answered), None)
    if not current or current.id != qid:
        raise ValueError('Pertanyaan tidak aktif.')
    return session


@router.websocket('/api/sessions/{sid}/voice/{qid}')
async def capture(socket: WebSocket, sid: str, qid: int):
    if not same_origin(socket) or not settings.realtime_voice_enabled:
        await socket.close(code=1008)
        return
    async with SessionLocal() as db:
        user = await resolve_user(socket, db)
        owner = user.id if user else None
    if owner is None:
        await socket.close(code=1008)
        return
    lease, started, session = uuid4().hex, time.monotonic(), None
    accepted = False
    try:
        async with SessionLocal() as db:
            session = await check_turn(db, sid, owner, qid)
            current_lease = session.script.get('voice_lease', {})
            if current_lease.get('until', '') > now().isoformat():
                raise ValueError('Mikrofon realtime sesi ini sedang dipakai.')
            session.script = {**session.script, 'voice_lease': {'id': lease,
                'until': (now()+timedelta(seconds=session.answer_seconds+45)).isoformat()}}
            await db.commit()
        await socket.accept(); accepted = True
        async with realtime.connection(session.script['settings']['language']) as upstream:
            transcript = realtime.Transcript()
            updated, committed = asyncio.Event(), asyncio.Event()
            count = 0
            finishing = False
            async def read_provider():
                async for raw in upstream:
                    event = json.loads(raw)
                    kind = event.get('type', '')
                    if kind == 'session.updated':
                        updated.set()
                    elif kind == 'input_audio_buffer.committed':
                        committed.set()
                    elif kind == 'error':
                        if finishing and event.get('error', {}).get('code') == 'input_audio_buffer_commit_empty':
                            committed.set()
                            continue
                        raise RuntimeError('Realtime provider rejected audio.')
                    elif kind == 'conversation.item.input_audio_transcription.failed':
                        raise RuntimeError('Realtime transcription failed.')
                    transcript.feed(event)
                    if kind in ('input_audio_buffer.speech_started', 'input_audio_buffer.speech_stopped'):
                        await socket.send_json({'type': 'speech_started' if kind.endswith('started') else 'speech_stopped'})
                    if kind in ('conversation.item.input_audio_transcription.delta', 'conversation.item.input_audio_transcription.completed'):
                        await socket.send_json({'type': 'transcript_delta', 'transcript': transcript.text()})
                raise RuntimeError('Realtime connection ended early.')

            async def receive_audio():
                nonlocal count, finishing
                await socket.send_json({'type':'ready','sample_rate':24000,'silence_ms':settings.vad_silence_ms})
                while True:
                    message = await socket.receive()
                    if message['type'] == 'websocket.disconnect':
                        raise WebSocketDisconnect()
                    pcm = message.get('bytes')
                    if pcm is not None:
                        if not pcm or len(pcm) % 2 or len(pcm) > 48000:
                            raise ValueError('Paket audio tidak valid.')
                        count += len(pcm)
                        if count > (session.answer_seconds+2)*48000:
                            raise ValueError('Batas waktu jawaban tercapai.')
                        await realtime.append(upstream, pcm)
                        continue
                    if len(message.get('text') or '') > 100:
                        raise ValueError('Pesan realtime tidak valid.')
                    action = json.loads(message.get('text') or '{}').get('type')
                    if action == 'cancel':
                        return None
                    if action != 'finish' or count < 4800:
                        raise ValueError('Audio terlalu singkat atau perintah tidak valid.')
                    finishing = True
                    # Disable VAD and await its acknowledgement before a final explicit commit.
                    # The acknowledgement is a barrier for earlier automatic commit events.
                    updated.clear()
                    await upstream.send(json.dumps(realtime.configuration(session.script['settings']['language'], vad=False)))
                    await asyncio.wait_for(updated.wait(), 10)
                    committed.clear()
                    await upstream.send(json.dumps({'type':'input_audio_buffer.commit'}))
                    await asyncio.wait_for(committed.wait(), 10)
                    deadline = time.monotonic()+20
                    while not transcript.complete():
                        if time.monotonic() > deadline:
                            raise RuntimeError('Transkripsi belum selesai.')
                        await asyncio.sleep(.05)
                    text = transcript.text()
                    if not text:
                        raise ValueError('Ucapan belum terdeteksi; coba rekam ulang atau gunakan teks.')
                    duration = round(count/48)
                    async with SessionLocal() as db:
                        if await resolve_user(socket, db, touch=False) is None:
                            raise ValueError('Login sudah berakhir.')
                        current = await check_turn(db, sid, owner, qid)
                        if current.script.get('voice_lease', {}).get('id') != lease:
                            raise ValueError('Percobaan rekaman sudah berubah.')
                        token = seal(current, qid, text, duration, transcript.order)
                        current.script = {**current.script, 'voice_lease': {}}
                        await record(db, current, 'voice:'+lease, 'voice_transcribed',
                            {'question_id':qid,'duration_ms':duration,'model':settings.stt_model,'segments':len(transcript.order)})
                        await db.commit()
                    await socket.send_json({'type':'transcript_final','transcript':text,'capture_token':token,'duration_ms':duration})
                    return text

            async def watch_turn():
                while True:
                    await asyncio.sleep(2)
                    async with SessionLocal() as db:
                        if await resolve_user(socket, db, touch=False) is None:
                            raise ValueError('Login sudah berakhir.')
                        stored = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid))
                        if (not stored or stored.status != 'running'
                                or stored.script.get('checkpoint', {}).get('phase') == 'interrupted'
                                or stored.script.get('voice_lease', {}).get('id') != lease):
                            raise ValueError('Pertanyaan sudah dihentikan.')

            tasks = [asyncio.create_task(fn()) for fn in (read_provider, receive_audio, watch_turn)]
            try:
                done, _ = await asyncio.wait(tasks, timeout=session.answer_seconds+40, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    raise TimeoutError()
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:
        emit('realtime_failed', error_type=type(exc).__name__)
        if accepted:
            try:
                await socket.send_json({'type':'error','message':'Suara realtime belum tersedia. Gunakan rekaman biasa atau jawaban teks.'})
            except Exception:
                pass
    finally:
        if session is not None:
            async with SessionLocal() as db:
                stored = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid,
                    InterviewSession.user_id == owner).with_for_update())
                if stored and stored.script.get('voice_lease', {}).get('id') == lease:
                    stored.script = {**stored.script, 'voice_lease': {}}
                    await db.commit()
        try:
            await socket.close()
        except RuntimeError:
            pass
        emit('realtime_closed', ms=round((time.monotonic()-started)*1000))


@router.get('/api/sessions/{sid}/speech/{kind}/{item_id}')
async def stream_speech(kind: str, item_id: int, session=Depends(owned_session), db=Depends(get_db)):
    if kind == 'language':
        from app.ai.answer_language import retry_message
        questions, answers = await turns(db, session)
        answered = {a.question_id for a in answers}
        current = next((q for q in questions if q.id not in answered), None)
        if session.status != 'running' or not current or current.id != item_id:
            raise HTTPException(404, 'Pertanyaan tidak tersedia.')
        text = retry_message(session.script['settings']['language'])
        persona = guidebook.speaker(session, current.main_order)
    elif kind == 'question':
        question = await db.scalar(select(InterviewQuestion).where(InterviewQuestion.id == item_id, InterviewQuestion.session_id == session.id))
        questions, answers = await turns(db, session)
        answered = {a.question_id for a in answers}
        current = next((q for q in questions if q.id not in answered), None)
        if not question or (question.id not in answered and (not current or current.id != question.id)):
            raise HTTPException(404, 'Pertanyaan tidak tersedia.')
        text, persona = question.question_text, guidebook.speaker(session, question.main_order)
    elif kind == 'response':
        result = (await db.execute(select(InterviewAnswer, InterviewQuestion).join(InterviewQuestion).where(
            InterviewAnswer.id == item_id, InterviewQuestion.session_id == session.id))).first()
        if not result:
            raise HTTPException(404, 'Tanggapan tidak tersedia.')
        answer, question = result
        text, persona = answer.response_text, guidebook.speaker(session, question.main_order)
    elif kind in ('intro','closing') and item_id == 0:
        from app.ai.closing import public_closing
        text = public_closing(session).get('text', '') if kind == 'closing' else session.script.get(kind, {}).get('text', '')
        if not text:
            raise HTTPException(404, 'Suara tidak tersedia.')
        persona = guidebook.panel_roles(session)[0] if kind == 'intro' else guidebook.speaker(session, session.question_count)
    else:
        raise HTTPException(404, 'Suara tidak tersedia.')
    if len(text) > 6000:
        raise HTTPException(422, 'Teks suara terlalu panjang.')
    try:
        cache = speech.stream_cache(text, persona, session.uuid)
    except SessionStorageDeleted:
        raise HTTPException(404, 'Suara tidak tersedia.')
    if settings.tts_cache and cache.exists():
        return FileResponse(cache, media_type='audio/mpeg',headers={'Cache-Control':'private, no-store'})
    return StreamingResponse(speech.stream_audio(text, persona, session.uuid),media_type='audio/mpeg',
        headers={'Cache-Control':'private, no-store','X-Accel-Buffering':'no'})


class Latency(BaseModel):
    answer_id: int
    elapsed_ms: int = Field(ge=0, le=300000)


@router.post('/api/sessions/{sid}/voice-latency')
async def voice_latency(data: Latency, session=Depends(owned_session), db=Depends(get_db)):
    answer = await db.scalar(select(InterviewAnswer).join(InterviewQuestion).where(
        InterviewAnswer.id == data.answer_id, InterviewQuestion.session_id == session.id))
    if not answer:
        raise HTTPException(404, 'Jawaban tidak ditemukan.')
    # Serialize duplicate playback telemetry; metrics do not affect scores.
    session = await db.scalar(select(InterviewSession).where(InterviewSession.id == session.id).with_for_update())
    await record(db, session, f'latency:{answer.id}', 'voice_first_playing', {'answer_id':answer.id,
        'elapsed_ms':data.elapsed_ms,'source':'browser_candidate_end_to_audio_playing'})
    await db.commit()
    return {'ok':True}
