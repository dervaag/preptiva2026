"""A durable answer graph. Browser interruptions remain explicit domain transitions."""
from app.ai.closing import public_closing
import asyncio
import hashlib
import json
import re
from fastapi import HTTPException
from sqlalchemy import select
from app.db import SessionLocal
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, GraphTurnInput
from app.ai import guidebook, memory, orchestrator, speech
from app.config import settings
from app.services.events import record, checkpoint
from app.services.interview import turns, public_question
from app.services.voice_capture import verify as verify_capture
from app.services.locks import local_lock
from app.graphs.coordinator import coordinate, apply_selection
from app.graphs.runtime import execute


def thread_key(session_id, question_id, attempt, input_hash):
    return f'turn:{session_id}:{question_id}:{attempt}:{input_hash[:20]}:v1'


def _attempt(session, skip=False, interruption_id=None):
    point = session.script.get('checkpoint', {})
    return 'skip-' + interruption_id if skip and interruption_id else point.get('recovered_interruption_id') or 'initial'


def _active(session, questions, answers, question_id, attempt, skip=False, interruption_id=None):
    if not session or session.status != 'running':
        raise HTTPException(409, 'Sesi tidak aktif.')
    answered = {a.question_id for a in answers}
    current = next((q for q in questions if q.id not in answered), None)
    if not current or current.id != question_id:
        raise HTTPException(409, 'Pertanyaan aktif sudah berubah.')
    point = session.script.get('checkpoint', {})
    if point.get('phase') == 'interrupted':
        if not skip or point.get('interruption_id') != interruption_id:
            raise HTTPException(409, 'Pertanyaan terhenti. Pilih Retry atau Next.')
    elif skip:
        raise HTTPException(409, 'Pertanyaan tidak sedang terhenti.')
    if attempt != _attempt(session, skip, interruption_id):
        raise HTTPException(409, 'Percobaan jawaban sudah berakhir. Gunakan pertanyaan aktif.')
    return current


