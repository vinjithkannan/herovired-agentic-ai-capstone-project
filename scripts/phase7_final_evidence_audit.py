#!/usr/bin/env python3
"""Read-only runtime evidence audit for ReqFlow Phase 7.

Reads authenticated FastAPI endpoints; never changes delivery approvals,
posts issues, or prints credentials. Writes only locally generated summaries.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def get_json(base, path, token=None, payload=None):
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
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{path} returned HTTP {exc.code}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'{path} unreachable: {exc.reason}') from exc


def analyze(backlog, delivery):
    stories = backlog.get('stories', [])
    clearance = backlog.get('story_clearances') or {}
    eligible = sorted(s.get('story_key') for s in stories
                      if s.get('story_key') and s.get('approval_status') == 'approved'
                      and (clearance.get(s.get('story_key')) or {}).get('status') == 'quality_cleared')
    artifacts = delivery.get('artifacts') or {}
    design_record = artifacts.get('design') or {}
    plan_record = artifacts.get('plan') or {}
    design = design_record.get('artifact') or {}
    plan = plan_record.get('artifact') or {}
    tasks = plan.get('tasks') or []
    task_keys = [t.get('task_key') for t in tasks]
    task_set = set(task_keys)
    deps = [(t.get('task_key'), d) for t in tasks for d in (t.get('depends_on') or [])]
    design_scope = (design.get('scope') or {}).get('story_keys') or []
    plan_scope = plan.get('story_keys') or []
    api_proposals = design.get('api_proposals') or []
    entities = design.get('data_model_proposals') or []
    architecture = design.get('architecture') or {}
    components = design.get('components') or []
    checks = {
        'design_approved': design_record.get('status') == 'approved',
        'plan_approved': plan_record.get('status') == 'approved',
        'eligible_story_scope_matches_design': bool(eligible) and sorted(design_scope) == eligible,
        'eligible_story_scope_matches_plan': bool(eligible) and sorted(plan_scope) == eligible,
        'architecture_flow_present': bool(architecture.get('flow')),
        'components_present': bool(components),
        'proposed_apis_present': bool(api_proposals),
        'proposed_entities_present': bool(entities),
        'assumptions_and_open_decisions_present': bool(design.get('assumptions')) and bool(design.get('open_decisions')),
        'tasks_present': bool(tasks),
        'unique_task_identifiers': bool(tasks) and len(task_keys) == len(task_set) and None not in task_set,
        'task_dependencies_resolve': all(d in task_set for _, d in deps),
        'task_estimation_metadata_present': bool(tasks) and all('estimate_status' in t and 'estimate_story_points' in t for t in tasks),
        'tasks_only_reference_eligible_stories': bool(tasks) and all(t.get('story_key') in eligible for t in tasks),
    }
    summary = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'audit': 'reqflow-phase7-final-runtime-evidence-v1',
        'source': 'authenticated local API; no changes to PostgreSQL or external services',
        'eligible_story_keys': eligible,
        'story_count': len(stories),
        'quality_cleared_count': sum(1 for s in stories if (clearance.get(s.get('story_key')) or {}).get('status') == 'quality_cleared'),
        'design': {
            'approval_status': design_record.get('status'),
            'scope_story_keys': design_scope,
            'architecture_style': architecture.get('style'),
            'architecture_flow': architecture.get('flow', []),
            'component_names': [c.get('name') for c in components],
            'api_proposal_count': len(api_proposals),
            'api_operations': [p.get('operation') for p in api_proposals],
            'proposed_entities': [e.get('entity') for e in entities],
            'assumptions_count': len(design.get('assumptions') or []),
            'open_decisions_count': len(design.get('open_decisions') or []),
        },
        'plan': {
            'approval_status': plan_record.get('status'),
            'scope_story_keys': plan_scope,
            'task_count': len(tasks),
            'phase_counts': {p: sum(1 for t in tasks if t.get('phase') == p) for p in sorted(set(t.get('phase') for t in tasks if t.get('phase')))},
            'dependency_edge_count': len(deps),
            'tasks_missing_numeric_estimate': sum(1 for t in tasks if t.get('estimate_story_points') is None),
            'tasks_requiring_team_estimation': sum(1 for t in tasks if t.get('estimate_status') == 'team_estimation_required'),
        },
        'checks': checks,
        'passed': all(checks.values()),
        'limitations': [
            'Approval status and schema-level completeness do not establish semantic design correctness.',
            'API paths, entities and estimates are proposed artifacts requiring technical/team review.',
            'This read-only audit does not exercise state-changing approval endpoints or live publishing.',
        ],
    }
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://localhost:8000')
    p.add_argument('--project-id', required=True)
    p.add_argument('--backlog-id', required=True)
    p.add_argument('--output', default='evidence/phase7_delivery_audit.json')
    a = p.parse_args(argv)
    user, password = os.getenv('REQFLOW_TEST_USER'), os.getenv('REQFLOW_TEST_PASSWORD')
    if not user or not password:
        p.error('Set REQFLOW_TEST_USER and REQFLOW_TEST_PASSWORD; do not pass secrets on the command line.')
    try:
        login = get_json(a.base, '/api/v1/auth/login', payload={'username':user,'password':password})
        token = login.get('access_token')
        if not token: raise RuntimeError('Login response has no access_token')
        path = f'/api/v1/projects/{a.project_id}/backlogs/{a.backlog_id}'
        backlog = get_json(a.base, path, token=token)
        delivery = get_json(a.base, path+'/delivery', token=token)
        report = analyze(backlog, delivery)
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed':report['passed'],'evidence_file':str(out),
                          'eligible_story_keys':report['eligible_story_keys'],
                          'design':report['design'], 'plan':report['plan'], 'checks':report['checks']}, indent=2))
        return 0 if report['passed'] else 1
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'passed':False,'error':str(exc)}))
        return 1

if __name__ == '__main__':
    sys.exit(main())
