"""Read-only ReqFlow integration smoke test (except creating a login session).

Run from the project root; set REQFLOW_TEST_USER/REQFLOW_TEST_PASSWORD
in your local shell. Does not write delivery artifacts or publish anything.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def check(condition, endpoint, message):
    if not condition:
        raise ValueError(f'{endpoint}: {message}')


def request(base, path, token=None, payload=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(base.rstrip('/') + path, data=data, headers=headers,
                                 method='POST' if payload is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print a token, password or complete response body.
        raise ValueError(f'{path}: HTTP {exc.code} {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise ValueError(f'{path}: connection failed: {exc.reason}') from exc


def validate_health(status, health):
    """Accept ReqFlow's real /health contract; never require root / fields."""
    check(status == 200, '/health', f'expected HTTP 200, received {status}')
    check(isinstance(health, dict), '/health', 'expected a JSON object')
    check(health.get('status') == 'ok', '/health',
          f'expected status=ok, received status={health.get("status")!r}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://localhost:8000')
    p.add_argument('--project-id')
    p.add_argument('--backlog-id')
    args = p.parse_args()
    checks = []
    try:
        status, health = request(args.base, '/health')
        validate_health(status, health)
        checks.append('GET /health: HTTP 200 status=ok')

        username = os.environ.get('REQFLOW_TEST_USER')
        password = os.environ.get('REQFLOW_TEST_PASSWORD')
        if not username or not password:
            print(json.dumps({'status':'partial','passed_checks': checks,
                              'skipped':['Authenticated checks: set REQFLOW_TEST_USER and REQFLOW_TEST_PASSWORD']}, indent=2))
            return

        status, login = request(args.base, '/api/v1/auth/login',
                                payload={'username': username, 'password': password})
        check(status == 200 and isinstance(login, dict) and bool(login.get('access_token')),
              '/api/v1/auth/login', 'expected HTTP 200 with an access_token')
        token = login['access_token']
        status, profile = request(args.base, '/api/v1/auth/me', token=token)
        check(status == 200 and isinstance(profile, dict) and bool(profile.get('role')),
              '/api/v1/auth/me', 'expected role in authenticated profile')
        checks.append('Authentication and bearer session valid')

        status, projects = request(args.base, '/api/v1/projects', token=token)
        check(status == 200 and isinstance(projects, list),
              '/api/v1/projects', 'expected HTTP 200 JSON list')
        checks.append('Projects list authorized')

        if args.project_id and args.backlog_id:
            root = f'/api/v1/projects/{args.project_id}/backlogs/{args.backlog_id}'
            status, backlog = request(args.base, root, token=token)
            check(status == 200 and isinstance(backlog, dict) and backlog.get('backlog_id') == args.backlog_id,
                  root, 'expected JSON backlog with requested backlog_id')
            checks.append('Backlog loaded from database')

            status, delivery = request(args.base, root + '/delivery', token=token)
            check(status == 200 and isinstance(delivery, dict) and isinstance(delivery.get('artifacts'), dict),
                  root + '/delivery', 'expected JSON delivery artifacts mapping')
            checks.append('Phase 7 delivery endpoint available')

            eligible = [s.get('story_key') for s in backlog.get('stories', [])
                        if s.get('approval_status') == 'approved'
                        and backlog.get('story_clearances', {}).get(s.get('story_key'), {}).get('status') == 'quality_cleared']
            checks.append(f'{len(eligible)} stories both quality-cleared and Product Owner-approved')
            if eligible:
                checks.append('Eligible story keys: ' + ', '.join(eligible))
            else:
                checks.append('No eligible stories; generating a design should remain gated')
            checks.append('Delivery statuses: ' + ', '.join(
                f'{k}={v.get("status")}' for k, v in delivery['artifacts'].items()))

        print(json.dumps({'status': 'passed', 'passed_checks': checks}, indent=2))
    except (ValueError, KeyError, TypeError, TimeoutError, OSError) as exc:
        print(json.dumps({'status': 'failed', 'passed_checks': checks,
                          'error': str(exc) or f'{type(exc).__name__} (no details)'}))
        sys.exit(1)


if __name__ == '__main__':
    main()
