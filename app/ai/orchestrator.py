import asyncio
from itertools import zip_longest
from pydantic import BaseModel, Field
from app.ai.model_router import complete
from app.ai.blueprint import blueprint, validate_questions, FOCUS, forbidden_hr
from app.ai.guidebook import role_context
from app.ai.memory import validate_refs, reference_options, ReferenceValidationError
from app.services.text import chunks
from app.log import emit
from app.ai.feedback import validate_review, validate_answer_feedback
from app.ai.closing import closing_text, invites_questions


class Question(BaseModel):
    slot: str
    category: str
    question_text: str = Field(min_length=5, max_length=1200)
    expected_points: list[str]
    competencies: list[str]
    anchor_id: str = ''
    source_refs: list[dict] = Field(default_factory=list)


class Response(BaseModel):
    action: str
    response_text: str = Field(min_length=1, max_length=1600)
    source_refs: list[dict] = Field(default_factory=list)


_REPAIR_GUIDANCE = {
    'schema_invalid': 'Return the requested JSON object with all required fields and valid field types.',
    'action_invalid': 'Use exactly one of these actions: next, follow_up, redirect.',
    'reference_required': 'Include at least one allowed_source_refs entry with its original turn_id and exact quote.',
    'reference_invalid': 'Use only exact quotes from the supplied turn. A short answer can be quoted in full; never invent or join excerpts.',
    'question_constraints': 'Ask one new question within the assigned persona, slot, competencies and CV anchors; do not repeat prior questions or assume undocumented experience.',
}


class ModelOutputError(ValueError):
    """Controlled diagnostics for rejected model output; never include its contents."""
    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__('Keluaran AI belum memenuhi aturan wawancara setelah dua percobaan.')


def _repair_output(data, stage, attempt, reason, error):
    emit('ai_output_rejected', stage=stage, reason=reason, attempt=attempt + 1)
    if attempt:
        raise ModelOutputError(stage, reason) from error
    # Pydantic errors can contain the entire model response; do not echo them.
    data['repair_required'] = _REPAIR_GUIDANCE[reason]


def _acknowledge(context):
    return {'action': 'next', 'response_text': 'Terima kasih.' if context['language'] == 'id' else 'Thank you.',
            'source_refs': []}


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
    slots = blueprint(context['question_count'], context['uuid'], roles, context['guidebook'], context.get('assessment'))
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
        'Never ask the candidate to ask you or the panel questions. There is no candidate Q&A phase. '
        'A reflection slot (or legacy candidate_questions slot) must ask about the candidate own learning or work experience, not invite their questions. '
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
            result['closing'] = closing_text(context.get('language', 'id'))
            return result
        except (ValueError, KeyError) as exc:
            if attempt:
                raise
            data['repair_required'] = str(exc)


async def adapt_question(context):
    """Generate the next main turn from the actual conversation, retaining its scope."""
    instruction = ('Generate ONE next interview question from the supplied conversation and verified CV anchors, in session language. '
        'Use the assigned intent and persona guidance. Preserve the planned competencies and slot. Do not repeat an already answered topic. '
        'Read the bounded context_packet: recent turns and retrieved older turns have immutable source IDs. Candidate claims are unverified. '
        'Ground this next question in at least one actual answer from context_packet and include source_refs [{"turn_id":"q123","quote":"exact original excerpt"}]. '
        'When an answer is short, quote that entire answer exactly; never pad the quote or infer missing experience. '
        'Ask a new unresolved aspect of that example within the planned competency, without assuming undocumented tools, events or feedback. Never invent prior facts. '
        'Candidate corrections in the conversation override assumptions in the CV. For students/fresh graduates use academic/project examples and never assume employment. '
        'Ask a concrete unresolved point or a new application of the assigned competency. Never invite the candidate to ask questions to you or the panel, even in a legacy candidate_questions slot. Do not merely rephrase the planned question when the answer changes its assumptions. '
        'Return {"question":{"slot":"...","category":"...","question_text":"one question <=35 words","anchor_id":"cv1","expected_points":["..."],"competencies":["..."],"source_refs":[{"turn_id":"q123","quote":"exact original excerpt"}]}}.')
    data = dict(context)
    data['allowed_source_refs'] = reference_options(context.get('context_packet', {}))
    planned = context['planned_question']
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=900)
        reason = 'schema_invalid'
        try:
            if not isinstance(result, dict) or 'question' not in result:
                raise ValueError('Missing question object.')
            q = Question.model_validate(result['question']).model_dump()
            reason = 'reference_invalid'
            q['source_refs'] = validate_refs(q['source_refs'], context.get('context_packet', {}), required=True)
            reason = 'question_constraints'
            if set(q['competencies']) != set(planned['competencies']):
                raise ValueError('Adaptasi harus mempertahankan kompetensi yang direncanakan.')
            validate_questions([q], [planned], context['interviewer'], context['asked_questions'], context.get('candidate_profile'))
            return q
        except ValueError as exc:
            if isinstance(exc, ReferenceValidationError):
                reason = exc.reason
            _repair_output(data, 'adapt_question', attempt, reason, exc)


