"""Deterministic routing boundaries independent of model/provider behavior."""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import unittest

# Use the suite's isolated settings before any module can read the IDE .env.
import test_system as _isolated_system_fixture

from app.ai import guidebook
from app.ai.assessment import snapshot
from app.graphs.coordinator import apply_selection, coordinate


def fixture():
    roles = ['hr', 'user', 'manager']
    competencies = ['communication', 'communication', 'leadership', 'teamwork', 'technical', 'analytical', 'adaptability']
    texts = ['Ceritakan pengalaman belajar Anda.', 'Bagaimana Anda menjelaskan persoalan kepada rekan?',
             'Apa keputusan Anda saat memimpin kelompok?', 'Bagaimana konflik kelompok itu diselesaikan?',
             'Pemeriksaan apa yang memastikan hasilnya benar?', 'Bagaimana Anda menimbang risiko dan manfaat?',
             'Apa yang Anda pelajari setelah rencana berubah?']
    questions = [SimpleNamespace(id=i, session_id=1, kind='main', main_order=i, slot='opening' if i == 1 else 'decision',
                                 category='probe', question_text=text, expected_points=['Bukti tindakan'], competencies=[key], audio_file=None)
                 for i, (key, text) in enumerate(zip(competencies, texts), 1)]
    session = SimpleNamespace(id=1, question_count=7, max_followups=1, interviewer='hr',
        script={'settings': {'panel': roles, 'language': 'id'}, 'assessment': snapshot('hr', roles),
                'speaker_by_order': {str(i): roles[(i - 1) % 3] for i in range(1, 8)},
                'question_plan': {str(q.id): {'main_order': q.main_order, 'slot': q.slot,
                    'interviewer': roles[(q.id - 1) % 3], 'competencies': q.competencies} for q in questions},
                'question_provenance': {str(q.id): {'anchor_id': f'cv{q.id}'} for q in questions}})
    dialogue = [{'question_id': 1, 'turn_id': 'q1', 'question': texts[0], 'answer': 'Saya membagi tugas dalam proyek kuliah dan meninjau hasil bersama rekan.',
                 'interviewer': 'hr', 'competencies': ['communication']}]
    return session, questions, dialogue