async def process(sid, owner_id, question_id, content=b'', filename='', duration_ms=0,
                  retry_count=0, think_ms=0, timed_out=False, events=None, skip=False,
                  interruption_id=None, text_answer=None, capture_token=None,
                  corrected_transcript=None, *, resume_input_id=None, allow_uncertain=False):
    supplied_hash = None if resume_input_id else hashlib.sha256(json.dumps({
        'audio': hashlib.sha256(content).hexdigest(), 'text': text_answer, 'capture': capture_token,
        'corrected': corrected_transcript, 'skip': skip, 'duration': duration_ms,
        'retry': retry_count, 'think': think_ms, 'timed_out': timed_out}, sort_keys=True).encode()).hexdigest()
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.uuid == sid, InterviewSession.user_id == owner_id))
        if not session:
            raise HTTPException(404, 'Sesi tidak ditemukan.')
        questions, answers = await turns(db, session)
        existing = next((a for a in answers if a.question_id == question_id), None)
        if existing and resume_input_id is None:
            committed = await db.scalar(select(GraphTurnInput).where(GraphTurnInput.question_id == question_id,
                GraphTurnInput.status == 'completed'))
            if committed and supplied_hash != committed.input_hash:
                raise HTTPException(409, 'Pertanyaan ini sudah memiliki jawaban tersimpan yang berbeda.')
            return existing.result_payload
        saved = await db.get(GraphTurnInput, resume_input_id) if resume_input_id else None
        if saved and (saved.session_id != session.id or saved.question_id != question_id):
            raise HTTPException(409, 'Referensi jawaban tidak sesuai sesi.')
        if saved:
            skip = saved.payload['skip']; interruption_id = saved.payload.get('interruption_id')
        attempt = saved.attempt if saved else _attempt(session, skip, interruption_id)
        if not existing:
            _active(session, questions, answers, question_id, attempt, skip, interruption_id)
        session_id = session.id
    effective_hash = saved.input_hash if saved else supplied_hash
    run_key = thread_key(session_id, question_id, attempt, effective_hash)

    async def load(db, *, lock=False):
        query = select(InterviewSession).where(InterviewSession.id == session_id)
        session = await db.scalar(query.with_for_update() if lock else query)
        questions, answers = await turns(db, session)
        saved = await db.scalar(select(GraphTurnInput).where(GraphTurnInput.question_id == question_id, GraphTurnInput.attempt == attempt))
        return session, questions, answers, saved

    async def accept_transcript(ctx):
        async with SessionLocal() as db:
            session, questions, answers, saved = await load(db)
            if saved:
                if supplied_hash and saved.input_hash != supplied_hash:
                    raise HTTPException(409, 'Jawaban sudah tersimpan. Kirim ulang jawaban yang sama untuk melanjutkan proses.')
                if events:
                    await events.put({'type': 'transcript', 'transcript': saved.payload['transcript']})
                return {'input_id': saved.id}
            _active(session, questions, answers, question_id, attempt, skip, interruption_id)
            if resume_input_id:
                raise HTTPException(409, 'Transkrip belum tersimpan. Kirim ulang rekaman dari browser.')
            capture = verify_capture(capture_token, session, question_id) if capture_token else None
            duration = capture['duration_ms'] if capture else duration_ms
            if retry_count > session.script['settings'].get('retry_limit', 2) or duration > (session.answer_seconds + 2) * 1000:
                raise HTTPException(422, 'Batas durasi atau rekam ulang sesi terlampaui.')
            language = session.script['settings']['language']
        if skip:
            transcript = ''
        elif capture:
            transcript = corrected_transcript if corrected_transcript is not None else capture['transcript']
        elif text_answer is not None:
            transcript = text_answer
        else:
            transcript = await ctx.operation('transcription', {'audio_sha256': hashlib.sha256(content).hexdigest(),
                'filename': filename, 'language': language, 'model': settings.stt_model},
                lambda: speech.transcribe(content, filename, language), paid=True)
        if not transcript.strip() and not skip:
            raise HTTPException(422, 'Ucapan tidak terdeteksi. Rekam ulang jawaban.')
        payload = {'transcript': transcript, 'duration_ms': duration, 'retry_count': retry_count,
            'think_ms': think_ms, 'timed_out': timed_out, 'skip': skip, 'interruption_id': interruption_id,
            'input_mode': 'skipped' if skip else 'realtime' if capture else 'text' if text_answer is not None else 'audio'}
        if capture:
            payload.update(original_transcript=capture['transcript'], transcript_corrected=transcript != capture['transcript'],
                capture_model=capture['model'], capture_item_ids=capture['item_ids'])
        await ctx.assert_owned()
        async with local_lock(('answer', sid)), SessionLocal() as db:
            session, questions, answers, saved = await load(db, lock=True)
            _active(session, questions, answers, question_id, attempt, skip, interruption_id)
            if saved and saved.input_hash != supplied_hash:
                raise HTTPException(409, 'Jawaban sudah tersimpan. Kirim ulang jawaban yang sama untuk melanjutkan proses.')
            if not saved:
                saved = GraphTurnInput(session_id=session_id, question_id=question_id, attempt=attempt,
                    input_hash=supplied_hash, payload=payload)
                db.add(saved); await db.flush()
                await record(db, session, f'accepted:{saved.id}', 'answer_accepted', {'question_id': question_id, 'input_id': saved.id})
                await db.commit()
            saved_id = saved.id
        if events:
            await events.put({'type': 'transcript', 'transcript': transcript})
        return {'input_id': saved_id}

    async def context_data():
        async with SessionLocal() as db:
            session, questions, answers, saved = await load(db)
            current = _active(session, questions, answers, question_id, attempt, skip, interruption_id)
            if not saved:
                raise RuntimeError('Accepted transcript is missing.')
            conversation = memory.dialogue(session, questions, answers, current, saved.payload['transcript'])
            return session, questions, current, conversation, saved

    async def shared_context(ctx):
        session, questions, current, conversation, saved = await context_data()
        packet = memory.packet(session, conversation, current, guidebook.speaker(session, current.main_order))
        return {'input_id': saved.id, 'source_turn_ids': [t['turn_id'] for t in conversation], 'coverage': packet['coverage']}

    async def analyze(ctx):
        session, questions, current, conversation, saved = await context_data()
        if skip:
            return {'action': 'next', 'response_text': 'Pertanyaan dilewati.' if session.script['settings']['language'] == 'id' else 'Question skipped.'}
        persona = guidebook.speaker(session, current.main_order)
        return await asyncio.wait_for(orchestrator.respond({**guidebook.context_for(session, persona),
            'question': current.question_text, 'context_packet': memory.packet(session, conversation, current, persona),
            'expected_points': current.expected_points, 'interviewer': persona, 'job_role': session.job_role,
            'language': session.script['settings']['language'],
            'allow_followup': current.kind == 'main' and sum(q.kind != 'main' for q in questions) < session.max_followups,
            'is_last': current.main_order == session.question_count}), timeout=settings.respond_timeout_sec)

    async def decide(ctx):
        session, questions, current, conversation, saved = await context_data()
        return coordinate(session, questions, conversation, current, await ctx.result('analyze'), skip=skip)

    async def prepare_response(ctx):
        session, questions, current, conversation, saved = await context_data()
        decision = await ctx.result('coordinate')
        apply_selection(session, questions, decision)
        persona = decision['interviewer']; text = decision['response_text']
        streaming = session.script['settings'].get('streaming_voice', False)
        suffix = hashlib.sha256(run_key.encode()).hexdigest()[:16]
        audio_name = f'r_graph_{question_id}_{suffix}.mp3'
        async def synthesize(text, role, name):
            if streaming or skip:
                return None
            return await ctx.operation('audio:' + name, {'text': text, 'persona': role, 'name': name},
                lambda: speech.optional_synthesize(text, role, sid, name, live=True, timeout=settings.tts_live_timeout_sec), paid=True)
        audio_url = await synthesize(text, persona, audio_name)
        revised, next_audio_name, next_audio_url = None, None, None
        next_q = next((q for q in questions if q.id == decision.get('next_question_id')), None)
        if decision['action'] == 'next' and next_q and session.script['settings'].get('dynamic_questions'):
            next_persona = guidebook.speaker(session, next_q.main_order)
            planned = {key: getattr(next_q, key) for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies')}
            packet = memory.packet(session, conversation, next_q, next_persona)
            context = {**guidebook.context_for(session, next_persona), 'planned_question': planned,
                'intent': session.script.get('question_plan', {}).get(str(next_q.main_order), {}),
                'context_packet': packet, 'handoff': decision.get('handoff'),
                'asked_questions': [t['question'] for t in conversation]}
            revised = planned if skip else await asyncio.wait_for(orchestrator.adapt_question(context), timeout=settings.respond_timeout_sec)
            next_audio_name = f'q_graph_{next_q.id}_{suffix}.mp3'
            next_audio_url = await synthesize(revised['question_text'], next_persona, next_audio_name)
        return {'decision': decision, 'audio_name': audio_name, 'audio_url': audio_url, 'revised': revised,
                'next_audio_name': next_audio_name, 'next_audio_url': next_audio_url}

    async def commit(ctx):
        prepared = await ctx.result('prepare_response'); decision = prepared['decision']
        await ctx.assert_owned()
        async with local_lock(('answer', sid)), SessionLocal() as db:
            session, questions, answers, saved = await load(db, lock=True)
            existing = next((a for a in answers if a.question_id == question_id), None)
            if existing:
                return existing.result_payload
            current = _active(session, questions, answers, question_id, attempt, skip, interruption_id)
            apply_selection(session, questions, decision)
            payload = saved.payload; transcript = payload['transcript']; duration = payload['duration_ms']
            persona = decision['interviewer']; action = decision['action']; text = decision['response_text']
            streaming = session.script['settings'].get('streaming_voice', False)
            follow, next_q = None, None
            if action == 'follow_up':
                follow = InterviewQuestion(session_id=session_id, kind='follow_up', main_order=current.main_order,
                    parent_question_id=current.id, slot=current.slot, category=current.category, question_text=text,
                    expected_points=current.expected_points, competencies=current.competencies,
                    audio_file=prepared['audio_name'] if prepared['audio_url'] else None)
                db.add(follow); await db.flush()
            else:
                next_q = next((q for q in questions if q.id == decision.get('next_question_id')), None)
                if next_q and prepared['revised']:
                    revised = prepared['revised']
                    for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies'):
                        setattr(next_q, key, revised[key])
                    next_q.audio_file = prepared['next_audio_name'] if prepared['next_audio_url'] else None
                    session.script = {**session.script, 'question_provenance': {**session.script.get('question_provenance', {}),
                        str(next_q.main_order): {'anchor_id': revised.get('anchor_id', ''), 'adapted_after_question_id': current.id,
                            'interviewer': guidebook.speaker(session, next_q.main_order), 'source_refs': revised.get('source_refs', []),
                            'handoff': decision.get('handoff')}}}
            last = action == 'next' and next_q is None
            answer = InterviewAnswer(question_id=question_id, transcript=transcript, duration_sec=duration / 1000,
                wpm=0 if payload['input_mode'] in ('text', 'skipped') else round(len(transcript.split()) / max(duration / 60000, .01)),
                filler_count=len(re.findall(r'\b(um|uh|eh|eee|hmm)\b', transcript, re.I)), retry_count=payload['retry_count'],
                timed_out=payload['timed_out'], think_sec=payload['think_ms'] / 1000, response_action=action, response_text=text)
            db.add(answer); await db.flush()
            result = {'answer_id': answer.id, 'transcript': transcript, 'action': action, 'response_text': text,
                'turn_id': f'q{question_id}', 'skipped': skip, 'input_mode': payload['input_mode'],
                'source_refs': decision.get('source_refs', []), 'response_interviewer': persona,
                'response_audio_url': f'/api/sessions/{sid}/speech/response/{answer.id}' if streaming and not skip else prepared['audio_url'],
                'follow_up_question': public_question(follow, session), 'next_question': public_question(next_q, session),
                'is_last': last, 'closing': public_closing(session) if last else None,
                'coordinator': {'version': decision.get('version'), 'handoff': decision.get('handoff')}}
            for key in ('original_transcript', 'transcript_corrected', 'capture_model', 'capture_item_ids'):
                if key in payload: result[key] = payload[key]
            answer.result_payload = result; saved.status = 'completed'
            target = follow or next_q
            checkpoint(session, 'closing' if last else 'question_ready', target, interruption_id=None,
                active_panelist=guidebook.speaker(session, target.main_order) if target else persona,
                remaining_seconds=session.answer_seconds if target else 0)
            await record(db, session, f'answer:{question_id}', 'question_skipped' if skip else 'answer_completed',
                {'question_id': question_id, 'answer_id': answer.id, 'input_id': saved.id, 'source_refs': result['source_refs'], 'graph_thread': run_key})
            if payload.get('transcript_corrected'):
                await record(db, session, f'corrected:{question_id}', 'transcript_corrected', {'question_id': question_id, 'answer_id': answer.id})
            if target and guidebook.speaker(session, target.main_order) != persona:
                await record(db, session, f'handoff:{question_id}', 'panelist_handoff', decision.get('handoff') or {})
            await db.commit()
            return result

    # A retry with changed input cannot bypass validation through a cached first node.
    async with SessionLocal() as db:
        _, _, _, saved = await load(db)
        if saved and supplied_hash and saved.input_hash != supplied_hash:
            raise HTTPException(409, 'Jawaban sudah tersimpan. Kirim ulang jawaban yang sama untuk melanjutkan proses.')
        if saved and events:
            await events.put({'type': 'transcript', 'transcript': saved.payload['transcript']})
    return await execute('turn', session_id, run_key, [
        ('accept_transcript', accept_transcript), ('shared_context', shared_context), ('analyze', analyze),
        ('coordinate', decide), ('prepare_response', prepare_response), ('commit', commit)],
        input_data={'question_id': question_id, 'attempt': attempt, 'input_hash': effective_hash}, allow_uncertain=allow_uncertain,
        session_factory=SessionLocal)


async def resume(input_id, *, allow_uncertain=False):
    async with SessionLocal() as db:
        saved = await db.get(GraphTurnInput, input_id)
        session = await db.get(InterviewSession, saved.session_id) if saved else None
        if not session:
            return None
        sid, owner, qid = session.uuid, session.user_id, saved.question_id
    return await process(sid, owner, qid, resume_input_id=input_id, allow_uncertain=allow_uncertain)
