"""Validated panel routing; coverage describes inquiries, never proven ability."""
from copy import deepcopy
from difflib import SequenceMatcher
import re

from app.ai import guidebook, memory
from app.ai.blueprint import forbidden_hr
from app.ai.scoring import WEIGHTS

VERSION = 'panel-routing-v1'
QUESTION_FIELDS = ('slot', 'category', 'question_text', 'expected_points', 'competencies', 'audio_file')


def _allowed(session, persona):
    assessment = session.script['assessment']
    weights = assessment.get('persona_weights', {}).get(persona, WEIGHTS[persona])
    return {key for key, weight in weights.items() if weight > 0}


def _acknowledgement(text, language):
    # Transitions must not ask an untracked second question.
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s for s in sentences if '?' not in s and not re.search(
        r'(pertanyaan (berikut|selanjut)|next question|let.s move|mari (lanjut|beralih))', s, re.I)]
    return ' '.join(sentences).strip() or ('Terima kasih.' if language == 'id' else 'Thank you.')


def coordinate(session, questions, dialogue, current, proposal, *, skip=False):
    """Return a bounded decision. A future slot may swap content, never IDs/order.

    The last planned slot remains fixed so its persona and closing stay aligned.
    Proposed routing/scores from the model are intentionally ignored: only the
    validated answer action/text/references are accepted. A skipped answer
    follows the immediate plan and cannot trigger another model dependency.
    """
    roles = guidebook.panel_roles(session)
    if not roles or len(set(roles)) != len(roles) or any(p not in WEIGHTS for p in roles):
        raise ValueError('Snapshot panel tidak valid.')
    if current.id not in {q.id for q in questions}:
        raise ValueError('Pertanyaan aktif tidak berada dalam sesi.')
    persona = guidebook.speaker(session, current.main_order)
    if persona not in roles or not set(current.competencies) <= _allowed(session, persona):
        raise ValueError('Pertanyaan melampaui lingkup persona dalam snapshot.')
    language = session.script.get('settings', {}).get('language', 'id')
    asked = {c for turn in dialogue if turn.get('answer', '').strip() for c in turn.get('competencies', [])}
    coverage = {key: ('asked_not_yet_scored' if key in asked else 'not_assessed')
                for key, weight in session.script['assessment']['weights'].items() if weight > 0}
    packet = memory.packet(session, dialogue, current, persona)
    action = proposal.get('action') if isinstance(proposal, dict) else None
    text = str(proposal.get('response_text', ''))[:1600] if isinstance(proposal, dict) else ''
    refs = []
    allow_followup = current.kind == 'main' and sum(q.kind != 'main' for q in questions) < session.max_followups
    reason = 'model_next'
    if not skip and action in ('follow_up', 'redirect') and allow_followup:
        try:
            refs = memory.validate_refs(proposal.get('source_refs', []), packet, required=True)
            if not text.strip() or text.count('?') > 1 or (persona == 'hr' and forbidden_hr(text)):
                raise ValueError('Pertanyaan lanjutan melampaui lingkup.')
            if any(SequenceMatcher(None, text.casefold(), t['question'].casefold()).ratio() > .92 for t in dialogue):
                raise ValueError('Pertanyaan lanjutan mengulang pertanyaan yang tersedia.')
            action = 'follow_up'
            reason = 'clarify_candidate_claim'
        except (ValueError, TypeError, AttributeError):
            action, reason = 'next', 'invalid_followup_rejected'
            text, refs = '', []
    else:
        if skip:
            reason = 'question_skipped'
        elif action in ('follow_up', 'redirect'):
            reason = 'followup_limit'
            text = ''
        elif action != 'next':
            reason = 'invalid_action_rejected'
            text = ''
        action = 'next'
    result = {'version': VERSION, 'action': action, 'interviewer': persona,
              'response_text': text, 'source_refs': refs, 'reason': reason,
              'next_question_id': None, 'selected_question_id': None,
              'next_persona': persona if action == 'follow_up' else None,
              'coverage': coverage, 'handoff': None}
    if action == 'follow_up':
        return result
    result['response_text'] = ('Pertanyaan dilewati.' if language == 'id' else 'Question skipped.') if skip else _acknowledgement(text, language)
    mains = sorted((q for q in questions if q.kind == 'main'), key=lambda q: q.main_order)
    target = next((q for q in mains if q.main_order == current.main_order + 1), None)
    if target is None:
        if current.main_order != session.question_count:
            raise ValueError('Rencana pertanyaan berikutnya tidak lengkap.')
        return result
    answered_ids = {turn['question_id'] for turn in dialogue}
    candidates = [q for q in mains if target.main_order <= q.main_order <= session.question_count and q.id not in answered_ids]
    # Preserve the terminal slot, which owns the prepared closing utterance.
    if target.main_order < session.question_count:
        candidates = [q for q in candidates if q.main_order < session.question_count and q.slot != 'candidate_questions']
    if skip:
        candidates = [target]
    eligible = []
    for question in candidates:
        role = guidebook.speaker(session, question.main_order)
        if role in roles and question.competencies and set(question.competencies) <= _allowed(session, role):
            eligible.append(question)
    if not eligible:
        raise ValueError('Tidak ada slot berikutnya dalam lingkup panel.')
    answered_by_persona = {p: sum(t.get('interviewer') == p and bool(t.get('answer', '').strip()) for t in dialogue) for p in roles}
    def priority(question):
        role = guidebook.speaker(session, question.main_order)
        repeated = any(SequenceMatcher(None, question.question_text.casefold(), t['question'].casefold()).ratio() > .88 for t in dialogue)
        return (repeated, -len(set(question.competencies) - asked), answered_by_persona[role], role == persona, question.main_order)
    selected = min(eligible, key=priority)
    next_persona = guidebook.speaker(session, selected.main_order)
    target_packet = memory.packet(session, dialogue, selected, next_persona)
    claims = [{'turn_id': fact['source_turn_id'], 'quote': fact['quote'], 'verification_status': 'candidate_claim_unverified'}
              for fact in target_packet['candidate_facts']]
    result.update(next_question_id=target.id, selected_question_id=selected.id, next_persona=next_persona)
    result['handoff'] = {'from': persona, 'to': next_persona,
                         'reason': 'coverage_priority' if selected.id != target.id else 'planned_order',
                         'target_competencies': list(selected.competencies),
                         'unasked_competencies': [c for c in selected.competencies if c not in asked],
                         'claims': claims,
                         'instruction': 'Reuse supplied answers and literal source references; probe an unresolved aspect without asking the candidate to repeat an available answer. Claims are unverified; coverage is not a score.'}
    return result


