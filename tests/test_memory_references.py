"""Conversation grounding keeps short answers usable without weakening evidence."""
# Set isolated database/environment settings before importing any application module.
import test_system as _isolated_system_fixture

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.ai import memory, orchestrator
from app.ai.scoring import verified_scores


def context_for(answer):
    session = SimpleNamespace(script={'assessment': {'weights': {'communication': 100}}})
    question = SimpleNamespace(id=1, question_text='Apa pengalaman Anda?',
                               competencies=['communication'], kind='main', slot='opening')
    turn = {'turn_id': 'q1', 'question_id': 1, 'interviewer': 'hr',
            'question': question.question_text, 'answer': answer, 'competencies': question.competencies}
    return memory.packet(session, [turn], question, 'hr')


class MemoryReferenceTests(unittest.TestCase):
    def assert_invalid(self, refs, context):
        with self.assertRaises(memory.ReferenceValidationError) as caught:
            memory.validate_refs(refs, context, required=True)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(caught.exception.reason, 'reference_invalid')

    def test_complete_short_answers_from_real_packets_are_valid_references(self):
        for answer in ('Ya', 'Tidak', 'Belum.', 'No.', 'Iya!'):
            with self.subTest(answer=answer):
                context = context_for(answer)
                self.assertFalse(context['recent_turns'][0]['is_excerpt'])
                refs = memory.reference_options(context)
                self.assertEqual(refs, [{'turn_id': 'q1', 'quote': answer}])
                self.assertEqual(memory.validate_refs(refs, context, required=True), refs)

    def test_whitespace_normalization_still_requires_a_literal_quote(self):
        answer = ' \tBelum.\n'
        context = context_for(answer)
        for quote in (answer, answer.strip()):
            refs = [{'turn_id': 'q1', 'quote': quote}]
            self.assertEqual(memory.validate_refs(refs, context, required=True), refs)
        self.assert_invalid([{'turn_id': 'q1', 'quote': '  Belum.  '}], context_for('Belum.'))

    def test_short_substrings_of_longer_answers_are_rejected(self):
        context = context_for('Belum. Saya sedang mempersiapkan proyek berikutnya.')
        self.assert_invalid([{'turn_id': 'q1', 'quote': 'Belum.'}], context)
        self.assert_invalid([{'turn_id': 'q1', 'quote': 'belum.'}], context_for('Belum.'))

    def test_short_excerpt_is_not_mistaken_for_a_complete_answer(self):
        context = context_for('Belum. ' + 'Pengalaman belajar ' * 90 + '.')
        turn = context['recent_turns'][0]
        self.assertTrue(turn['is_excerpt'])
        # A legacy/externally supplied short excerpt remains invalid even
        # though current packet construction now retains a useful passage.
        turn.update(answer='Belum.', source_quotes=['Belum.'])
        self.assert_invalid([{'turn_id': 'q1', 'quote': 'Belum.'}], context)
        # Without an explicit non-excerpt marker, a short source is not trusted
        # as the whole original answer either.
        del turn['is_excerpt']
        self.assert_invalid([{'turn_id': 'q1', 'quote': 'Belum.'}], context)

    def test_long_answers_with_short_fragments_keep_usable_grounding(self):
        answers = ('Belum. ' + 'Pengalaman belajar ' * 90 + '.',
                   'Ya. Tidak. Belum. ' * 90,
                   'Ya.\n' + 'Pengalaman belajar ' * 90 + '.',
                   'Ya. Saya membagi tugas dalam proyek kuliah. ' * 90)
        for answer in answers:
            with self.subTest(answer=answer[:50]):
                context = context_for(answer)
                self.assertTrue(context['recent_turns'][0]['is_excerpt'])
                refs = memory.reference_options(context)
                self.assertTrue(refs)
                for ref in refs:
                    self.assertGreaterEqual(len(ref['quote'].strip()), 8)
                    self.assertIn(ref['quote'], answer)
                    self.assertEqual(memory.validate_refs([ref], context, required=True), [ref])

    def test_word_boundary_truncation_does_not_leave_a_short_first_word(self):
        for size in (400, 1300):
            answer = 'Ya ' + 'x' * size
            context = context_for(answer)
            refs = memory.reference_options(context)
            self.assertTrue(refs)
            for ref in refs:
                self.assertGreaterEqual(len(ref['quote'].strip()), 8)
                self.assertLessEqual(len(ref['quote']), 220)
                self.assertIn(ref['quote'], answer)
                self.assertEqual(memory.validate_refs([ref], context, required=True), [ref])

    def test_long_literal_references_still_work_and_are_deduplicated(self):
        context = context_for('Saya membagi tugas dan meninjau hasil bersama tim.')
        ref = {'turn_id': 'q1', 'quote': 'membagi tugas dan meninjau hasil'}
        self.assertEqual(memory.validate_refs([ref, {**ref, 'extra': 'ignored'}], context, required=True), [ref])
        self.assert_invalid([{**ref, 'turn_id': 'q999'}], context)
        self.assert_invalid([{**ref, 'quote': 'Saya memimpin seratus karyawan.'}], context)
        excerpt = context_for('Saya membagi tugas. ' * 150)
        self.assertTrue(excerpt['recent_turns'][0]['is_excerpt'])
        valid = [{'turn_id': 'q1', 'quote': 'Saya membagi tugas.'}]
        self.assertEqual(memory.validate_refs(valid, excerpt, required=True), valid)

    def test_bad_reference_shapes_raise_controlled_errors(self):
        context = context_for('Saya membagi tugas dalam proyek kuliah.')
        invalid = (None, {}, 'private-input-marker', (), [None], [[]], ['private-input-marker'],
                   [{}], [{'turn_id': ['q1'], 'quote': 'Saya membagi tugas'}],
                   [{'turn_id': {'id': 'q1'}, 'quote': 'Saya membagi tugas'}],
                   [{'turn_id': 1, 'quote': 'Saya membagi tugas'}],
                   [{'turn_id': 'q1', 'quote': None}], [{'turn_id': 'q1', 'quote': {}}],
                   [{'turn_id': 'q1'}], [{'turn_id': 'q1', 'quote': ' \n '}])
        for refs in invalid:
            with self.subTest(refs=refs):
                self.assert_invalid(refs, context)
                try:
                    memory.validate_refs(refs, context)
                except memory.ReferenceValidationError as exc:
                    self.assertNotIn('private-input-marker', str(exc))

    def test_bad_context_shapes_raise_controlled_errors(self):
        ref = [{'turn_id': 'q1', 'quote': 'Saya membagi tugas'}]
        invalid = (None, [], {'recent_turns': None}, {'recent_turns': [None]},
                   {'recent_turns': [{'turn_id': [], 'answer': 'Saya membagi tugas'}]},
                   {'recent_turns': [{'turn_id': 'q1', 'answer': None}]},
                   {'recent_turns': [{'turn_id': 'q1', 'answer': 'Saya membagi tugas', 'source_quotes': None}]},
                   {'recent_turns': [{'turn_id': 'q1', 'answer': 'Saya membagi tugas', 'source_quotes': [None]}]})
        for context in invalid:
            with self.subTest(context=context):
                self.assert_invalid(ref, context)

    def test_empty_answers_need_no_reference_but_nonempty_answers_do(self):
        for answer in ('', ' \t\n '):
            context = context_for(answer)
            self.assertEqual(memory.reference_options(context), [])
            self.assertEqual(memory.validate_refs([], context, required=True), [])
            self.assert_invalid([{'turn_id': 'q1', 'quote': answer}], context)
        with self.assertRaises(memory.ReferenceValidationError) as caught:
            memory.validate_refs([], context_for('Belum.'), required=True)
        self.assertEqual(caught.exception.reason, 'reference_required')

    def test_short_conversation_quote_does_not_become_scoring_evidence(self):
        value = {'communication': {'score': 5, 'evidence': ['Belum.'], 'evidence_sufficiency': 'sufficient'}}
        scores = verified_scores(value, 'Belum.', ['communication'], [{'turn_id': 'q1', 'transcript': 'Belum.'}])
        self.assertEqual(scores['communication']['source_refs'], [])
        self.assertNotEqual(scores['communication']['status'], 'measured')


class MemoryAdaptationTests(unittest.IsolatedAsyncioTestCase):
    async def test_long_answer_can_ground_adaptation_using_offered_reference(self):
        context = context_for('Belum. ' + 'Pengalaman belajar ' * 90 + '.')
        planned = {'slot': 'behavior', 'category': 'Komunikasi',
                   'question_text': 'Bagaimana Anda menjelaskan hasil belajar kepada rekan?',
                   'expected_points': ['Contoh komunikasi'], 'competencies': ['communication']}
        revised = {**planned, 'source_refs': memory.reference_options(context)}
        complete = AsyncMock(return_value={'question': revised})
        with patch('app.ai.orchestrator.complete', complete):
            result = await orchestrator.adapt_question({'interviewer': 'hr', 'language': 'id',
                'planned_question': planned, 'asked_questions': [], 'context_packet': context})
        self.assertEqual(complete.await_count, 1)
        self.assertEqual(result['source_refs'], revised['source_refs'])


if __name__ == '__main__':
    unittest.main()
