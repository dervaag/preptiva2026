import random
import re
from difflib import SequenceMatcher

PERSONAS = {'hr': {'name': 'Rina', 'title': 'HR Interviewer'}, 'user': {'name': 'Andi', 'title': 'Functional / Technical Lead'}, 'manager': {'name': 'Hendra', 'title': 'Hiring Manager'}}
FOCUS = {'hr': 'Learning potential, motivation, integrity, collaboration and adaptability. Never quiz coding, SQL, syntax or algorithms.',
         'user': 'Role-specific functional/technical practice, personal contribution, diagnosis, validation and trade-offs. Do not assume software roles.',
         'manager': 'Leadership, people development, priorities, risk, business impact and functional/technical investment trade-offs. No coding quizzes.'}
SLOTS = ['opening', 'background', 'motivation', 'behavior', 'competency', 'decision', 'candidate_questions']
ANGLES = ['a recent challenge', 'an unexpected constraint', 'a disagreement', 'a lesson learned', 'a measurable improvement', 'a first decision', 'a change of plan', 'a difficult priority', 'feedback received']


def blueprint(count, uuid):
    indices = [0, 3, 5] if count == 3 else [0, 1, 3, 5, 6] if count == 5 else range(7)
    angles = random.Random(uuid).sample(ANGLES, count)
    return [{'slot': SLOTS[i], 'angle': angle} for i, angle in zip(indices, angles)]


def forbidden_hr(text):
    return bool(re.search(r'\b(SQL|syntax|sintaks|coding|algorithm|algoritma|query optimization|optimasi query)\b', text, re.I))


def validate_questions(questions, slots, persona, history):
    if len(questions) != len(slots):
        raise ValueError('Jumlah pertanyaan tidak sesuai blueprint.')
    texts = []
    for q, slot in zip(questions, slots):
        text = q['question_text'].strip()
        if not text or text.count('?') > 1 or q['slot'] != slot['slot']:
            raise ValueError('Pertanyaan kosong, ganda, atau urutan tidak sesuai.')
        if persona == 'hr' and forbidden_hr(text):
            raise ValueError('Pertanyaan HR melampaui fokus persona.')
        if any(SequenceMatcher(None, text.casefold(), old.casefold()).ratio() > .88 for old in texts):
            raise ValueError('Pertanyaan berulang dalam sesi.')
        if any(SequenceMatcher(None, text.casefold(), old.casefold()).ratio() > .92 for old in history):
            raise ValueError('Pertanyaan terlalu mirip riwayat.')
        texts.append(text)
    return questions