def apply_selection(session, questions, decision):
    """Apply a validated choice inside the caller's short database transaction.

    Returns the next actual question. IDs/main_order and the number of slots do
    not change; only two untouched future slots exchange their planned content.
    """
    if decision['action'] != 'next' or decision['next_question_id'] is None:
        return None
    by_id = {q.id: q for q in questions}
    target = by_id[decision['next_question_id']]
    selected = by_id[decision['selected_question_id']]
    if target.id == selected.id:
        return target
    if target.kind != 'main' or selected.kind != 'main' or selected.main_order <= target.main_order or selected.main_order == session.question_count:
        raise ValueError('Pertukaran slot koordinator tidak valid.')
    old_target = {key: deepcopy(getattr(target, key)) for key in QUESTION_FIELDS}
    old_selected = {key: deepcopy(getattr(selected, key)) for key in QUESTION_FIELDS}
    for key in QUESTION_FIELDS:
        setattr(target, key, old_selected[key])
        setattr(selected, key, old_target[key])
    left, right = str(target.main_order), str(selected.main_order)
    speakers = {str(q.main_order): guidebook.speaker(session, q.main_order) for q in questions if q.kind == 'main'}
    speakers[left], speakers[right] = speakers[right], speakers[left]
    plan = deepcopy(session.script.get('question_plan', {}))
    provenance = deepcopy(session.script.get('question_provenance', {}))
    for mapping in (plan, provenance):
        mapping[left], mapping[right] = mapping.get(right, {}), mapping.get(left, {})
        for key in (left, right):
            mapping[key] = {**mapping[key], 'interviewer': speakers[key]}
    for key in (left, right):
        plan[key] = {**plan[key], 'main_order': int(key)}
    session.script = {**session.script, 'speaker_by_order': speakers, 'question_plan': plan, 'question_provenance': provenance}
    return target
