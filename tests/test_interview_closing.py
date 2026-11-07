import test_system
from types import SimpleNamespace
import unittest
from app.ai.closing import closing_text, invites_questions, public_closing
from app.ai.blueprint import blueprint, validate_questions


class InterviewClosingTests(unittest.TestCase):
    def test_no_candidate_qa_slot_in_new_sessions(self):
        for count in (3, 5, 7):
            slots = blueprint(count, 'closing-policy-test')
            self.assertEqual(len(slots), count)
            self.assertNotIn('candidate_questions', [slot['slot'] for slot in slots])

    def test_bilingual_invitations_rejected_as_interview_questions(self):
        for text in ['Do you have any questions for us?', 'Feel free to ask me about the role.',
                     'Apakah Anda memiliki pertanyaan untuk kami?', 'Silakan ajukan pertanyaan kepada panel.',
                     'Apa yang ingin Anda tanyakan?']:
            with self.subTest(text=text):
                self.assertTrue(invites_questions(text))
                with self.assertRaises(ValueError):
                    validate_questions([{'question_text':text, 'slot':'reflection', 'competencies':['teamwork']}],
                        [{'slot':'reflection', 'competencies':['teamwork']}], 'hr', [])

    def test_old_closing_uses_matching_safe_text_and_streamed_audio(self):
        for language in ('id', 'en'):
            session = SimpleNamespace(uuid='test-session', script={'settings':{'language':language},
                'closing': {'text':'Do you have any questions for us?', 'audio_url':'/old-closing.mp3', 'persona':{'name':'Andi'}}})
            result = public_closing(session)
            self.assertEqual(result['text'], closing_text(language))
            self.assertEqual(result['audio_url'], '/api/sessions/test-session/speech/closing/0')
            self.assertEqual(result['persona'], {'name':'Andi'})
            self.assertNotIn('?', result['text'])
            self.assertEqual(session.script['closing']['audio_url'], '/old-closing.mp3')

    def test_safe_existing_closing_audio_is_preserved(self):
        original = {'text':'Terima kasih telah menyelesaikan sesi.', 'audio_url':'/safe.mp3'}
        self.assertEqual(public_closing(SimpleNamespace(script={'closing':original}, uuid='test')), original)
