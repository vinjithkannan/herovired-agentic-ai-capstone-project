"""Phase 7 scope completion: source-grounded specialized delivery agents.

This workflow consumes persisted Phase 3 / 4 artifacts. It never silently
re-generates or approves requirements/stories and never publishes remotely.
"""
from __future__ import annotations
from typing import Any


def _log(state: dict, node: str, **extra) -> list[dict]:
    return [*state.get('execution_log', []), {'node': node, 'status': 'completed', **extra}]


def intake_node(state: dict) -> dict:
    if not state.get('project_id') or not state.get('backlog_id'):
        raise ValueError('Persisted project_id and backlog_id are required')
    return {'execution_log': _log(state, 'intake')}


def research_agent(state: dict) -> dict:
    """Replay already validated Phase 3 research, never invent new requirements."""
    requirements = state.get('requirements', [])
    allowed = set(state.get('source_requirement_ids', []))
    evidence = state.get('evidence', {})
    sourced = [r for r in requirements if r.get('temporary_id') in allowed and
               evidence.get(r.get('temporary_id')) in ('supported', 'partially_supported')]
    if not sourced:
        raise ValueError('No source-backed Phase 3 requirements found for this backlog')
    return {'research_findings': [{'id': r['temporary_id'],
                                  'statement': r.get('statement', ''),
                                  'evidence_status': evidence[r['temporary_id']]}
                                 for r in sourced],
            'execution_log': _log(state, 'research_agent', source_count=len(sourced))}


def story_agent(state: dict) -> dict:
    """Preserve Phase 4 story snapshot; select independently revalidated approvals."""
    clearances = state.get('story_clearances', {})
    allowed = {r['id'] for r in state['research_findings']}
    eligible = [s for s in state.get('stories', [])
                if s.get('approval_status') == 'approved'
                and clearances.get(s.get('story_key'), {}).get('status') == 'quality_cleared'
                and set(s.get('source_requirement_ids', [])).issubset(allowed)
                and s.get('source_requirement_ids')]
    if not eligible:
        raise ValueError('No source-backed, quality-cleared, PO-approved stories available')
    return {'eligible_stories': eligible,
            'execution_log': _log(state, 'story_agent', eligible_count=len(eligible))}


def design_agent(state: dict) -> dict:
    """Produce a traceable *proposed* solution design; no invented API contracts."""
    eligible = state['eligible_stories']
    refs = sorted({r for s in eligible for r in s.get('source_requirement_ids', [])})
    criteria = [c for c in state.get('acceptance_criteria', [])
                if c.get('story_key') in {s['story_key'] for s in eligible}]
    domain_text = ' '.join((s.get('title','') + ' ' + s.get('story_text','')) for s in eligible).lower()
    attendance_domain = 'attendance' in domain_text
    proposed_entities = ([
        {'entity':'AttendanceRecord', 'fields':['id','student_id','session_id','status','recorded_by','recorded_at'], 'status':'proposed — confirm status vocabulary and attendance rules'},
        {'entity':'AttendanceCorrection', 'fields':['id','attendance_record_id','previous_status','new_status','changed_by','changed_at','reason'], 'status':'proposed — confirm audit/retention rules'},
        {'entity':'AccessGrant', 'fields':['id','principal_id','role','scope_id'], 'status':'proposed — review approved role matrix'},
    ] if attendance_domain else [
        {'entity':'DomainRecord', 'fields':['id','created_at','updated_at'], 'status':'illustrative — refine from approved requirements'},
        {'entity':'AuditEvent', 'fields':['id','actor_id','action','event_time'], 'status':'proposed — confirm compliance and retention'},
    ])
    design = {
        'status': 'draft_requires_human_review',
        'title': 'Solution Design — ' + state.get('project_title', 'ReqFlow project'),
        'scope': {'story_keys': [s['story_key'] for s in eligible], 'requirement_ids': refs},
        'architecture': {
            'style': 'Proposed modular web-application architecture; validate with technical lead',
            'flow': ['Client/UI', 'Authenticated API', 'Application services', 'Persistent database',
                     'Audit/observability'],
            'alternatives': ['Deploy as modular monolith first',
                             'Extract microservices only after scaling/ownership justification'],
        },
        'components': [
            {'name': 'UI', 'responsibility': 'Role-aware user workflows and validation'},
            {'name': 'API', 'responsibility': 'Authentication, authorization, validation and contracts'},
            {'name': 'Domain service', 'responsibility': 'Implement approved story business rules'},
            {'name': 'Persistence', 'responsibility': 'Store records and change/audit history'},
        ],
        'api_proposals': [
            {'story_key': s['story_key'],
             'operation': ('PATCH /api/v1/attendance/{record_id}' if 'correct' in (s.get('title','')+' '+s.get('story_text','')).lower() else
                           'GET /api/v1/attendance/reports' if 'report' in (s.get('title','')+' '+s.get('story_text','')).lower() else
                           'GET /api/v1/attendance' if attendance_domain else 'TBD /api/v1/domain-resource'),
             'status': 'proposed endpoint, not an implemented contract',
             'purpose': s.get('title', ''), 'source_requirement_ids': s['source_requirement_ids']}
            for s in eligible
        ],
        'data_model_proposals': proposed_entities,
        'traceable_acceptance_criteria': criteria,
        'assumptions': [
            'Technology, data entities and endpoint paths are proposals, not source requirements.',
            'Access roles, persistence schema, security and NFR thresholds require technical/PO sign-off.',
            'Only explicitly approved and quality-cleared source stories are included.',
        ],
        'open_decisions': ['Agree API contract and entity relationships',
                           'Confirm hosting, security controls, performance and availability targets',
                           'Review architecture against actual business context'],
    }
    return {'solution_design': design,
            'execution_log': _log(state, 'design_agent', story_count=len(eligible))}


