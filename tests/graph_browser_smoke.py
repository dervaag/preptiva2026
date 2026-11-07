"""Run existing Chrome behavior regressions with the real LangGraph backend.

Python 3.12: python tests/graph_browser_smoke.py [panel|voice|realtime]
Every provider is synthetic; all database/audio/artifacts are temporary.
"""
import os
import sys
os.environ['ORCHESTRATION_ENGINE'] = 'langgraph'

import browser_smoke as fixture
from app.ai.blueprint import blueprint
from app.ai import model_router


async def questions(context, history):
    plan = blueprint(context['question_count'], context['uuid'], context['panel'], context['guidebook'], context['assessment'])
    text = {
        1: ['Ceritakan perjalanan karier Anda?', 'Bagaimana Anda berkolaborasi dengan tim?', 'Apa yang Anda pelajari dari perubahan?'],
        2: ['Saat mengikuti kegiatan kampus, bagaimana Anda memulai tugas yang belum dikenal?', 'Apa pertimbangan Anda ketika memilih cara menyelesaikan tugas organisasi?', 'Ceritakan cara Anda meninjau hasil kegiatan bersama rekan?'],
        3: ['Dari pengalaman selama belajar, bagaimana Anda menentukan tujuan dan rencana?', 'Bagaimana Anda memeriksa langkah kerja agar hasil proyek sesuai kebutuhan?', 'Apa yang Anda pelajari dari perubahan?'],
    }[len(context['panel'])]
    anchors = context['candidate_profile']['anchors']
    return {'intro': 'Selamat datang.', 'closing': 'Terima kasih.', 'plan': plan, 'questions': [
        {'slot': row['slot'], 'category': 'Latihan', 'question_text': text[index],
         'competencies': row['competencies'], 'expected_points': ['impact'], 'anchor_id': anchors[0]['id']}
        for index, row in enumerate(plan)]}


async def evaluate(context):
    result = await fixture_original_evaluate(context)
    result['competency_scores'] = {key: {'score': 4, 'evidence': ['Saya mengukur hasil eksperimen'],
        'evidence_sufficiency': 'sufficient'} for key in context['competencies']}
    return result


async def forbid_provider(*args, **kwargs):
    raise AssertionError('Unexpected real provider request in graph browser smoke')


fixture_original_evaluate = fixture.evaluate
fixture.questions = questions
fixture.evaluate = evaluate
model_router.provider_post = forbid_provider

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'panel'
    if mode == 'panel': fixture.main()
    elif mode == 'voice':
        from voice_mode_browser_smoke import main
        main()
    elif mode == 'realtime':
        from realtime_browser_smoke import main
        main()
    else: raise SystemExit('Choose panel, voice or realtime.')
