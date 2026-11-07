"""Final feedback language and terminal-output contracts; no paid providers."""
import test_system  # Use an isolated database and test settings.
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from app.ai.feedback import feedback_language, validate_review
from app.ai import orchestrator


class FeedbackLanguageTests(unittest.IsolatedAsyncioTestCase):
    def test_language_snapshot_and_historical_fallback(self):
        session = SimpleNamespace(script={'settings': {'language': 'en', 'feedback_language': 'id'}})
        self.assertEqual(feedback_language(session), 'id')
        del session.script['settings']['feedback_language']
        self.assertEqual(feedback_language(session), 'en')

    async def test_final_review_repairs_questions_in_both_languages(self):
        for language, summary in [('en', 'No overall score is available.'), ('id', 'Skor keseluruhan belum tersedia.')]:
            good = dict(summary=summary, strengths=[], improvements=[], study_recommendations=[])
            bad = {**good, 'study_recommendations': [dict(topic='Practice', reason='More evidence', action='What did you do?')]}
            with self.subTest(language=language), patch('app.ai.orchestrator.complete', AsyncMock(side_effect=[bad, good])) as model:
                result = await orchestrator.summarize({'language': language, 'total_score': None, 'coverage': {'measured': 0}})
                self.assertEqual(result, good)
                self.assertEqual(model.call_count, 2)
                instruction = model.call_args.args[0]
                self.assertIn('English.' if language == 'en' else 'Bahasa Indonesia.', instruction)
                self.assertIn('interview has ended', instruction)
                self.assertIn('no overall score', instruction)

    async def test_persistent_question_output_fails_instead_of_reopening_interview(self):
        bad = dict(summary='Can you give another answer?', strengths=[], improvements=[], study_recommendations=[])
        with patch('app.ai.orchestrator.complete', AsyncMock(return_value=bad)) as model:
            with self.assertRaises(ValueError):
                await orchestrator.summarize({'language': 'en'})
            self.assertEqual(model.call_count, 2)

    async def test_answer_explanations_follow_platform_language_but_keep_original_quotes(self):
        for language in ('id', 'en'):
            with patch('app.ai.orchestrator.complete', AsyncMock(return_value={'competency_scores': {}})) as model:
                await orchestrator.evaluate({'interviewer':'user', 'language':'en' if language == 'id' else 'id',
                    'feedback_language':language, 'competencies':['technical']})
                instruction = model.call_args.args[0]
                self.assertIn('English.' if language == 'en' else 'Bahasa Indonesia.', instruction)
                self.assertIn('original language', instruction)

    async def test_per_answer_coaching_does_not_ask_another_question(self):
        bad = {'competency_scores': {}, 'feedback': {'better_answer_tip': 'How would you test errors?'}}
        good = {'competency_scores': {}, 'feedback': {'better_answer_tip': 'Describe error cases and assertions.'}}
        with patch('app.ai.orchestrator.complete', AsyncMock(side_effect=[bad, good])) as model:
            self.assertEqual(await orchestrator.evaluate({'interviewer':'user', 'language':'en'}), good)
            self.assertEqual(model.call_count, 2)
