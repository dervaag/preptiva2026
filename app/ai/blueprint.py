import random
import re
from difflib import SequenceMatcher

PERSONAS = {'hr': {'name': 'Rina', 'title': 'HR Interviewer'}, 'user': {'name': 'Andi', 'title': 'Functional / Technical Lead'}, 'manager': {'name': 'Hendra', 'title': 'Hiring Manager'}}
FOCUS = {'hr': 'Learning potential, motivation, integrity, collaboration and adaptability. Never quiz coding, SQL, syntax or algorithms.',
         'user': 'Role-specific functional/technical practice, personal contribution, diagnosis, validation and trade-offs. Do not assume software roles.',
         'manager': 'Leadership, people development, priorities, risk, business impact and functional/technical investment trade-offs. No coding quizzes.'}
SLOTS = ['opening', 'background', 'motivation', 'behavior', 'competency', 'decision', 'candidate_questions']


def blueprint(count, uuid, personas=None, guide=None, assessment=None):
    from app.ai.guidebook import snapshot
    guide = guide or snapshot()
    personas = personas or ['hr']
    indices = [0, 3, 5] if count == 3 else [0, 1, 3, 5, 6] if count == 5 else range(7)
    rng = random.Random(uuid)
    pools = {p: rng.sample(guide['roles'][p]['angles'], len(guide['roles'][p]['angles'])) for p in personas}
    job_keys = list((assessment or {}).get('weights', {})) if (assessment or {}).get('profile_id') else []
    rng.shuffle(job_keys)
    result = []
    for order, i in enumerate(indices, 1):
        persona = personas[(order - 1) % len(personas)]
        if job_keys:
            key = job_keys[(order-1) % len(job_keys)]
            definition = assessment['competency_definitions'][key]
            # The specialized purpose is fixed, while wording/examples remain CV-adaptive.
            angle = {'id':f'em.{key}.{order}', 'intent':definition['definition'], 'competencies':[key]}
        else:
            angle = pools[persona].pop()
        result.append({'slot': SLOTS[i], 'angle': angle['intent'], 'intent_id': angle['id'],
                       'competencies': angle['competencies'], 'interviewer': persona, 'main_order': order})
    return result


def forbidden_hr(text):
    technical = re.search(r'\b(SQL|syntax|sintaks|coding|algorithm|algoritma|query|arsitektur|architecture|debug|jurnal penyesuaian|rekonsiliasi)\b', text, re.I)
    if re.search(r'(optimasi query|query optimization|implementasikan|write (?:a |the )?code|tulis(?:kan)? (?:kode|query)|kompleksitas algoritma)', text, re.I):
        return True
    behavior = re.search(r'(kolaborasi|kerja sama|teamwork|collaborat|motivasi|motivation|umpan balik|feedback|konflik|conflict|perasaan|communicat|komunikasi|meminta bantuan|belajar|pelajari|learning)', text, re.I)
    return bool(technical and not behavior)


def validate_questions(questions, slots, persona, history, profile=None):
    if len(questions) != len(slots):
        raise ValueError('Jumlah pertanyaan tidak sesuai blueprint.')
    texts = []
    for q, slot in zip(questions, slots):
        text = q['question_text'].strip()
        if not text or text.count('?') > 1 or q['slot'] != slot['slot']:
            raise ValueError('Pertanyaan kosong, ganda, atau urutan tidak sesuai.')
        if persona == 'hr' and forbidden_hr(text):
            raise ValueError('Pertanyaan HR melampaui fokus persona.')
        from app.ai.scoring import WEIGHTS
        allowed = {k for k, weight in WEIGHTS[persona].items() if weight > 0}
        if not q.get('competencies') or set(q['competencies']) - allowed:
            raise ValueError('Kompetensi pertanyaan melampaui fokus persona.')
        if slot.get('competencies') and set(q['competencies']) != set(slot['competencies']):
            raise ValueError('Kompetensi harus sesuai tujuan pertanyaan pada guidebook.')
        if profile and profile.get('anchors') and q.get('anchor_id') not in {a['id'] for a in profile['anchors']}:
            raise ValueError('Pertanyaan harus merujuk bukti CV yang tersedia.')
        if profile and profile.get('career_stage') in ('student', 'fresh_graduate') and re.search(
            r'(bawahan Anda|your direct reports|perusahaan Anda sebelumnya|your previous employer|tim yang Anda kelola|team you managed)', text, re.I):
            raise ValueError('Jangan mengasumsikan pengalaman kerja/manajerial untuk kandidat pemula.')
        if any(SequenceMatcher(None, text.casefold(), old.casefold()).ratio() > .88 for old in texts):
            raise ValueError('Pertanyaan berulang dalam sesi.')
        if any(SequenceMatcher(None, text.casefold(), old.casefold()).ratio() > .92 for old in history):
            raise ValueError('Pertanyaan terlalu mirip riwayat.')
        texts.append(text)
    return questions