class PanelCoordinatorTests(unittest.TestCase):
    def test_adaptive_swap_preserves_ids_order_panel_allocation_and_closing(self):
        session, questions, dialogue = fixture()
        before = Counter(session.script['speaker_by_order'].values())
        first, last = deepcopy(vars(questions[0])), deepcopy(vars(questions[-1]))
        decision = coordinate(session, questions, dialogue, questions[0],
                              {'action': 'next', 'response_text': 'Terima kasih. Apa pertanyaan selanjutnya?', 'next_persona': 'attacker'})
        self.assertEqual(decision['next_question_id'], 2)
        self.assertEqual(decision['selected_question_id'], 3)
        self.assertEqual(decision['next_persona'], 'manager')
        self.assertNotIn('?', decision['response_text'])
        self.assertEqual(decision['handoff']['reason'], 'coverage_priority')
        self.assertEqual(decision['coverage']['communication'], 'asked_not_yet_scored')
        self.assertEqual(decision['coverage']['leadership'], 'not_assessed')
        self.assertNotIn('measured', decision['coverage'].values())
        target = apply_selection(session, questions, decision)
        self.assertEqual(target.id, 2)
        self.assertEqual(target.main_order, 2)
        self.assertEqual(target.competencies, ['leadership'])
        self.assertEqual(questions[2].competencies, ['communication'])
        self.assertEqual(guidebook.speaker(session, 2), 'manager')
        self.assertEqual(guidebook.speaker(session, 3), 'user')
        self.assertEqual(before, Counter(session.script['speaker_by_order'].values()))
        self.assertEqual(first, vars(questions[0]))
        self.assertEqual(last, vars(questions[-1]))
        self.assertEqual([q.main_order for q in questions], list(range(1, 8)))
        self.assertEqual(session.script['question_plan']['2']['main_order'], 2)
        self.assertEqual(session.script['question_provenance']['2']['anchor_id'], 'cv3')

    def test_followup_stays_with_asking_persona_and_requires_original_quote(self):
        session, questions, dialogue = fixture()
        proposal = {'action': 'follow_up', 'response_text': 'Apa yang Anda pelajari dari pembagian tugas itu?',
                    'source_refs': [{'turn_id': 'q1', 'quote': 'Saya membagi tugas dalam proyek kuliah'}],
                    'interviewer': 'user', 'next_persona': 'manager'}
        decision = coordinate(session, questions, dialogue, questions[0], proposal)
        self.assertEqual((decision['action'], decision['interviewer'], decision['next_persona']), ('follow_up', 'hr', 'hr'))
        self.assertIsNone(decision['next_question_id'])
        for alteration in ({'source_refs': [{'turn_id': 'q999', 'quote': 'Saya membagi tugas dalam proyek kuliah'}]},
                           {'response_text': 'Tuliskan query SQL untuk tabel mahasiswa?'},
                           {'response_text': questions[0].question_text}, {'source_refs': []}):
            with self.subTest(alteration=alteration):
                actual = coordinate(session, questions, dialogue, questions[0], {**proposal, **alteration})
                self.assertEqual(actual['action'], 'next')
                self.assertEqual(actual['source_refs'], [])

    def test_followup_limit_and_unknown_actions_cannot_extend_session(self):
        session, questions, dialogue = fixture()
        followup = SimpleNamespace(**{**vars(questions[0]), 'id': 8, 'kind': 'follow_up'})
        proposal = {'action': 'follow_up', 'response_text': 'Apa yang Anda pelajari?',
                    'source_refs': [{'turn_id': 'q1', 'quote': 'Saya membagi tugas dalam proyek kuliah'}]}
        for current, rows in ((questions[0], questions + [followup]), (followup, questions + [followup])):
            decision = coordinate(session, rows, dialogue, current, proposal)
            self.assertEqual(decision['action'], 'next')
            self.assertEqual(decision['reason'], 'followup_limit')
        decision = coordinate(session, questions, dialogue, questions[0], {'action': 'finish', 'response_text': ''})
        self.assertEqual(decision['action'], 'next')
        self.assertIsNotNone(decision['next_question_id'])
        final = coordinate(session, questions, dialogue, questions[-1], {'action': 'next', 'response_text': ''})
        self.assertIsNone(final['next_question_id'])

    def test_skip_does_not_reorder_and_handoff_claims_stay_unverified(self):
        session, questions, dialogue = fixture()
        decision = coordinate(session, questions, dialogue, questions[0], {'action': 'follow_up'}, skip=True)
        self.assertEqual(decision['next_question_id'], decision['selected_question_id'])
        self.assertEqual(decision['selected_question_id'], 2)
        self.assertEqual(decision['reason'], 'question_skipped')
        self.assertEqual(decision['source_refs'], [])
        for claim in decision['handoff']['claims']:
            self.assertEqual(claim['verification_status'], 'candidate_claim_unverified')
            self.assertEqual(claim['turn_id'], 'q1')
            self.assertIn(claim['quote'], dialogue[0]['answer'])

    def test_repeated_topic_loses_priority_and_scope_corruption_is_rejected(self):
        session, questions, dialogue = fixture()
        questions[2].question_text = dialogue[0]['question']
        decision = coordinate(session, questions, dialogue, questions[0], {'action': 'next', 'response_text': 'Terima kasih.'})
        self.assertNotEqual(decision['selected_question_id'], 3)
        questions[0].competencies = ['technical']
        with self.assertRaises(ValueError):
            coordinate(session, questions, dialogue, questions[0], {'action': 'next'})


if __name__ == '__main__':
    unittest.main()
