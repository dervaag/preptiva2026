"""Check real result renderer and print disclosures using synthetic data only."""
from pathlib import Path
from io import BytesIO
from playwright.sync_api import sync_playwright, expect
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page()
        page.route('http://preptiva.test/**', lambda route: route.fulfill(body='<html><body></body></html>', content_type='text/html'))
        page.goto('http://preptiva.test/')
        page.set_content('<body class="result-page" data-page="test"><main id="result-content"></main></body>')
        for name in ('workspace.css', 'result.css'):
            page.add_style_tag(path=str(ROOT / 'app/static/css' / name))
        for name in ('app.js', 'result.js'):
            page.add_script_tag(path=str(ROOT / 'app/static/js' / name))
        # Full-rubric placeholders should not look like missing results.
        visibility = dict(total_score=3, competencies=[
            dict(key='communication', name='Communication', score=3, status='measured', assessed_units=1),
            dict(key='technical', name='Technical', score=None, status='not_assessed', assessed_units=0, evidence=[]),
            dict(key='teamwork', name='Teamwork', score=None, status='insufficient', assessed_units=1),
            dict(key='analytical', name='Analytical', score=None, status='unusable_transcript', assessed_units=1),
            dict(key='adaptability', name='Adaptability', score=None, status='not_assessed', assessed_units=0),
        ], coverage=dict(measured=1,total=5,weighted_percent=20))
        page.evaluate('(data) => document.querySelector("#result-content").innerHTML = renderResult(data)', visibility)
        expect(page.locator('.result-competency')).to_have_count(2)
        assert page.locator('.result-competency h3').all_text_contents() == ['Communication', 'Analytical']
        # Keep the denominator honest; filtering cards must not fabricate full coverage.
        expect(page.locator('.result-metrics')).to_contain_text('1 dari 5 kompetensi')
        page.evaluate('document.querySelector("#result-content").innerHTML = renderResult({competencies:[{key:"technical",name:"Technical",score:null,status:"not_assessed",assessed_units:0}]})')
        expect(page.locator('.result-competency')).to_have_count(0)
        expect(page.locator('.result-competency-list')).to_contain_text('Belum ada kompetensi yang dinilai.')
        fixture = dict(total_score=None, competencies=[dict(key='technical', name='Technical', score=None,
            status='insufficient', evidence=[])], coverage=dict(measured=0, total=6, weighted_percent=0),
            review=dict(summary='Evidence is limited.', improvements=['Explain the testing steps.']),
            items=[dict(main_order=1, question_text='How did you test the API?', transcript='I used Postman <script>not code</script>.',
                persona=dict(name='Andi'), input_mode='audio', feedback=dict(better_answer_tip='Describe assertions and error cases.'),
                competency_scores=dict(technical=dict(score=2, status='insufficient', evidence=[],
                    rationale='Testing assertions and observed results were not described.')))])
        for width in (390, 1440):
            page.set_viewport_size(dict(width=width, height=900))
            page.evaluate('(data) => document.querySelector("#result-content").innerHTML = renderResult(data)', fixture)
            expect(page.locator('.result-answer .transcript')).to_be_visible()
            expect(page.locator('.result-answer-tip')).to_be_visible()
            expect(page.locator('.result-score-explanation')).to_be_visible()
            expect(page.locator('.result-evidence')).to_have_attribute('open', '')
            assert page.locator('.transcript script').count() == 0
            assert page.locator('.transcript').inner_text() == fixture['items'][0]['transcript']
            # Print expands even details the reader has manually closed, then restores them.
            page.evaluate('document.querySelectorAll("#result-content details").forEach(d => d.open = false)')
            page.evaluate('window.dispatchEvent(new Event("beforeprint"))')
            page.emulate_media(media='print')
            expect(page.locator('.result-answer .transcript')).to_be_visible()
            expect(page.locator('.result-evidence .evidence-detail')).to_be_visible()
            page.evaluate('window.dispatchEvent(new Event("afterprint"))')
            page.emulate_media(media='screen')
            assert page.locator('#result-content details[open]').count() == 0
            pdf = PdfReader(BytesIO(page.pdf()))
            printed = ' '.join(p.extract_text() for p in pdf.pages)
            assert 'I used Postman' in printed
            assert 'Testing assertions and observed results were not described.' in printed
            assert page.locator('#result-content details[open]').count() == 0
        fixture['total_score'] = 3
        fixture['items'][0]['skipped'] = True
        page.evaluate('(data) => document.querySelector("#result-content").innerHTML = renderResult(data)', fixture)
        assert page.locator('.result-score-explanation').count() == 0
        expect(page.locator('.transcript')).to_contain_text('Pertanyaan dilewati')
        # Website controls translate in both directions; candidate text is never translated.
        fixture['total_score'] = None
        fixture['items'][0]['skipped'] = False
        page.evaluate('(data) => document.querySelector("#result-content").innerHTML = renderResult(data)', fixture)
        page.add_script_tag(path=str(ROOT / 'app/static/js/ui-language.js'))
        for language, heading, title in [('en', 'No overall score available', 'Review your answers'),
                                         ('id', 'Skor belum tersedia', 'Tinjau jawaban')]:
            page.evaluate('(language) => window.PreptivaI18n.setLanguage(language)', language)
            expect(page.locator('.result-score-explanation h2')).to_have_text(heading)
            expect(page.locator('.result-answers .ws-panel-heading h2')).to_have_text(title)
            expect(page.locator('.transcript')).to_have_text(fixture['items'][0]['transcript'])
        browser.close()
        print('Result visibility passed: transcripts, feedback, null-score explanation, escaping, print and mobile.')


if __name__ == '__main__':
    main()
