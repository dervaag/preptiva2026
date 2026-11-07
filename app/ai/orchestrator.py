import asyncio
from itertools import zip_longest
from pydantic import BaseModel, Field
from app.ai.model_router import complete
from app.ai.blueprint import blueprint, validate_questions, FOCUS
from app.services.text import chunks
from app.log import emit


class Question(BaseModel):
    slot: str
    category: str
    question_text: str = Field(min_length=5, max_length=1200)
    expected_points: list[str]
    competencies: list[str]


class Response(BaseModel):
    action: str
    response_text: str = Field(min_length=1, max_length=1600)


async def parse_documents(cv, jd):
    cv_parts = chunks(cv, 6000) if len(cv) > 12000 or len(jd) > 8000 else [cv]
    jd_parts = chunks(jd, 4000) if len(cv_parts) > 1 or len(jd) > 8000 else [jd]
    gate = asyncio.Semaphore(2)
    async def parse(a, b):
        async with gate:
            return await complete('Extract candidate CV and job requirements. Return {"cv_summary":{"experience":[],"skills":[],"education":[],"years_exp":0},"jd_summary":{"requirements":[],"responsibilities":[]}}. Preserve facts, do not invent.', {'cv': a, 'jd': b}, tokens=1200)
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
                elif old is None:
                    merged[section][key] = value
    return merged


async def build_questions(context, history):
    slots = blueprint(context['question_count'], context['uuid'])
    data = {**context, 'blueprint': slots, 'previous_questions_to_avoid': history}
    instruction = ('Create personalized interview questions and intro/closing in session language. ' + FOCUS[context['interviewer']] +
        ' Each question <=35 words and exactly one question per turn. Match role, level, industry and supplied CV/JD. '
        'Return {"intro":"...","closing":"...","questions":[{"slot":"...","category":"...","question_text":"...","expected_points":["..."],"competencies":["communication",...]}]}. '
        'Competencies allowed: communication, problem_solving, technical, analytical, teamwork, adaptability, leadership. Respect blueprint order.')
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=3000)
        try:
            result['questions'] = [Question.model_validate(q).model_dump() for q in result['questions']]
            validate_questions(result['questions'], slots, context['interviewer'], history)
            if not result.get('intro') or not result.get('closing'):
                raise ValueError('Intro atau penutup kosong.')
            if context['interviewer'] == 'hr':
                for q in result['questions']:
                    q['competencies'] = [c for c in q['competencies'] if c != 'technical']
            return result
        except (ValueError, KeyError) as exc:
            if attempt:
                raise
            data['repair_required'] = str(exc)


async def respond(context):
    result = Response.model_validate(await complete(
        'You are an interview coach. ' + FOCUS[context['interviewer']] +
        ' Respond in session language, <=45 words; accept bilingual answers. Return {"action":"next|follow_up|redirect","response_text":"..."}. '
        'A follow_up/redirect asks one short question <=25 words only when allow_followup=true. '
        'For next, acknowledge briefly and never ask a question or invite another answer. If is_last=true, do not announce a next question.', context, tokens=250))
    if result.action not in ('next', 'follow_up', 'redirect'):
        raise ValueError('Aksi AI tidak valid.')
    return result.model_dump()


async def evaluate(context):
    return await complete('Evaluate the main question and all its follow-up answers as one unit. Follow the session rubric exactly. '
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
