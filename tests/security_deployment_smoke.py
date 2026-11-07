"""Opt-in deployed security checks using one disposable synthetic account.

Run explicitly, for example:
    python tests/security_deployment_smoke.py --base-url https://app.example.com \
        --output artifacts/security-deployment-smoke.json --run

No application configuration, real account credentials, interview sessions, or
AI providers are used. Credentials/cookies remain in memory. The report contains
only fixed check names, statuses, flags, and counts. Account cleanup is attempted
in finally; transport/server failures are reported as cleanup_incomplete.
"""
import argparse
import asyncio
from http.cookies import SimpleCookie
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import tempfile
from urllib.parse import urlsplit
from uuid import UUID

import httpx


class SmokeFailure(Exception):
    """Only fixed, non-sensitive check codes may cross the test boundary."""


def origin(value):
    try:
        parsed = urlsplit(value)
        local = parsed.hostname == 'localhost'
        if parsed.hostname and not local:
            try:
                local = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                pass
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or (parsed.scheme == 'http' and not local)):
            raise ValueError()
        parsed.port  # Reject malformed ports before making a request.
        return f'{parsed.scheme}://{parsed.netloc}'
    except ValueError:
        raise argparse.ArgumentTypeError('Use an HTTPS origin, or HTTP on localhost, without credentials or a path.') from None


def initial_report():
    return {'executed': False, 'ok': False, 'status': 'opt_in_required',
            'synthetic_account_created': False, 'synthetic_account_deleted': False,
            'cleanup_attempted': False, 'cleanup_complete': False,
            'provider_calls': 0, 'interview_sessions_created': 0,
            'requests_sent': 0, 'checks': []}


