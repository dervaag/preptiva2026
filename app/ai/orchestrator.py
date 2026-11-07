import asyncio
from itertools import zip_longest
from pydantic import BaseModel, Field
from app.ai.model_router import complete
from app.ai.blueprint import blueprint, validate_questions, FOCUS, forbidden_hr
from app.ai.guidebook import role_context
from app.services.text import chunks
from app.log import emit


class Question(BaseModel):
    slot: str
    category: str
    question_text: str = Field(min_length=5, max_length=1200)
    expected_points: list[str]
    competencies: list[str]
    anchor_id: str = ''


class Response(BaseModel):
    action: str
    response_text: str = Field(min_length=1, max_length=1600)


async def parse_documents(cv, jd):
    cv_parts = chunks(cv, 6000) if len(cv) > 12000 or len(jd) > 8000 else [cv]
    jd_parts = chunks(jd, 4000) if len(cv_parts) > 1 or len(jd) > 8000 else [jd]
    gate = asyncio.Semaphore(2)
    async def parse(a, b):
        async with gate:
            return await complete('Extract candidate CV and job requirements. Return {"cv_summary":{"experience":[],"skills":[],"education":[],"projects":[],"internships":[],"activities":[],"years_exp":null,"career_stage":"unknown|student|fresh_graduate|experienced|career_switcher","career_stage_evidence":"exact CV quote supporting stage or empty","evidence":[{"kind":"education|project|internship|work|activity","quote":"exact CV excerpt"}]},"jd_summary":{"requirements":[],"responsibilities":[]}}. Preserve facts, do not invent. Unknown experience is not zero. Do not infer stage from age, gender, junior job level, or lack of work details. Include academic and extracurricular evidence. career_stage must be exactly one allowed value. Copy evidence as a literal substring of the original CV, preserving spelling and numbers; never paraphrase or convert written numerals to digits in quotes.', {'cv': a, 'jd': b}, tokens=2200)
    emit('documents_chunked', cv_chars=len(cv), jd_chars=len(jd), cv_chunks=len(cv_parts), jd_chunks=len(jd_parts))
    results = await asyncio.gather(*(parse(a, b) for a, b in zip_longest(cv_parts, jd_parts, fillvalue='')))
    merged = {'cv_summary': {}, 'jd_summary': {}}
    for item in results:
        for section in merged:
            for key, value in item.get(section, {}).items():
                old = merged[section].get(key)
                if isinstance(value, list):
                    target = old if isinstance(old, list) else []
                    merged[section][key] = target + [v for v in value if v not in target]
                elif key == 'years_exp' and isinstance(value, (int, float)):
                    merged[section][key] = max(value, old or 0)
                elif key == 'career_stage' and old and old != value and value != 'unknown':
                    merged[section][key] = 'unknown'
                    merged[section]['career_stage_evidence'] = ''
                elif old is None:
                    merged[section][key] = value
    merged['cv_summary']['career_stage_candidates'] = [
        {'stage': item.get('cv_summary', {}).get('career_stage'),
         'quote': item.get('cv_summary', {}).get('career_stage_evidence', '')} for item in results]
    return merged


async def build_questions(context, history):
    roles = context.get('panel', [context['interviewer']])
    slots = blueprint(context['question_count'], context['uuid'], roles, context['guidebook'])
    output, intro, closing = {}, '', ''
    for persona in roles:
        assigned = [s for s in slots if s['interviewer'] == persona]
        past = history.get(persona, []) if isinstance(history, dict) else history
        result = await generate_set(role_context(context, persona), assigned, past)
        if not intro:
            intro = result['intro']
        if persona == slots[-1]['interviewer']:
            closing = result['closing']
        for slot, q in zip(assigned, result['questions']):
            output[slot['main_order']] = q
    return {'intro': intro, 'closing': closing, 'questions': [output[i] for i in sorted(output)], 'plan': slots}


