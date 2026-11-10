"""Gate and idempotent publication orchestrator shared by API and MCP adapters.

Phase 6 FastAPI endpoints authenticate users and enforce roles. Live publishing also requires a
separate server-side publishing key. A remote POST is never automatically retried:
if its outcome cannot be reconciled, the local reservation stays ``uncertain``.
"""

import hmac
import logging
import os

import httpx

from app.services.database import get_connection
from app.services.story_clearance import clearance_report, require_clearance
from integrations.publishing import story_markdown, publish_provider, validate_target

logger = logging.getLogger(__name__)


class PublicationDenied(Exception):
    """Publication is not permitted by configuration or approval rules."""


class PublicationConflict(Exception):
    """A remote publication was already attempted or needs reconciliation."""


def provider_config():
    keys = (
        'github_owner',
        'github_repository',
        'github_token',
        'jira_base_url',
        'jira_project_key',
        'jira_email',
        'jira_api_token',
        'jira_issue_type',
        'jira_issue_type_id',
        'jira_reporter_account_id',
    )
    return {key: os.getenv(key.upper(), '') for key in keys}


def gate(backlog, approvals, source_requirements, story_key, *, live=False, evidence_statuses=None):
    """Dry-run requires quality clearance; live publishing also requires approval."""
    stories = [story for story in backlog.get('stories', []) if story.get('story_key') == story_key]
    if len(stories) != 1:
        raise PublicationDenied('Story not found or duplicate story keys.')

    story = dict(stories[0])
    story['approval_status'] = approvals.get(story_key, 'pending')
    if not source_requirements:
        raise PublicationDenied('Validated source requirements unavailable.')

    clearances, validation = clearance_report(backlog, source_requirements, evidence_statuses)
    if not validation.get('quality_gate_version'):
        raise PublicationDenied('Quality gate unavailable; publication blocked.')

    try:
        require_clearance(clearances, story_key)
    except ValueError as exc:
        raise PublicationDenied(str(exc)) from exc

    if live and story['approval_status'] != 'approved':
        raise PublicationDenied('Live publishing requires manual product-owner approval.')
    return story