async def run_smoke(base_url, *, transport=None):
    """transport is only for an isolated ASGI fixture; CLI always uses HTTP(S)."""
    report = initial_report()
    report.update(executed=True, status='running', tls=base_url.startswith('https://'))
    # No env/.env, reusable test login, supplied password, or disk-backed cookies.
    email = f'security-smoke-{secrets.token_hex(20)}@example.com'
    password = 'Synthetic1-' + secrets.token_urlsafe(30)
    wrong_password = 'Wrong2-' + secrets.token_urlsafe(30)
    cv = 'Synthetic security smoke CV. Fictional projects and education only. ' * 8
    credentials = {'email': email, 'password': password}
    registration_attempted = False
    clients = [httpx.AsyncClient(base_url=base_url, follow_redirects=False, trust_env=False,
        timeout=httpx.Timeout(25, connect=10), transport=transport,
        headers={'Origin': base_url, 'Sec-Fetch-Site': 'same-origin',
                 'User-Agent': 'Preptiva-Synthetic-Security-Smoke/1'}) for _ in range(4)]
    first, second, third, old_cookie = clients

    def check(name, passed, **safe_counts):
        report['checks'].append({'name': name, 'passed': bool(passed), **safe_counts})
        if not passed:
            raise SmokeFailure(name)

    async def request(client, method, path, **kwargs):
        report['requests_sent'] += 1
        return await client.request(method, path, **kwargs)

    def status(name, response, expected):
        check(name, response.status_code == expected, status_code=response.status_code,
              expected_status=expected)

    def data(response):
        try:
            value = response.json()
        except (ValueError, UnicodeError):
            raise SmokeFailure('response_json_invalid') from None
        if not isinstance(value, dict):
            raise SmokeFailure('response_object_invalid')
        return value

    async def current(client, name):
        response = await request(client, 'GET', '/api/me')
        status(name, response, 200)
        check(name + '_owns_synthetic_account', data(response).get('email') == email)
        return response

    def private_headers(name, response):
        headers = response.headers
        check(name + '_no_store', 'no-store' in headers.get('cache-control', '').lower())
        check(name + '_nosniff', headers.get('x-content-type-options', '').lower() == 'nosniff')
        check(name + '_frame_protection', headers.get('x-frame-options', '').upper() == 'DENY'
              and "frame-ancestors 'none'" in headers.get('content-security-policy', ''))

    def receipt(name, response, scope, **expected_counts):
        value = data(response).get('receipt')
        check(name + '_object', isinstance(value, dict))
        allowed = {'id', 'scope', 'status', 'created_at', 'completed_at', 'counts',
                   'database_deleted', 'files_pending'}
        counts = value.get('counts')
        encoded = json.dumps(value, ensure_ascii=False)
        safe = (set(value) <= allowed and isinstance(counts, dict)
                and set(counts) <= {'sessions', 'questions', 'answers', 'files', 'accounts', 'saved_cvs'}
                and all(type(v) is int and v >= 0 for v in counts.values())
                and not any(secret in encoded for secret in (email, password, wrong_password, cv)))
        check(name + '_contains_only_receipt_fields', safe)
        try:
            UUID(value.get('id', ''))
        except (ValueError, AttributeError, TypeError):
            raise SmokeFailure(name + '_identifier_invalid') from None
        check(name + '_scope', value.get('scope') == scope)
        check(name + '_complete', value.get('status') == 'complete'
              and value.get('database_deleted') is True and value.get('files_pending') == 0
              and bool(value.get('completed_at')))
        check(name + '_counts', all(counts.get(key) == count for key, count in expected_counts.items()),
              **{key: counts.get(key) for key in expected_counts if type(counts.get(key)) is int})
        # Same JSON representation downloaded by the browser; never persist its
        # identifier, timestamps, account identity, or arbitrary server fields.
        check(name + '_json_downloadable', json.loads(encoded) == value)
        return value['id']

    async def cleanup():
        if not registration_attempted:
            report['cleanup_complete'] = True
            return
        if report['synthetic_account_deleted']:
            return
        report['cleanup_attempted'] = True
        # Keep valid cookies throughout the brute-force test. No logout or login
        # is needed to clean up a still-authenticated synthetic account.
        for candidate in (second, first, old_cookie):
            try:
                response = await request(candidate, 'GET', '/api/me')
                if response.status_code != 200 or data(response).get('email') != email:
                    continue
                deleted = await request(candidate, 'DELETE', '/api/profile',
                    json={'password': password, 'confirmation': 'HAPUS AKUN'})
                result = data(deleted).get('receipt', {}) if deleted.status_code == 200 else {}
                if result.get('scope') == 'account' and result.get('database_deleted') is True:
                    report['synthetic_account_deleted'] = True
                    report['cleanup_complete'] = result.get('status') == 'complete'
                    return
            except Exception:
                # Never print exception/response data: a server may echo secrets.
                continue
        # Only needed if an earlier failure occurred between logout and login,
        # or the registration response was interrupted. Still the generated
        # account only; never try an account from the caller or environment.
        try:
            response = await request(third, 'POST', '/api/auth/login', json=credentials)
            if response.status_code != 200:
                return
            owned = await request(third, 'GET', '/api/me')
            if owned.status_code != 200 or data(owned).get('email') != email:
                return
            deleted = await request(third, 'DELETE', '/api/profile',
                json={'password': password, 'confirmation': 'HAPUS AKUN'})
            result = data(deleted).get('receipt', {}) if deleted.status_code == 200 else {}
            if result.get('scope') == 'account' and result.get('database_deleted') is True:
                report['synthetic_account_deleted'] = True
                report['cleanup_complete'] = result.get('status') == 'complete'
        except Exception:
            pass

    try:
        response = await request(first, 'GET', '/api/me')
        status('unauthenticated_rejected', response, 401)
        registration_attempted = True
        response = await request(first, 'POST', '/api/auth/register', json={**credentials,
            'password_confirm': password, 'name': 'Synthetic Security Check',
            'gender': 'female', 'age': 25, 'agree': True})
        status('synthetic_registration', response, 200)
        report['synthetic_account_created'] = True
        cookies = SimpleCookie()
        for header in response.headers.get_list('set-cookie'):
            cookies.load(header)
        cookie = cookies.get('isim_session')
        check('session_cookie_protected', cookie is not None and bool(cookie['httponly'])
              and cookie['samesite'].lower() == 'lax' and (bool(cookie['secure']) if report['tls'] else True))
        private_headers('private_api', await current(first, 'first_login_active'))

        response = await request(second, 'POST', '/api/auth/login', json=credentials)
        status('second_login_rejected', response, 409)
        await current(first, 'first_login_survives_rejection')
        response = await request(first, 'GET', '/api/auth/session')
        status('session_policy_available', response, 200)
        session = data(response)
        check('one_session_policy', session.get('single_session') is True
              and type(session.get('idle_timeout_seconds')) is int and session['idle_timeout_seconds'] > 0
              and type(session.get('absolute_timeout_seconds')) is int and session['absolute_timeout_seconds'] > 0)

        old_cookie.cookies = httpx.Cookies(first.cookies)
        status('first_logout', await request(first, 'POST', '/api/auth/logout'), 200)
        status('second_login_after_logout', await request(second, 'POST', '/api/auth/login', json=credentials), 200)
        # A separate client replays the revoked cookie; its 401 cannot clear the
        # new client's valid cookie, including on older deployed code.
        status('old_cookie_revoked', await request(old_cookie, 'GET', '/api/me'), 401)
        await current(second, 'second_login_active')

        response = await request(second, 'GET', '/api/privacy/policy')
        status('retention_policy_available', response, 200)
        policy = data(response)
        check('retention_policy_7_90', policy.get('audio_days') == 7 and policy.get('history_days') == 90
              and policy.get('retention_enabled') is True and policy.get('cv_retention') == 'until_deleted')
        response = await request(second, 'GET', '/profile')
        status('private_page_available', response, 200)
        private_headers('private_page', response)
        response = await request(second, 'POST', '/api/auth/logout',
            headers={'Origin': 'https://untrusted.example.invalid', 'Sec-Fetch-Site': 'cross-site'})
        status('cross_origin_mutation_rejected', response, 403)
        await current(second, 'cross_origin_did_not_logout')

        response = await request(second, 'PATCH', '/api/profile', data={'cv_text': cv})
        status('synthetic_cv_saved', response, 200)
        check('synthetic_cv_roundtrip', data(response).get('cv_text') == cv.strip())
        response = await request(second, 'DELETE', '/api/profile/cv',
            json={'password': wrong_password, 'confirmation': 'HAPUS CV'})
        status('wrong_reauthentication_rejected', response, 403)
        response = await request(second, 'GET', '/api/profile')
        status('cv_after_rejected_delete_available', response, 200)
        check('wrong_password_preserves_cv', data(response).get('cv_text') == cv.strip())
        response = await request(second, 'DELETE', '/api/profile/cv',
            json={'password': password, 'confirmation': 'WRONG CONFIRMATION'})
        status('wrong_confirmation_rejected', response, 422)
        response = await request(second, 'DELETE', '/api/profile/cv',
            json={'password': password, 'confirmation': 'HAPUS CV'})
        status('saved_cv_deleted', response, 200)
        cv_receipt = receipt('saved_cv_receipt', response, 'saved_cv', saved_cvs=1, sessions=0)
        check('saved_cv_gone', data(response).get('has_cv') is False and data(response).get('cv_text') == '')

        response = await request(second, 'GET', '/api/sessions')
        status('synthetic_history_available', response, 200)
        check('synthetic_history_empty', data(response).get('items') == [])
        response = await request(second, 'DELETE', '/api/sessions',
            json={'password': password, 'confirmation': 'HAPUS RIWAYAT'})
        status('empty_history_deleted', response, 200)
        history_receipt = receipt('history_receipt', response, 'history', sessions=0, questions=0, answers=0)
        response = await request(second, 'GET', '/api/privacy/receipts')
        status('owned_receipts_available', response, 200)
        items = data(response).get('items')
        check('owned_receipts_include_actions', isinstance(items, list)
              and {cv_receipt, history_receipt} <= {item.get('id') for item in items if isinstance(item, dict)})

        for attempt in range(1, 7):
            response = await request(third, 'POST', '/api/auth/login',
                json={'email': email, 'password': wrong_password})
            status(f'login_attempt_{attempt}', response, 401 if attempt <= 5 else 429)
        retry_after = response.headers.get('retry-after', '')
        check('login_limit_retry_after', retry_after.isdecimal() and int(retry_after) > 0)
        await current(second, 'active_login_survives_attempt_limit')

        old_cookie.cookies = httpx.Cookies(second.cookies)
        response = await request(second, 'DELETE', '/api/profile',
            json={'password': password, 'confirmation': 'HAPUS AKUN'})
        status('synthetic_account_deleted', response, 200)
        # Mark deletion before receipt assertions: if the DB deletion completed,
        # an assertion must not trigger a fresh login or recreate this account.
        result = data(response).get('receipt', {})
        report['synthetic_account_deleted'] = result.get('database_deleted') is True and result.get('scope') == 'account'
        report['cleanup_complete'] = report['synthetic_account_deleted'] and result.get('status') == 'complete'
        receipt('account_receipt', response, 'account', accounts=1, sessions=0)
        report['cleanup_complete'] = True
        status('deleted_account_cookie_revoked', await request(old_cookie, 'GET', '/api/me'), 401)
        status('deleted_account_receipts_private', await request(old_cookie, 'GET', '/api/privacy/receipts'), 401)
        report.update(ok=True, status='passed')
    except SmokeFailure as exc:
        # SmokeFailure is raised only with fixed check names, never server input.
        report.update(status='check_failed', failed_check=exc.args[0])
    except httpx.HTTPError:
        report.update(status='transport_error')
    except Exception:
        report.update(status='unexpected_error')
    finally:
        try:
            await cleanup()
        finally:
            await asyncio.gather(*(client.aclose() for client in clients), return_exceptions=True)
        if registration_attempted and not report['cleanup_complete']:
            report.update(ok=False, status='cleanup_incomplete')
    return report


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.security-smoke-', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', type=origin, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/security-deployment-smoke.json'))
    parser.add_argument('--run', action='store_true', help='Create and delete a new synthetic account on this deployment.')
    args = parser.parse_args()
    # httpx logging must not reveal URL/header/body details supplied by a server.
    logging.getLogger('httpx').disabled = True
    logging.getLogger('httpcore').disabled = True
    report = asyncio.run(run_smoke(args.base_url)) if args.run else initial_report()
    try:
        write_report(args.output, report)
    except OSError:
        print(json.dumps({'ok': False, 'status': 'report_write_failed',
                          'synthetic_account_deleted': report['synthetic_account_deleted']}))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not args.run or report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
