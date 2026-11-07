"""Isolated dashboard/history browser checks; no interview or provider requests."""
import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import re
import socket
import threading
import time
from uuid import UUID

import browser_smoke as fixture
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import select

from app.models import InterviewAnswer, InterviewQuestion, InterviewSession, SessionCompetency, User
from app.services.interview import session_item


async def seed_workspace():
    await fixture.seed()
    sessions = []
    scored = {0: 2.5, 4: 3.5, 10: None, 14: 4.5}
    other_statuses = ('preparing', 'ready', 'running', 'scoring', 'failed')
    async with fixture.SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == 'demo@interview.local'))
        user.name = 'Kandidat' + 'Panjang' * 15
        for index in range(15):
            created = datetime(2025, 1, 1, 10) + timedelta(days=index)
            status = 'done' if index in scored else other_statuses[index % len(other_statuses)]
            session = InterviewSession(
                uuid=str(UUID(int=index + 1)), user_id=user.id,
                candidate_name='Kandidat Uji', gender='male', age=28,
                job_role='P' * 140 if index == 13 else f'Product Designer {index:02d}',
                level='middle', industry='Technology',
                company='Needle Research' if index == 14 else 'Perusahaan' + 'Panjang' * 18,
                job_description='Research and design accessible products with measurable outcomes.',
                cv_text='Experience designing and researching products. ' * 8,
                interviewer=('hr', 'user', 'manager')[index % 3], question_count=3,
                status=status, total_score=scored.get(index), created_at=created,
                finished_at=created + timedelta(minutes=10) if status == 'done' else None,
                script={'assessment': {'weights': {'communication': 25, 'technical': 0, 'teamwork': 75},
                                       'version': 'workspace-test', 'sha256': 'test', 'validated': False}},
            )
            db.add(session)
            sessions.append(session)
        await db.flush()
        db.add_all([
            SessionCompetency(session_id=sessions[0].id, competency='technical', weight=50, score=4.5),
            SessionCompetency(session_id=sessions[0].id, competency='communication', weight=50, score=2.5),
            SessionCompetency(session_id=sessions[4].id, competency='communication', weight=100, score=3.5),
            SessionCompetency(session_id=sessions[14].id, competency='communication', weight=25, score=3.0),
            SessionCompetency(session_id=sessions[14].id, competency='technical', weight=0, score=4.5),
            SessionCompetency(session_id=sessions[14].id, competency='teamwork', weight=75, score=5.0),
        ])
        question = InterviewQuestion(session_id=sessions[14].id, main_order=1,
                                     question_text='Describe your contribution to a team project.')
        db.add(question)
        await db.flush()
        db.add(InterviewAnswer(
            question_id=question.id, transcript='I worked with the team and measured the outcome.',
            duration_sec=30, response_action='next', response_text='Thank you.',
            competency_scores={key: {'score': score, 'evidence': ['I worked with the team']}
                               for key, score in {'communication': 3.0, 'technical': 4.5, 'teamwork': 5.0}.items()},
        ))
        await db.commit()
    return sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    if args.screenshots_dir:
        args.screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Reuse the fixture's temporary database, but keep even incidental storage in its directory.
    from app import storage
    storage.ROOT = Path(fixture.temporary.name)
    sessions = asyncio.run(seed_workspace())
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f'http://127.0.0.1:{port}'
    server = fixture.uvicorn.Server(fixture.uvicorn.Config(
        fixture.app, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    assert server.started, 'Isolated workspace server did not start'

    errors, forbidden_requests, result_requests = [], [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def block_interview_requests(route):
                request = route.request
                if request.method != 'GET' or ('/api/sessions/' in request.url and not request.url.endswith('/result')):
                    forbidden_requests.append(f'{request.method} {request.url}')
                    route.abort()
                else:
                    if request.url.endswith('/result'):
                        result_requests.append(request.url)
                    route.continue_()

            page.route('**/api/sessions**', block_interview_requests)

            def screenshot(name):
                if args.screenshots_dir:
                    page.screenshot(path=str(args.screenshots_dir / name), full_page=True)

            def assert_layout(label):
                for width in (320, 390, 768, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{label} overflows at {width}'
                    expect(page.locator('.workspace-header')).to_be_visible()
                    if width == 390:
                        screenshot(f'{label}-stress-mobile.png')
                screenshot(f'{label}-stress-desktop.png')

            def choose(name, value):
                page.locator(f'#setup-select-{name}-trigger').click()
                page.locator(f'#setup-select-{name}-menu [data-value="{value}"]').click()
                expect(page.locator(f'input[name="{name}"]')).to_have_value(value)

            def rows():
                return page.locator('#history-list .ws-session-row')

            def expected_href(session):
                destination = 'hasil' if session.status in ('done', 'scoring') else 'ruang'
                return f'/sesi/{session.uuid}/{destination}'

            def tab(status):
                page.locator(f'#history-tabs [data-history-status="{status}"]').click()

            page.goto(base + '/dev-login')
            page.goto(base + '/dashboard')
            expect(page.locator('body')).to_have_class(re.compile(r'\bworkspace-page\b'))
            expect(page.locator('#stat-completed')).to_have_text('4')
            expect(page.locator('#stat-average')).to_contain_text(re.compile(r'\b70\b'))
            expect(page.locator('#stat-best')).to_contain_text(re.compile(r'\b90\b'))
            expect(page.locator('#stat-change')).to_contain_text('+40')
            expect(page.locator('#trend-chart svg')).to_have_count(1)
            for value in (50, 70, 90):
                expect(page.locator('#trend-chart svg')).to_have_attribute('aria-label', re.compile(rf'\b{value}\b'))
            expect(page.locator('#focus-content')).to_contain_text('Komunikasi')
            expect(page.locator('#focus-content .ws-focus-item').filter(has_text='Komunikasi').locator('.ws-focus-score')).to_have_text('60/100')
            expect(page.locator('#focus-content')).not_to_contain_text(re.compile(r'technical|teknis', re.I))
            expect(page.locator('#recent-sessions .ws-session-row')).to_have_count(5)
            for position, session in enumerate(reversed(sessions[-5:])):
                expect(page.locator('#recent-sessions .ws-session-row').nth(position)).to_have_attribute('href', expected_href(session))
            assert_layout('dashboard')

            page.goto(base + '/riwayat')
            expect(rows()).to_have_count(8)
            expect(page.locator('#history-count')).to_have_text('15 dari 15 latihan')
            for status in ('all', 'done', 'active', 'failed'):
                count = sum(status == 'all' or session.status == status or
                            (status == 'active' and session.status in ('preparing', 'ready', 'running', 'scoring'))
                            for session in sessions)
                expect(page.locator(f'#history-tabs [data-history-status="{status}"] [data-count]')).to_have_text(str(count))
            expect(rows().first).to_have_attribute('href', expected_href(sessions[-1]))
            expect(page.locator('#history-prev')).to_be_disabled()
            expect(page.locator('#history-next')).to_be_enabled()
            page.locator('#history-next').click()
            expect(rows()).to_have_count(7)
            expect(page.locator('#history-next')).to_be_disabled()
            expect(page.locator('#history-prev')).to_be_enabled()

            tab('done')
            expect(rows()).to_have_count(4)
            expect(page.locator('#history-prev')).to_be_disabled()
            expect(page.locator('#history-next')).to_be_disabled()
            for session in (session for session in sessions if session.status == 'done'):
                expect(page.locator(f'#history-list a[href="{expected_href(session)}"]')).to_have_count(1)
            null_score = page.locator(f'#history-list a[href="{expected_href(sessions[10])}"]')
            expect(null_score.locator('.ws-session-score')).to_have_text('-')
            expect(null_score).not_to_contain_text(re.compile(r'/\s*100'))

            active_sessions = [session for session in sessions if session.status in ('preparing', 'ready', 'running', 'scoring')]
            tab('active')
            expect(rows()).to_have_count(min(8, len(active_sessions)))
            active_hrefs = {expected_href(session) for session in active_sessions}
            assert set(rows().evaluate_all('(els) => els.map(el => el.getAttribute("href"))')) <= active_hrefs
            tab('failed')
            failed = [session for session in sessions if session.status == 'failed']
            expect(rows()).to_have_count(len(failed))
            assert set(rows().evaluate_all('(els) => els.map(el => el.getAttribute("href"))')) == {expected_href(session) for session in failed}

            tab('all')
            page.locator('#history-next').click()
            page.locator('#history-search').fill('Needle Research')
            expect(rows()).to_have_count(1)
            expect(rows().first).to_have_attribute('href', expected_href(sessions[14]))
            expect(page.locator('#history-prev')).to_be_disabled()
            page.locator('#history-search').fill('no session matches this query')
            expect(rows()).to_have_count(0)
            page.locator('#history-reset').click()
            expect(page.locator('#history-search')).to_have_value('')
            expect(rows()).to_have_count(8)

            choose('history_interviewer', 'hr')
            hr_sessions = [session for session in sessions if session.interviewer == 'hr']
            expect(rows()).to_have_count(len(hr_sessions))
            assert set(rows().evaluate_all('(els) => els.map(el => el.getAttribute("href"))')) == {expected_href(session) for session in hr_sessions}
            page.locator('#setup-select-history_interviewer-trigger').focus()
            page.keyboard.press('Space')
            page.keyboard.press('End')
            page.keyboard.press('Enter')
            expect(page.locator('[name=history_interviewer]')).to_have_value('manager')
            expect(rows()).to_have_count(5)
            page.locator('#history-reset').click()
            expect(page.locator('[name=history_interviewer]')).to_have_value('all')
            choose('history_sort', 'oldest')
            expect(rows().first).to_have_attribute('href', expected_href(sessions[0]))
            choose('history_sort', 'score')
            expect(rows().first).to_have_attribute('href', expected_href(sessions[14]))
            expect(rows().nth(1)).to_have_attribute('href', expected_href(sessions[4]))
            expect(rows().nth(2)).to_have_attribute('href', expected_href(sessions[0]))
            page.locator('#history-reset').click()
            expect(page.locator('[name=history_sort]')).to_have_value('newest')
            expect(rows()).to_have_count(8)
            assert_layout('history')

            failing = True

            def dashboard_failure(route):
                if failing:
                    route.fulfill(status=503, content_type='application/json', body='{"detail":"Workspace test unavailable"}')
                else:
                    route.fallback()

            page.route('**/api/sessions', dashboard_failure)
            page.goto(base + '/dashboard')
            expect(page.locator('#workspace-error')).to_be_visible()
            failing = False
            page.locator('#workspace-retry').click()
            expect(page.locator('#stat-average')).to_contain_text(re.compile(r'\b70\b'))
            expect(page.locator('#workspace-error')).not_to_be_visible()
            page.unroute('**/api/sessions', dashboard_failure)

            focus_failing = True

            def focus_failure(route):
                if focus_failing:
                    route.fulfill(status=503, content_type='application/json', body='{"detail":"Focus test unavailable"}')
                else:
                    route.fallback()

            page.route(f'**/api/sessions/{sessions[14].uuid}/result', focus_failure)
            page.reload()
            expect(page.locator('#stat-average')).to_contain_text(re.compile(r'\b70\b'))
            expect(page.locator('#workspace-error')).not_to_be_visible()
            expect(page.locator('#focus-retry')).to_be_visible()
            expect(page.locator('#focus-content a')).to_have_attribute('href', expected_href(sessions[14]))
            focus_failing = False
            page.locator('#focus-retry').click()
            expect(page.locator('#focus-content')).to_contain_text('Komunikasi')
            expect(page.locator('#focus-content .ws-focus-item').filter(has_text='Komunikasi').locator('.ws-focus-score')).to_have_text('60/100')
            expect(page.locator('#focus-retry')).to_have_count(0)
            page.unroute(f'**/api/sessions/{sessions[14].uuid}/result', focus_failure)

            history_failing = True

            def history_failure(route):
                if history_failing:
                    route.fulfill(status=503, content_type='application/json', body='{"detail":"History test unavailable"}')
                else:
                    route.fallback()

            page.route('**/api/sessions', history_failure)
            page.goto(base + '/riwayat')
            expect(page.locator('#workspace-error')).to_be_visible()
            history_failing = False
            page.locator('#workspace-retry').click()
            expect(rows()).to_have_count(8)
            expect(page.locator('#workspace-error')).not_to_be_visible()
            page.unroute('**/api/sessions', history_failure)

            scenario_items = [session_item(session) for session in sessions]
            scenario_results = []
            scenario_competencies = [{'key': 'communication', 'score': 1.5, 'weight': 25}]

            def scenario_sessions(route):
                if route.request.method == 'GET':
                    route.fulfill(json={'items': scenario_items})
                else:
                    block_interview_requests(route)

            def scenario_result(route):
                if route.request.method != 'GET':
                    block_interview_requests(route)
                    return
                session_id = route.request.url.rsplit('/', 2)[-2]
                scenario_results.append(session_id)
                route.fulfill(json={'session_id': session_id, 'competencies': scenario_competencies})

            page.route('**/api/sessions', scenario_sessions)
            page.route('**/api/sessions/*/result', scenario_result)
            # Completion order deliberately reverses creation order for the scored sessions.
            for item in scenario_items:
                if item['id'] == sessions[14].uuid:
                    item['finished_at'] = '2025-02-01T10:00:00Z'
                elif item['id'] == sessions[4].uuid:
                    item['finished_at'] = '2025-02-02T10:00:00Z'
                elif item['id'] == sessions[0].uuid:
                    item['finished_at'] = '2025-02-03T10:00:00Z'
            page.goto(base + '/dashboard')
            expect(page.locator('#stat-change')).to_have_text('-40')
            expect(page.locator('#stat-change')).to_have_attribute('data-direction', 'down')
            expect(page.locator('#trend-chart svg')).to_have_attribute('aria-label', re.compile(r'90, 70, 50'))
            expect(page.locator('#focus-content .ws-focus-score')).to_have_text('30/100')
            expect(page.locator('#focus-content a')).to_have_attribute('href', expected_href(sessions[0]))
            assert scenario_results == [sessions[0].uuid], scenario_results
            expect(page.locator('#recent-sessions .ws-session-row').first).to_have_attribute('href', expected_href(sessions[14]))
            page.goto(base + '/riwayat')
            expect(rows().first).to_have_attribute('href', expected_href(sessions[14]))

            scenario_items = [session_item(sessions[14])]
            scenario_competencies = [{'key': 'communication', 'score': 3.0, 'weight': 25}]
            page.goto(base + '/dashboard')
            expect(page.locator('#stat-completed')).to_have_text('1')
            expect(page.locator('#stat-average')).to_have_text('90')
            expect(page.locator('#stat-best')).to_have_text('90')
            expect(page.locator('#stat-change')).to_have_text('-')
            expect(page.locator('#trend-range')).to_have_text('1 sesi dinilai')
            expect(page.locator('#trend-chart .ws-trend-point')).to_have_count(1)
            expect(page.locator('#trend-chart .ws-trend-line')).to_have_count(0)
            expect(page.locator('#focus-content .ws-focus-score')).to_have_text('60/100')

            scenario_competencies = [{'key': 'communication', 'score': None, 'weight': 25},
                                     {'key': 'technical', 'score': 5.0, 'weight': 0}]
            page.reload()
            expect(page.locator('#stat-average')).to_have_text('90')
            expect(page.locator('#focus-content')).to_contain_text('Belum ada kompetensi terukur')
            expect(page.locator('#focus-content .ws-focus-item')).to_have_count(0)
            expect(page.locator('#focus-content a')).to_have_attribute('href', expected_href(sessions[14]))
            expect(page.locator('#focus-retry')).to_have_count(0)

            scenario_items = [{**session_item(session), 'total_score': None}
                              for session in sessions if session.status == 'done']
            requests_before_unscored = len(scenario_results)
            page.reload()
            expect(page.locator('#stat-completed')).to_have_text('4')
            for metric in ('stat-average', 'stat-best', 'stat-change'):
                expect(page.locator('#' + metric)).to_have_text('-')
            expect(page.locator('#trend-chart')).to_contain_text('Belum ada skor')
            expect(page.locator('#trend-chart svg')).to_have_count(0)
            expect(page.locator('#focus-content')).to_contain_text('Belum ada fokus latihan')
            assert len(scenario_results) == requests_before_unscored, scenario_results
            page.goto(base + '/riwayat')
            expect(rows()).to_have_count(4)
            for score in page.locator('#history-list .ws-session-score').all():
                expect(score).to_have_text('-')

            scenario_items = []
            page.goto(base + '/dashboard')
            expect(page.locator('#stat-completed')).to_have_text('0')
            expect(page.locator('#recent-sessions .ws-session-row')).to_have_count(0)
            expect(page.locator('#focus-content')).not_to_contain_text('Komunikasi')
            expect(page.locator('#stat-average')).not_to_contain_text('NaN')
            expect(page.locator('#stat-best')).not_to_contain_text('NaN')
            expect(page.locator('#workspace-error')).not_to_be_visible()
            page.goto(base + '/riwayat')
            expect(rows()).to_have_count(0)
            expect(page.locator('#history-prev')).to_be_disabled()
            expect(page.locator('#history-next')).to_be_disabled()
            expect(page.locator('#workspace-error')).not_to_be_visible()
            assert not errors, errors
            assert not forbidden_requests, forbidden_requests
            assert result_requests and set(result_requests) == {f'{base}/api/sessions/{sessions[14].uuid}/result'}, result_requests
            browser.close()
            print('PASS: isolated workspace metrics/completion chronology, weighted focus, one-score/unmeasured/all-null states, history filters/sort/pagination, keyboard select, empty/error/retry, and 320–1440px layouts. No interview/provider requests.')
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == '__main__':
    main()
