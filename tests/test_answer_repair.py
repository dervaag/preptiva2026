"""Model-output repair contracts, using synthetic answers and no provider calls."""
import test_system  # Establish the isolated database/environment before app imports.

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.ai import memory, orchestrator
from app.ai.errors import ProviderError
from app.ai.guidebook import role_context


class AnswerRepairTests(unittest.IsolatedAsyncioTestCase):
    def context(self, answer='Belum.'):
        context = role_context(test_system.GuidebookTests().context(), 'hr')
        question = SimpleNamespace(id=1, question_text='Apakah Anda pernah menerima masukan untuk proyek kampus?',
                                   competencies=['teamwork'], kind='main', slot='behavior')
        session = SimpleNamespace(script={'assessment': test_system.snapshot('hr')})
        turns = [{'turn_id': 'q1', 'question_id': 1, 'interviewer': 'hr', 'question': question.question_text,
                  'answer': answer, 'competencies': question.competencies}]
        context.update(context_packet=memory.packet(session, turns, question, 'hr'),
                       allow_followup=True, is_last=False,
                       planned_question={'slot': 'behavior', 'category': 'Kolaborasi',
                                         'question_text': 'Bagaimana Anda membagi tugas dalam proyek kampus?',
                                         'anchor_id': 'cv1', 'expected_points': ['Contoh konkret'],
                                         'competencies': ['teamwork']},
                       asked_questions=[question.question_text])
        return context

    def followup(self, quote='Belum.'):
        return {'action': 'follow_up', 'response_text': 'Bagaimana Anda akan meminta masukan pada proyek berikutnya?',
                'source_refs': [{'turn_id': 'q1', 'quote': quote}]}

    def adaptation(self, context, quote='Belum.'):
        return {'question': {**context['planned_question'],
                             'question_text': 'Bagaimana Anda akan menyepakati pembagian tugas bersama tim proyek?',
                             'source_refs': [{'turn_id': 'q1', 'quote': quote}]}}

    async def test_short_actual_answer_can_ground_followup_and_adaptation(self):
        context = self.context()
        for operation, output in ((orchestrator.respond, self.followup()),
                                  (orchestrator.adapt_question, self.adaptation(context))):
            with self.subTest(operation=operation.__name__), patch('app.ai.orchestrator.complete', return_value=output) as call:
                result = await operation(context)
            self.assertEqual(result['source_refs'], [{'turn_id': 'q1', 'quote': 'Belum.'}])
            self.assertEqual(call.call_count, 1)

    async def test_response_repairs_schema_and_action_once(self):
        malformed = [{'action': 'unknown', 'response_text': 'PRIVATE-MODEL-OUTPUT'},
                     {'action': {'private': 'PRIVATE-MODEL-OUTPUT'}, 'response_text': 'Something'},
                     {'action': 'next'}, [], None]
        for output in malformed:
            requests = []
            results = iter([output, self.followup()])

            async def complete(instruction, data, **kwargs):
                requests.append(copy.deepcopy(data))
                return next(results)

            with self.subTest(output=output), patch('app.ai.orchestrator.complete', side_effect=complete) as call, self.assertLogs('preptiva', level='INFO') as logs:
                result = await orchestrator.respond(self.context())
            self.assertEqual(call.call_count, 2)
            self.assertEqual(result['action'], 'follow_up')
            self.assertNotIn('PRIVATE-MODEL-OUTPUT', requests[1]['repair_required'])
            self.assertNotIn('PRIVATE-MODEL-OUTPUT', '\n'.join(logs.output))
            self.assertIn('ai_output_rejected', '\n'.join(logs.output))

    async def test_disallowed_probe_discards_ungrounded_text_and_references(self):
        for language in ('id', 'en'):
            for action in ('follow_up', 'redirect'):
                context = {**self.context(), 'allow_followup': False, 'language': language}
                output = {'action': action, 'response_text': 'PRIVATE-FABRICATED-PROBE',
                          'source_refs': 'invalid reference shape'}
                with self.subTest(language=language, action=action), patch('app.ai.orchestrator.complete', return_value=output) as call:
                    result = await orchestrator.respond(context)
                self.assertEqual(result, {'action': 'next', 'response_text': 'Terima kasih.' if language == 'id' else 'Thank you.',
                                          'source_refs': []})
                self.assertEqual(call.call_count, 1)

    async def test_two_bad_references_fail_with_controlled_reason(self):
        context = self.context()
        for operation, output in ((orchestrator.respond, self.followup('PRIVATE-FABRICATED-QUOTE')),
                                  (orchestrator.adapt_question, self.adaptation(context, 'PRIVATE-FABRICATED-QUOTE'))):
            with self.subTest(operation=operation.__name__), patch('app.ai.orchestrator.complete', return_value=output) as call, self.assertLogs('preptiva', level='INFO') as logs:
                with self.assertRaises(orchestrator.ModelOutputError) as caught:
                    await operation(context)
            self.assertEqual(call.call_count, 2)
            self.assertEqual(caught.exception.stage, operation.__name__)
            self.assertEqual(caught.exception.reason, 'reference_invalid')
            self.assertNotIn('PRIVATE', str(caught.exception))
            self.assertNotIn('PRIVATE-FABRICATED-QUOTE', '\n'.join(logs.output))

    async def test_missing_required_reference_has_distinct_reason(self):
        with patch('app.ai.orchestrator.complete', return_value={**self.followup(), 'source_refs': []}) as call:
            with self.assertRaises(orchestrator.ModelOutputError) as caught:
                await orchestrator.respond(self.context())
        self.assertEqual(caught.exception.reason, 'reference_required')
        self.assertEqual(call.call_count, 2)

    async def test_two_invalid_actions_stop_after_two_attempts(self):
        with patch('app.ai.orchestrator.complete', return_value={'action': 'invalid', 'response_text': 'Text'}) as call:
            with self.assertRaises(orchestrator.ModelOutputError) as caught:
                await orchestrator.respond(self.context())
        self.assertEqual(caught.exception.reason, 'action_invalid')
        self.assertEqual(call.call_count, 2)

    async def test_adaptation_repairs_bad_schema_but_never_falls_back_to_unvalidated_plan(self):
        context = self.context()
        for bad in ({}, [], {'question': None}, {'question': {'slot': 'behavior'}}):
            with self.subTest(bad=bad), patch('app.ai.orchestrator.complete', side_effect=[bad, self.adaptation(context)]) as call:
                result = await orchestrator.adapt_question(context)
            self.assertEqual(call.call_count, 2)
            self.assertNotEqual(result['question_text'], context['planned_question']['question_text'])
        output = self.adaptation(context)
        output['question']['question_text'] = context['asked_questions'][0]
        with patch('app.ai.orchestrator.complete', return_value=output) as call:
            with self.assertRaises(orchestrator.ModelOutputError) as caught:
                await orchestrator.adapt_question(context)
        self.assertEqual(caught.exception.reason, 'question_constraints')
        self.assertEqual(call.call_count, 2)

    async def test_repeated_hr_scope_violation_keeps_safe_acknowledgment(self):
        output = {**self.followup(), 'response_text': 'Bagaimana optimasi query SQL?'}
        with patch('app.ai.orchestrator.complete', return_value=output) as call:
            result = await orchestrator.respond(self.context())
        self.assertEqual(call.call_count, 2)
        self.assertEqual(result, {'action': 'next', 'response_text': 'Terima kasih.', 'source_refs': []})

    async def test_provider_and_runtime_failures_are_not_output_repair(self):
        for operation in (orchestrator.respond, orchestrator.adapt_question):
            for error in (ProviderError('Provider unavailable'), RuntimeError('Runtime unavailable')):
                with self.subTest(operation=operation.__name__, error=type(error).__name__), patch('app.ai.orchestrator.complete', side_effect=error) as call:
                    with self.assertRaises(type(error)) as caught:
                        await operation(self.context())
                self.assertIs(caught.exception, error)
                self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
