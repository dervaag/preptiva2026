"""Bounded, source-linked dialogue context; original answers remain in PostgreSQL."""
import json
import re
from app.ai.guidebook import speaker

VERSION = '2026-11-07.3'
PACKET_CHARS = 14000  # Conservative character budget, measured before each model call.


class ReferenceValidationError(ValueError):
    """A stable reason for diagnostics without candidate/model content."""
    def __init__(self, reason='reference_invalid'):
        messages = {
            'reference_required': 'Adaptasi/follow-up harus merujuk minimal satu kutipan jawaban kandidat yang tersedia.',
            'reference_invalid': 'Rujukan percakapan harus berupa kutipan asli dari giliran yang tersedia.',
        }
        self.reason = reason if reason in messages else 'reference_invalid'
        super().__init__(messages[self.reason])


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


def _literal_prefix(text, budget):
    """Prefer word boundaries without reducing usable evidence to a tiny fragment."""
    text = text.strip()
    if len(text) <= budget:
        return text
    end = text.rfind(' ', 0, budget)
    return text[:end] if end > 0 and len(text[:end].strip()) >= 8 else text[:budget]


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
    if any(len(sentence.strip()) >= 8 for _, sentence in chosen):
        return '\n'.join(s.strip() for _, s in sorted(chosen))
    # A long sentence or only tiny selected fragments: retain a contiguous
    # original passage so the required reference can actually be satisfied.
    start = next((m.start() for m in re.finditer(r'\b\w+\b', text) if m.group().casefold() in words), 0)
    if len(text[start:].strip()) < 8:
        start = 0
    return _literal_prefix(text[start:], budget)


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
        source_quotes = [answer] if answer in turn['answer'] else [part for part in answer.splitlines() if part and part in turn['answer']]
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
        quote = next((part for part in turn['source_quotes'] if len(part.strip()) >= 8
                      or (not turn['is_excerpt'] and part.strip() == turn['answer'].strip())), '')
        quote = _literal_prefix(quote, 220)
        if quote.strip():
            # The offered model options must obey the same rules as its output.
            try:
                validate_refs([{'turn_id': turn['turn_id'], 'quote': quote}], context)
            except ReferenceValidationError:
                continue
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
    if not isinstance(refs, list) or not isinstance(context, dict):
        raise ReferenceValidationError()
    available = {}
    for group in ('recent_turns', 'retrieved_turns'):
        turns = context.get(group, [])
        if not isinstance(turns, list):
            raise ReferenceValidationError()
        for turn in turns:
            if (not isinstance(turn, dict) or not isinstance(turn.get('turn_id'), str)
                    or not turn['turn_id'].strip() or not isinstance(turn.get('answer'), str)):
                raise ReferenceValidationError()
            quotes = turn.get('source_quotes', [turn['answer']])
            if not isinstance(quotes, list) or any(not isinstance(text, str) for text in quotes):
                raise ReferenceValidationError()
            available[turn['turn_id']] = (turn, quotes)
    result = []
    if required and any(text.strip() for _, quotes in available.values() for text in quotes) and not refs:
        raise ReferenceValidationError('reference_required')
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get('turn_id'), str):
            raise ReferenceValidationError()
        quote = ref.get('quote', '')
        if ref['turn_id'] not in available or not isinstance(quote, str) or not quote.strip():
            raise ReferenceValidationError()
        turn, originals = available[ref['turn_id']]
        # A short answer can ground a clarification, but a short fragment of a
        # longer answer/excerpt cannot. This does not relax scoring evidence.
        whole_short_answer = (turn.get('is_excerpt') is False and quote.strip() == turn['answer'].strip())
        if (not any(quote in original for original in originals)
                or (len(quote.strip()) < 8 and not whole_short_answer)):
            raise ReferenceValidationError()
        normalized = {'turn_id': ref['turn_id'], 'quote': quote}
        if normalized not in result:
            result.append(normalized)
    return result


def reference_options(context):
    return [{'turn_id': f['source_turn_id'], 'quote': f['quote']} for f in context.get('candidate_facts', [])]
