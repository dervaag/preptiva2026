"""Bounded, source-linked dialogue context; original answers remain in PostgreSQL."""
import json
import re
from app.ai.guidebook import speaker

VERSION = '2026-11-07.2'
PACKET_CHARS = 14000  # Conservative character budget, measured before each model call.


def dialogue(session, questions, answers, current=None, transcript=None):
    by_id = {q.id: q for q in questions}
    ordered = sorted(answers, key=lambda a: (by_id[a.question_id].main_order, a.question_id))
    result = []
    for answer in ordered:
        q = by_id[answer.question_id]
        result.append({'turn_id': f'q{q.id}', 'question_id': q.id, 'interviewer': speaker(session, q.main_order),
                       'question': q.question_text, 'answer': answer.transcript, 'competencies': q.competencies})
    if current is not None and transcript is not None:
        result.append({'turn_id': f'q{current.id}', 'question_id': current.id,
                       'interviewer': speaker(session, current.main_order), 'question': current.question_text,
                       'answer': transcript, 'competencies': current.competencies})
    return result


def excerpt(text, query, budget=900):
    """Select complete relevant sentences; label excerpts instead of rewriting quotations."""
    if len(text) <= budget:
        return text
    words = set(re.findall(r'\w{3,}', query.casefold()))
    spans = [(m.start(), m.group()) for m in re.finditer(r'[^.!?\n]+(?:[.!?]|$)', text)]
    ranked = sorted(spans, key=lambda x: (-len(words & set(re.findall(r'\w{3,}', x[1].casefold()))), x[0]))
    chosen, used = [], 0
    for offset, sentence in ranked:
        if len(sentence) + used <= budget:
            chosen.append((offset, sentence)); used += len(sentence)
    if not chosen:
        # A long sentence: retain one contiguous passage on word boundaries, explicitly excerpted.
        start = next((m.start() for m in re.finditer(r'\b\w+\b', text) if m.group().casefold() in words), 0)
        end = text.rfind(' ', start, start + budget)
        return text[start:end if end > start else start + budget]
    return '\n'.join(s.strip() for _, s in sorted(chosen))


def packet(session, dialogue_turns, question, persona):
    query = question.question_text + ' ' + ' '.join(question.competencies)
    words = set(re.findall(r'\w{3,}', query.casefold()))
    recent = dialogue_turns[-3:]
    older = dialogue_turns[:-3]
    ranked = sorted(older, key=lambda t: (len(set(question.competencies) & set(t['competencies'])),
        len(words & set(re.findall(r'\w{3,}', t['answer'].casefold())))), reverse=True)
    retrieved = ranked[:3]
    def compact(turn):
        answer = excerpt(turn['answer'], query)
        source_quotes = [answer] if answer == turn['answer'] else [part for part in answer.splitlines() if part and part in turn['answer']]
        return {k: turn[k] for k in ('turn_id', 'question_id', 'interviewer', 'question')} | {
            'answer': answer, 'source_quotes': source_quotes, 'is_excerpt': answer != turn['answer'], 'verification_status': 'candidate_claim_unverified'}
    context = {'version': VERSION, 'active_panelist': persona,
        'phase': 'deep_dive' if question.kind != 'main' else question.slot,
        'current_question_id': question.id, 'target_competencies': question.competencies,
        'recent_turns': [compact(t) for t in recent], 'retrieved_turns': [compact(t) for t in retrieved],
        'older_turn_index': [{'turn_id': t['turn_id'], 'interviewer': t['interviewer'],
                              'competencies': t['competencies']} for t in older],
        'candidate_facts': [], 'coverage': {},
        'memory_policy': 'Statements are candidate claims, not independently verified facts. Quotes and original turns override summaries. Only refer to supplied source turns.'}
    for turn in context['retrieved_turns'] + context['recent_turns']:
        quote = (turn['source_quotes'] or [''])[0]
        if len(quote) > 220:
            end = quote.rfind(' ', 0, 220)
            quote = quote[:end if end > 0 else 220]
        if quote:
            context['candidate_facts'].append({'source_turn_id': turn['turn_id'],
                'quote': quote, 'verification_status': 'unverified'})
    asked = {c for t in dialogue_turns if t['answer'].strip() for c in t['competencies']}
    context['coverage'] = {c: ('asked_not_yet_scored' if c in asked else 'not_assessed')
                           for c, weight in session.script['assessment']['weights'].items() if weight}
    # Remove lowest-priority retrieval first; never silently discard original stored answers.
    while len(json.dumps(context, ensure_ascii=False)) > PACKET_CHARS and context['retrieved_turns']:
        removed = context['retrieved_turns'].pop()
        context['candidate_facts'] = [f for f in context['candidate_facts'] if f['source_turn_id'] != removed['turn_id']]
    while len(json.dumps(context, ensure_ascii=False)) > PACKET_CHARS and context['older_turn_index']:
        context['older_turn_index'].pop(0)
    if len(json.dumps(context, ensure_ascii=False)) > PACKET_CHARS:
        raise ValueError('Paket konteks melampaui anggaran.')
    return context


def validate_refs(refs, context, required=False):
    available = {t['turn_id']: t.get('source_quotes', [t['answer']]) for t in context.get('recent_turns', []) + context.get('retrieved_turns', [])}
    result = []
    if required and any(text.strip() for quotes in available.values() for text in quotes) and not refs:
        raise ValueError('Adaptasi/follow-up harus merujuk minimal satu kutipan jawaban kandidat yang tersedia.')
    for ref in refs:
        quote = ref.get('quote', '')
        if ref.get('turn_id') not in available or not isinstance(quote, str) or len(quote.strip()) < 8 or not any(quote in original for original in available[ref['turn_id']]):
            raise ValueError('Rujukan percakapan harus berupa kutipan asli dari giliran yang tersedia.')
        if ref not in result:
            result.append({'turn_id': ref['turn_id'], 'quote': quote})
    return result


def reference_options(context):
    return [{'turn_id': f['source_turn_id'], 'quote': f['quote']} for f in context.get('candidate_facts', [])]