async def generate_set(context, slots, history):
    data = {**context, 'blueprint': slots, 'previous_questions_to_avoid': history}
    instruction = ('Create personalized interview questions and intro/closing in session language. ' + FOCUS[context['interviewer']] +
        ' Speak as the selected interviewer role, never as another panel member. If panel_members are supplied, introduce them briefly in the intro. '
        ' Each question <=35 words and exactly one question per turn. Match role, level, industry and supplied CV/JD. '
        'Anchor each question in an actual candidate_profile anchor, including its anchor_id. Unknown background requires a neutral clarification. '
        'Student/fresh graduate questions must use actual academic, project, internship or volunteering evidence rather than assume employment or direct reports. '
        'Return {"intro":"...","closing":"...","questions":[{"slot":"...","category":"...","question_text":"...","anchor_id":"cv1","expected_points":["..."],"competencies":["communication"]}]}. '
        'Use the competencies specified in each blueprint slot. Respect blueprint order and all guidance rules. Expected evidence must fit the candidate background, not a senior model answer.')
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=3000)
        try:
            result['questions'] = [Question.model_validate(q).model_dump() for q in result['questions']]
            validate_questions(result['questions'], slots, context['interviewer'], history, context.get('candidate_profile'))
            if not result.get('intro') or not result.get('closing'):
                raise ValueError('Intro atau penutup kosong.')
            return result
        except (ValueError, KeyError) as exc:
            if attempt:
                raise
            data['repair_required'] = str(exc)


async def adapt_question(context):
    """Generate the next main turn from the actual conversation, retaining its scope."""
    instruction = ('Generate ONE next interview question from the supplied conversation and verified CV anchors, in session language. '
        'Use the assigned intent and persona guidance. Preserve the planned competencies and slot. Do not repeat an already answered topic. '
        'Candidate corrections in the conversation override assumptions in the CV. For students/fresh graduates use academic/project examples and never assume employment. '
        'Ask a concrete unresolved point or a new application of the assigned competency. Do not merely rephrase the planned question when the answer changes its assumptions. '
        'Return {"question":{"slot":"...","category":"...","question_text":"one question <=35 words","anchor_id":"cv1","expected_points":["..."],"competencies":["..."]}}.')
    data = dict(context)
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=900)
        try:
            q = Question.model_validate(result['question']).model_dump()
            planned = context['planned_question']
            if set(q['competencies']) != set(planned['competencies']):
                raise ValueError('Adaptasi harus mempertahankan kompetensi yang direncanakan.')
            validate_questions([q], [planned], context['interviewer'], context['asked_questions'], context.get('candidate_profile'))
            return q
        except (ValueError, KeyError) as exc:
            if attempt:
                raise
            data['repair_required'] = str(exc)


async def respond(context):
    data = dict(context)
    for attempt in range(2):
        result = Response.model_validate(await complete(
        'You are the active interviewer, not a coach giving an answer during the interview. ' + FOCUS[context['interviewer']] +
        ' Follow guidance and candidate_profile. Use the whole conversation to avoid repeated probes. '
        'Candidate corrections override CV assumptions. Coursework, projects, internships and student organizations are valid experience. '
        ' Respond in session language, <=45 words; accept bilingual answers. Return {"action":"next|follow_up|redirect","response_text":"..."}. '
        'A follow_up/redirect asks one short question <=25 words only when allow_followup=true. '
        'For next, acknowledge briefly and never ask a question or invite another answer. If is_last=true, do not announce a next question.', data, tokens=300))
        if result.action not in ('next', 'follow_up', 'redirect'):
            raise ValueError('Aksi AI tidak valid.')
        if result.action != 'next' and (result.response_text.count('?') > 1 or
                (context['interviewer'] == 'hr' and forbidden_hr(result.response_text))):
            data['repair_required'] = 'Ask one question within this persona scope, or choose next.'
            if not attempt:
                continue
            return {'action': 'next', 'response_text': 'Terima kasih.' if context['language'] == 'id' else 'Thank you.'}
        return result.model_dump()


async def evaluate(context):
    return await complete('Evaluate the main question and all its follow-up answers as one unit. ' + FOCUS.get(context.get('interviewer'), '') +
        ' Follow the session rubric exactly. Accept coursework, student organizations, projects and internships as evidence; do not penalize lack of employment by itself. '
        'Use only transcript evidence. Do not score age, gender, accent or code-switching. Do not assume transcription mistakes reflect ability. '
        'Return {"competency_scores":{"communication":{"score":1,"evidence":["exact transcript quote"]}},'
        '"star":{"situation":false,"task":false,"action":false,"result":false},'
        '"feedback":{"strengths":[],"improvements":[],"better_answer_tip":"..."}}. Only score listed question competencies. '
        'Use numbers 1 to 5. Leave unmeasured competencies out. Feedback in session language.', context, deep=True, tokens=1500)


async def summarize(context):
    return await complete('Write a useful practice interview review in session language based only on supplied evaluations. '
        'Do not invent scores or evidence. Return {"summary":"...","strengths":[],"improvements":[], '
        '"study_recommendations":[{"topic":"...","reason":"...","action":"..."}]}. '
        'This is practice feedback, not a prediction of job selection or personality diagnosis.', context, deep=True, tokens=1500)