def read_snapshot(project_id, backlog_id, story_key, *, live=False):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''SELECT b.result, a.result FROM backlog_runs b
               JOIN analysis_runs a ON a.id = b.analysis_run_id
               WHERE b.id = %s AND b.project_id = %s''',
            (backlog_id, project_id),
        )
        row = cur.fetchone()
        if not row:
            raise PublicationDenied('Backlog does not belong to this project.')

        cur.execute(
            '''SELECT story_key, approval_status
               FROM user_stories WHERE backlog_run_id = %s''',
            (backlog_id,),
        )
        approvals = dict(cur.fetchall())

    backlog, analysis = row
    req_ids = set(backlog.get('source_requirement_ids', []))
    evidence = {
        requirement.get('temporary_id'): requirement.get('evidence_status')
        for requirement in analysis.get('validation', {}).get('requirements', [])
    }
    requirements = [
        requirement
        for requirement in analysis.get('requirements', [])
        if requirement.get('temporary_id') in req_ids
        and evidence.get(requirement.get('temporary_id')) in ('supported', 'partially_supported')
    ]

    story = gate(
        backlog,
        approvals,
        requirements,
        story_key,
        live=live,
        evidence_statuses=evidence,
    )
    return backlog, story


def preview(project_id, backlog_id, story_key, provider):
    backlog, story = read_snapshot(project_id, backlog_id, story_key)
    config = provider_config()
    target = validate_target(provider, config)
    return {
        'mode': 'dry_run',
        'eligible': True,
        'provider': provider,
        'target': target,
        'story_key': story_key,
        'title': story['title'],
        'body': story_markdown(
            story,
            backlog.get('acceptance_criteria', []),
            str(project_id),
            str(backlog_id),
        ),
        'writes_performed': False,
        'approval_status': story['approval_status'],
        'quality_status': 'quality_cleared',
    }


def require_live_key(user_key):
    secret = os.getenv('PHASE5_PUBLISH_KEY', '')
    if os.getenv('PHASE5_ENABLE_LIVE_PUBLISH', 'false').lower() != 'true':
        raise PublicationDenied('Live publication is disabled by PHASE5_ENABLE_LIVE_PUBLISH.')
    if len(secret) < 24 or not user_key or not hmac.compare_digest(secret, user_key):
        raise PublicationDenied('Valid Phase 5 publishing key required.')


def _find_http_status_error(exc):
    """Find a status error retained in an adapter's exception chain."""
    seen = set()
    pending = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, httpx.HTTPStatusError):
            return current
        # A publishing adapter should use ``raise PublishError(...) from exc``.
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return None


def _safe_failure_note(exc):
    """Return a diagnostic note without copying HTTP bodies or credentials."""
    http_error = _find_http_status_error(exc)
    if http_error is not None:
        status = http_error.response.status_code
        # Even a definite rejection is conservatively held for manual review.
        return f'Remote API returned HTTP {status}; reconcile remote issue before retry.'
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return f'Network outcome uncertain ({type(exc).__name__}); reconcile before retry.'
    return f'Publication failed ({type(exc).__name__}); remote outcome requires reconciliation.'


def publish(project_id, backlog_id, story_key, provider, user_key):
    require_live_key(user_key)
    backlog, story = read_snapshot(project_id, backlog_id, story_key, live=True)
    config = provider_config()
    target = validate_target(provider, config)

    # Reserve the exact publication key before the remote POST. The database's
    # unique constraint prevents simultaneous requests from creating duplicates.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''INSERT INTO external_publications
               (project_id, backlog_run_id, story_key, provider, target, state)
               VALUES (%s, %s, %s, %s, %s, 'reserved')
               ON CONFLICT (provider, target, backlog_run_id, story_key) DO NOTHING
               RETURNING id''',
            (project_id, backlog_id, story_key, provider, target),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                '''SELECT state, external_url FROM external_publications
                   WHERE provider = %s AND target = %s
                     AND backlog_run_id = %s AND story_key = %s''',
                (provider, target, backlog_id, story_key),
            )
            old = cur.fetchone()
            raise PublicationConflict(
                f'Already attempted: state={old[0] if old else "unknown"}; '
                f'external_url={old[1] if old else ""}. Reconcile manually before retry.'
            )
        record_id = row[0]

    try:
        published = publish_provider(
            provider,
            config,
            story,
            backlog.get('acceptance_criteria', []),
            str(project_id),
            str(backlog_id),
        )
    except Exception as exc:
        note = _safe_failure_note(exc)
        http_error = _find_http_status_error(exc)
        # Log only identifiers, exception class, and status. Do not dump the
        # exception traceback or HTTP response, which could contain secrets.
        logger.error(
            'Remote publication failed: provider=%s, story=%s, target=%s, '
            'exception_type=%s, http_status=%s',
            provider,
            story_key,
            target,
            type(exc).__name__,
            http_error.response.status_code if http_error is not None else 'unknown',
        )
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                '''UPDATE external_publications
                   SET state = 'uncertain', error_note = %s, updated_at = NOW()
                   WHERE id = %s''',
                (note, record_id),
            )
        raise PublicationConflict(
            'Remote publication failed. Check backend logs and reconcile the '
            'GitHub/Jira issue before retrying.'
        ) from exc

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''UPDATE external_publications
               SET state = 'published', external_id = %s,
                   external_url = %s, updated_at = NOW()
               WHERE id = %s''',
            (published['external_id'], published['external_url'], record_id),
        )

    return {
        'state': 'published',
        'provider': provider,
        'target': target,
        'story_key': story_key,
        'external_id': published['external_id'],
        'external_url': published['external_url'],
    }


def list_records(project_id, backlog_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''SELECT story_key, provider, target, state, external_id,
                      external_url, created_at, error_note
               FROM external_publications
               WHERE project_id = %s AND backlog_run_id = %s
               ORDER BY created_at DESC''',
            (project_id, backlog_id),
        )
        rows = cur.fetchall()
    return [
        {
            'story_key': row[0],
            'provider': row[1],
            'target': row[2],
            'state': row[3],
            'external_id': row[4],
            'external_url': row[5],
            'created_at': row[6].isoformat(),
            'error_note': row[7],
        }
        for row in rows
    ]