async def respond(context):
    data = dict(context)
    data['allowed_source_refs'] = reference_options(context.get('context_packet', {}))
    for attempt in range(2):
        output = await complete(
        'You are the active interviewer, not a coach giving an answer during the interview. ' + FOCUS[context['interviewer']] +
        ' Follow guidance and candidate_profile. Use context_packet recent/retrieved turns to avoid repeated probes. '
        'Previous candidate statements are unverified claims. A follow_up/redirect must include at least one source_refs [{"turn_id":"q123","quote":"exact original excerpt"}] grounding the probe in the answer. '
        'When an answer is short, quote that entire answer exactly; never pad the quote or infer missing experience. '
        'Candidate corrections override CV assumptions. Coursework, projects, internships and student organizations are valid experience. '
        ' Respond in session language, <=45 words; accept bilingual answers. Return {"action":"next|follow_up|redirect","response_text":"...","source_refs":[]}. '
        'A follow_up/redirect asks one short question <=25 words only when allow_followup=true. '
        'Never ask the candidate to ask you or the panel questions; there is no candidate Q&A phase. '
        'For next, acknowledge briefly and never ask a question or invite another answer. If is_last=true, do not announce a next question.', data, tokens=300)
        if isinstance(output, dict) and output.get('action') == 'next' and isinstance(output.get('response_text'), str) and invites_questions(output['response_text']):
            return _acknowledge(context)
        if (isinstance(output, dict) and output.get('action') in ('follow_up', 'redirect')
                and context.get('allow_followup') is False):
            # No probe may be inserted here, so discard its text and references together.
            return _acknowledge(context)
        reason = 'schema_invalid'
        try:
            result = Response.model_validate(output)
            if not result.response_text.strip():
                raise ValueError('Empty response.')
            reason = 'action_invalid'
            if result.action not in ('next', 'follow_up', 'redirect'):
                raise ValueError('Invalid action.')
            reason = 'reference_invalid'
            result.source_refs = validate_refs(result.source_refs, context.get('context_packet', {}), required=result.action != 'next')
            reason = 'question_constraints'
            if result.action != 'next' and (result.response_text.count('?') > 1 or
                    invites_questions(result.response_text) or
                    (context['interviewer'] == 'hr' and forbidden_hr(result.response_text))):
                raise ValueError('Probe outside persona scope or multiple questions.')
        except ValueError as exc:
            if isinstance(exc, ReferenceValidationError):
                reason = exc.reason
            if attempt and reason == 'question_constraints':
                emit('ai_output_rejected', stage='respond', reason=reason, attempt=attempt + 1)
                return _acknowledge(context)
            _repair_output(data, 'respond', attempt, reason, exc)
            continue
        return result.model_dump()


async def evaluate(context):
    indicator_instruction = ('' if not context.get('competency_definitions') else
        'FIRST decide whether the answer describes an actual relevant action or a concrete hypothetical decision. '
        'A wish, inability to recall an example, or lack of opportunity is NOT an action and cannot support any score, including 1. '
        'For example: "I have not had the opportunity to mentor someone" is missing evidence, NOT refusal to support someone. '
        'In that case return score:null, evidence_sufficiency:"none", indicators_met:[], indicator_evidence:[] and explain the missing evidence. '
        'By contrast, an explicit description of rejecting a requested mentoring opportunity for a personal label could support a low anchor if its actual conditions match. '
        'Never substitute "no example supplied" for the harmful behavior described in a level 1 or 2 anchor. '
        'The supplied competency_definitions are the exact job-specific anchors. For each scored competency return '
        'indicators_met:["exact ID at the scored level"], indicator_evidence:[{"indicator_id":"same ID","turn_id":"source turn ID","quote":"verbatim source quote"}], '
        'and next_level_gap describing which higher-anchor behaviors are not yet demonstrated in this answer. '
        'At score 5 next_level_gap is empty. Score must be an integer 1–5. Anchors are ALTERNATIVE levels, not cumulative requirements: '
        'never require low-performance behaviors from levels 1 or 2 to award a higher score. '
        'Use score 1 or 2 only for explicit evidence of that anchor, never for missing detail. '
        'Missing/ambiguous evidence means partial or none; do not invent indicator matches. '
        'Write rationale and next_level_gap in feedback_language when supplied, otherwise session language. '
        'Do not output URLs or source citations; the application resolves these from the immutable rubric. ')
    shape = ('Return {"competency_scores":{"communication":{"score":1,"evidence":["exact transcript quote"]}},' if not context.get('competency_definitions') else
        'Return {"competency_scores":{"<requested competency key>":{"score":3,"evidence":["verbatim quote"],'
        '"evidence_sufficiency":"sufficient","rationale":"why this anchor fits the quoted behavior",'
        '"indicators_met":["exact ID for this key at level 3"],'
        '"indicator_evidence":[{"indicator_id":"same ID","turn_id":"source turn ID","quote":"verbatim quote"}],'
        '"next_level_gap":"specific higher-anchor behavior not demonstrated yet"}},')
    instruction = (indicator_instruction + 'Evaluate the main question and all its follow-up answers as one unit. ' + FOCUS.get(context.get('interviewer'), '') +
        ' Follow the session rubric exactly. Accept coursework, student organizations, projects and internships as evidence; do not penalize lack of employment by itself. '
        'Use only transcript evidence. Do not score age, gender, accent or code-switching. Do not assume transcription mistakes reflect ability. ' +
        shape +
        '"star":{"situation":false,"task":false,"action":false,"result":false},'
        '"feedback":{"strengths":[],"improvements":[],"better_answer_tip":"..."}}. Only score listed question competencies. '
        'For each competency also return evidence_sufficiency (sufficient|partial|none) and rationale. '
        'Insufficient evidence is not demonstrated low ability. Use sufficient with a low score only when a quote demonstrates the low performance. '
        'Quotes must be literal original-language excerpts from ONE supplied source turn, never joined across turns. '
        'Transcription confidence is unknown; never infer accent, speech quality or transcription accuracy from text. '
        'Use numbers 1 to 5 for measured competencies. Leave unmeasured competencies out or mark evidence_sufficiency none with score null. Feedback follows feedback_language when supplied, otherwise session language.')
    output_language = context.get('feedback_language', context.get('language', 'id'))
    instruction += (' All rationale, next_level_gap and feedback fields MUST be written in '
                    + ('English.' if output_language == 'en' else 'Bahasa Indonesia.')
                    + ' The interview is finished. Give direct explanations and actionable suggestions; '
                    'do not ask the candidate questions or request another answer. Preserve evidence quotes exactly in their original language.')
    data = dict(context)
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=2200 if context.get('competency_definitions') else 1800)
        try:
            validate_answer_feedback(result)
            if context.get('competency_definitions'):
                validate_indicator_output(result, context)
            return result
        except (ValueError,KeyError,TypeError) as exc:
            if attempt:
                raise ValueError('Struktur bukti atau feedback belum valid; evaluasi dapat dicoba ulang.') from exc
            data['repair_required'] = str(exc)
            data['previous_output'] = result