def design_gate(state: dict) -> dict:
    approved = state.get('design_approval') == 'approved'
    return {'workflow_status': 'design_approved' if approved else 'awaiting_design_approval',
            'execution_log': _log(state, 'design_gate', approved=approved)}


def planning_agent(state: dict) -> dict:
    """Create developer tasks, conservative story-point ranges and dependencies.

    The estimates are planning proposals; no claimed historical velocity.
    """
    stories = state['eligible_stories']
    keys = {s['story_key'] for s in stories}
    task_ids = {}
    tasks = []
    for i, story in enumerate(stories, 1):
        key = story['story_key']
        base = f'TASK-{i:03d}'
        task_ids[key] = base
        points = story.get('story_points')
        points = points if type(points) is int and points in (1, 2, 3, 5, 8, 13) else None
        stages = [
            ('design', 'Confirm technical design and interfaces', 1),
            ('implementation', 'Implement the approved user story', points),
            ('testing', 'Add acceptance, authorization and regression tests', 2),
        ]
        for idx, (phase, label, estimate) in enumerate(stages):
            task_key = f'{base}-{idx+1}'
            prev = [f'{base}-{idx}'] if idx else []
            tasks.append({'task_key': task_key, 'story_key': key,
                          'title': f'{label}: {story.get("title", key)}',
                          'phase': phase,
                          'source_requirement_ids': story['source_requirement_ids'],
                          'depends_on': prev,
                          'priority': story.get('priority_recommendation', 'should'),
                          'estimate_story_points': estimate,
                          'estimate_status': 'proposed' if estimate is not None else 'team_estimation_required',
                          'acceptance_criteria_keys': [c.get('criterion_key') for c in state.get('acceptance_criteria', [])
                                                       if c.get('story_key') == key] if phase == 'testing' else [],
                          'assumptions': ['Confirm task sizing and dependencies in team refinement']})
    # Link each implementation task to other approved story's testing task.
    for dep in state.get('dependencies', []):
        story_key = dep.get('story_key')
        predecessor = dep.get('depends_on_story_key') or dep.get('depends_on')
        if story_key in task_ids and predecessor in keys and predecessor != story_key:
            target = next((t for t in tasks if t['task_key'] == task_ids[story_key]+'-2'), None)
            if target:
                prerequisite = task_ids[predecessor]+'-3'
                if prerequisite not in target['depends_on']:
                    target['depends_on'].append(prerequisite)
    return {'implementation_tasks': tasks,
            'execution_log': _log(state, 'planning_agent', task_count=len(tasks))}


def planning_gate(state: dict) -> dict:
    approved = state.get('plan_approval') == 'approved'
    return {'workflow_status': 'ready_for_delivery' if approved else 'awaiting_plan_approval',
            'execution_log': _log(state, 'planning_gate', approved=approved)}
