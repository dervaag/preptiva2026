"""Session preparation graph reusing existing document/question/audio providers."""
from sqlalchemy import select

from app.ai import guidebook, orchestrator, speech
from app.ai.blueprint import PERSONAS, blueprint, validate_questions
from app.config import settings
from app.db import SessionLocal
from app.models import InterviewQuestion, InterviewSession
from app.services.events import checkpoint, record


async def _session(sid):
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        if not session or session.status != 'preparing':
            raise ValueError('Persiapan sesi sudah tidak aktif.')
        return session


async def prepare(sid, *, allow_uncertain=False):
    """Execute/resume preparation; never reset an already prepared session."""
    from app.graphs.runtime import execute
    from app.graphs.models import GraphExecution
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, sid)
        existing_run = await db.get(GraphExecution, f'prepare:{sid}:v1')
        reconcile_ready = session is not None and session.status in ('ready', 'running', 'scoring', 'done') and existing_run is not None
        if not session or (session.status != 'preparing' and not reconcile_ready):
            return {'session_id': sid, 'status': session.status if session else 'missing'}

    async def validate(ctx):
        session = await _session(sid)
        roles = guidebook.panel_roles(session)
        if (session.question_count not in (3, 5, 7) or not roles or len(set(roles)) != len(roles)
                or len(roles) > 3 or any(role not in PERSONAS for role in roles)
                or not session.cv_text or not session.job_description):
            raise ValueError('Konteks persiapan tidak lengkap.')
        if not session.script.get('assessment', {}).get('sha256') or not session.script.get('guidebook', {}).get('sha256'):
            raise ValueError('Persiapan memerlukan snapshot rubrik dan panduan.')
        return {'session_id': sid, 'assessment_hash': session.script['assessment']['sha256'],
                'guidebook_hash': session.script['guidebook']['sha256'], 'panel': roles}

    async def parse(ctx):
        session = await _session(sid)
        # The provider wrapper checkpoints each model request; this result is
        # stored once in the operation ledger, not copied into graph state.
        return await orchestrator.parse_documents(session.cv_text, session.job_description)

    async def context(ctx):
        session = await _session(sid)
        parsed = await ctx.result('parse')
        roles = guidebook.panel_roles(session)
        history = {role: [] for role in roles}
        async with SessionLocal() as db:
            previous = (await db.execute(select(InterviewQuestion, InterviewSession).join(InterviewSession).where(
                InterviewSession.user_id == session.user_id, InterviewSession.id != sid, InterviewQuestion.kind == 'main')
                .order_by(InterviewQuestion.id.desc()).limit(140))).all()
            for question, old_session in previous:
                role = guidebook.speaker(old_session, question.main_order)
                if role in history and len(history[role]) < 35:
                    history[role].append(question.question_text)
        profile = guidebook.profile(parsed['cv_summary'], session.cv_text, session.script['settings'].get('career_stage', 'auto'))
        # This stores compact verified anchors once; raw documents stay on the session.
        return {'candidate_profile': profile, 'history': history}

    async def plan(ctx):
        session = await _session(sid)
        return {'slots': blueprint(session.question_count, session.uuid, guidebook.panel_roles(session),
                                  session.script['guidebook'], session.script['assessment'])}

    async def questions(ctx):
        session = await _session(sid)
        parsed = await ctx.result('parse')
        prepared_context = await ctx.result('context')
        slots = (await ctx.result('plan'))['slots']
        roles = guidebook.panel_roles(session)
        data = {**parsed, 'uuid': session.uuid, 'job_role': session.job_role, 'level': session.level,
                'industry': session.industry, 'company': session.company, 'interviewer': session.interviewer,
                'panel': roles, 'panel_members': [PERSONAS[role] for role in roles],
                'candidate_profile': prepared_context['candidate_profile'], 'guidebook': session.script['guidebook'],
                'question_count': session.question_count, 'assessment': session.script['assessment'],
                'language': session.script['settings']['language']}
        output = await orchestrator.build_questions(data, prepared_context['history'])
        if output.get('plan', slots) != slots or len(output.get('questions', [])) != session.question_count:
            raise ValueError('Pertanyaan tidak sesuai rencana cakupan panel.')
        output['questions'] = [orchestrator.Question.model_validate(q).model_dump() for q in output['questions']]
        for persona in roles:
            assigned = [(slot, output['questions'][slot['main_order'] - 1]) for slot in slots if slot['interviewer'] == persona]
            validate_questions([q for slot, q in assigned], [slot for slot, q in assigned], persona,
                               prepared_context['history'][persona], prepared_context['candidate_profile'])
        if not isinstance(output.get('intro'), str) or not output['intro'].strip() or not isinstance(output.get('closing'), str) or not output['closing'].strip():
            raise ValueError('Intro atau penutup kosong.')
        return {'intro': output['intro'], 'closing': output['closing'], 'questions': output['questions']}

    async def audio(ctx):
        session = await _session(sid)
        output = await ctx.result('questions')
        slots = (await ctx.result('plan'))['slots']
        speakers = {str(slot['main_order']): slot['interviewer'] for slot in slots}
        roles = guidebook.panel_roles(session)
        utterances = [('intro.mp3', output['intro'], roles[0]), ('closing.mp3', output['closing'], speakers[str(session.question_count)])]
        utterances += [(f'q{i}.mp3', q['question_text'], speakers[str(i)]) for i, q in enumerate(output['questions'], 1)
                       if not session.script['settings'].get('dynamic_questions', False) or i == 1]
        if session.script['settings'].get('streaming_voice', False):
            return {'intro.mp3': f'/api/sessions/{session.uuid}/speech/intro/0',
                    'closing.mp3': f'/api/sessions/{session.uuid}/speech/closing/0'}
        urls = {}
        # Each completed synthesis survives a later failure/restart. Sequential
        # calls keep operation identifiers and provider traces unambiguous.
        for name, text, persona in utterances:
            await _session(sid)
            async def synthesize(name=name, text=text, persona=persona):
                return {'url': await speech.optional_synthesize(text, persona, session.uuid, name,
                                      timeout=settings.tts_prepared_timeout_sec)}
            cached = await ctx.operation(f'audio:{name}', {'text': text, 'persona': persona, 'session': session.uuid}, synthesize, paid=True)
            urls[name] = cached['url']
        return urls

    async def commit(ctx):
        parsed = await ctx.result('parse')
        prepared_context = await ctx.result('context')
        slots = (await ctx.result('plan'))['slots']
        output = await ctx.result('questions')
        urls = await ctx.result('audio')
        await ctx.assert_owned()
        async with SessionLocal() as db:
            session = await db.scalar(select(InterviewSession).where(InterviewSession.id == sid).with_for_update())
            if not session or session.status != 'preparing':
                return {'session_id': sid, 'status': session.status if session else 'missing'}
            existing = list((await db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == sid))).all())
            # Question creation and status transition share one application txn.
            if existing:
                raise ValueError('Persiapan menemukan pertanyaan sebelum commit ready.')
            speakers = {str(slot['main_order']): slot['interviewer'] for slot in slots}
            roles = guidebook.panel_roles(session)
            session.cv_summary, session.jd_summary = parsed['cv_summary'], parsed['jd_summary']
            session.script = {**session.script,
                'intro': {'text': output['intro'], 'audio_url': urls.get('intro.mp3'), 'persona': PERSONAS[roles[0]]},
                'closing': {'text': output['closing'], 'audio_url': urls.get('closing.mp3'), 'persona': PERSONAS[speakers[str(session.question_count)]]},
                'fillers': [], 'candidate_profile': prepared_context['candidate_profile'],
                'speaker_by_order': speakers, 'question_plan': {str(slot['main_order']): slot for slot in slots},
                'question_provenance': {str(i): {'anchor_id': q.get('anchor_id', ''), 'interviewer': speakers[str(i)],
                    'conversation_turns': 0} for i, q in enumerate(output['questions'], 1)}}
            for i, question in enumerate(output['questions'], 1):
                fields = {key: question[key] for key in ('slot', 'category', 'question_text', 'expected_points', 'competencies')}
                db.add(InterviewQuestion(session_id=sid, main_order=i, audio_file=f'q{i}.mp3' if urls.get(f'q{i}.mp3') else None, **fields))
            checkpoint(session, 'ready', active_panelist=roles[0], remaining_seconds=session.answer_seconds)
            await record(db, session, 'ready', 'session_prepared', {'guidebook_version': session.script['guidebook']['version'], 'graph_thread': ctx.thread_id})
            session.status, session.error_message = 'ready', None
            await db.commit()
            return {'session_id': sid, 'status': 'ready'}

    return await execute('prepare', sid, f'prepare:{sid}:v1', nodes=[('validate', validate), ('parse', parse),
        ('context', context), ('plan', plan), ('questions', questions), ('audio', audio), ('commit', commit)],
        allow_uncertain=allow_uncertain, session_factory=SessionLocal)
