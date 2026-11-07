"""A closing ends the interview; it never opens an unsupported candidate Q&A."""
import re


def invites_questions(text):
    return bool(re.search(
        r'(any\s+questions|questions?\s+(?:for|to)\s+(?:us|me|the\s+(?:panel|team|interviewer))|'
        r'(?:ask|asking)\s+(?:us|me)|what\s+would\s+you\s+like\s+to\s+(?:ask|know)|'
        r'(?:anda|kamu)\s+(?:ingin|mau|boleh|dapat|bisa)\s+bertanya|'
        r'(?:ada|punya|memiliki|ajukan|mengajukan|sampaikan|menyampaikan)\s+(?:sebuah\s+|beberapa\s+)?pertanyaan|'
        r'(?:ingin|mau)\s+(?:anda\s+)?tanyakan)', text or '', re.I))


def closing_text(language):
    return ('Thank you for completing this practice interview. Your answers will now be assessed. '
            'Your scores and feedback will appear on the results page.' if language == 'en' else
            'Terima kasih telah menyelesaikan latihan wawancara ini. Jawaban Anda akan dinilai. '
            'Nilai dan umpan balik akan ditampilkan di halaman hasil.')


def public_closing(session):
    closing = dict(session.script.get('closing') or {})
    text = closing.get('text', '')
    if not text.strip() or any(mark in text for mark in ('?', '？', '؟')) or invites_questions(text):
        closing['text'] = closing_text(session.script.get('settings', {}).get('language', 'id'))
        # Old generated audio may still invite questions; never play it with corrected text.
        closing['audio_url'] = f'/api/sessions/{session.uuid}/speech/closing/0'
    return closing