def validate_indicator_output(result, context):
    scores = result['competency_scores']
    if not isinstance(scores,dict) or set(scores) - set(context['competencies']):
        raise ValueError('Only return the requested competency keys.')
    for key,value in scores.items():
        if not isinstance(value,dict) or value.get('evidence_sufficiency') not in ('sufficient','partial','none'):
            raise ValueError('Every competency needs an explicit evidence_sufficiency.')
        if not isinstance(value.get('rationale'),str):
            raise ValueError('Every competency needs a rationale.')
        if value['evidence_sufficiency'] != 'sufficient':
            continue
        score = value.get('score')
        if type(score) is not int or score not in range(1,6):
            raise ValueError('A sufficient score must be an integer 1–5.')
        anchor = context['competency_definitions'][key]['levels'][str(score)]
        if value.get('indicators_met') != [anchor['id']]:
            raise ValueError('indicators_met must contain exactly the supplied ID at the scored level.')
        evidence = value.get('indicator_evidence')
        if not isinstance(evidence,list) or not evidence:
            raise ValueError('A sufficient score requires indicator_evidence with a literal source-turn quotation.')
        for entry in evidence:
            quote = entry.get('quote') if isinstance(entry,dict) else None
            if (not isinstance(quote,str) or len(quote.strip()) < 8 or entry.get('indicator_id') != anchor['id']
                    or not any(quote in turn['transcript'] and entry.get('turn_id') == turn['turn_id'] for turn in context['source_turns'])):
                raise ValueError('indicator_evidence must match the anchor ID and an exact quotation in its source turn.')
        if score < 5 and (not isinstance(value.get('next_level_gap'),str) or not value['next_level_gap'].strip()):
            raise ValueError('Explain the missing higher-anchor evidence in next_level_gap.')


async def summarize(context):
    instruction = ('Write a useful practice interview review based only on supplied evaluations. '
        'Do not invent scores or evidence. Return {"summary":"...","strengths":[],"improvements":[], '
        '"study_recommendations":[{"topic":"...","reason":"...","action":"..."}]}. '
        'The interview has ended: return final feedback, never a new interview question, a request for input or an invitation to answer. '
        'Use declarative explanations and imperative practice actions, without question marks. '
        'Insufficient evidence means missing evidence in the answers, not proven lack of ability. '
        'If coverage.measured is zero or total_score is null, explain that no overall score is available; do not infer low ability or confirmed potential. '
        'This is practice feedback, not a prediction of job selection or personality diagnosis. '
        'Write every summary, strength, improvement, recommendation topic, reason and action in '
        + ('English.' if context.get('language') == 'en' else 'Bahasa Indonesia.'))
    data = dict(context)
    for attempt in range(2):
        result = await complete(instruction, data, deep=True, tokens=1500)
        try:
            validate_review(result)
            return result
        except ValueError:
            if attempt:
                raise ValueError('Final feedback is incomplete or asks questions; retry evaluation.')
            data['repair_required'] = 'Return all requested fields as final statements and practice actions. Do not ask questions.'
