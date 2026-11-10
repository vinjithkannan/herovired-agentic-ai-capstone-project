"""Phase 5.1: derive story-level clearance from source-backed validation.

Clearance is NOT product owner approval. An unresolved assumption remains review_required.
Recompute at read/approve/publish time; never trust a stored client status.
"""
from agents.story_generation.quality import validate as validate_quality

BLOCKING = frozenset(('critical', 'high'))
REVIEW_KINDS = frozenset(('assumptions',))


def clearance_report(backlog, requirements, evidence_statuses=None):
    evidence_statuses = evidence_statuses or {}
    validation = validate_quality({**backlog, 'requirements': requirements})
    source = {r.get('temporary_id') for r in requirements}
    issues = validation.get('issues', [])
    results = {}
    for story in backlog.get('stories', []):
        key = story.get('story_key', '')
        linked = story.get('source_requirement_ids') or []
        own = [i for i in issues if i.get('story_key') in (key, '')]
        reasons = []
        if not linked or any(r not in source for r in linked):
            reasons.append('Unknown or missing validated requirement reference')
        if evidence_statuses and any(evidence_statuses.get(r) not in ('supported', 'partially_supported') for r in linked):
            reasons.append('Requirement lacks validated supporting evidence')
        if not any(c.get('story_key') == key and c.get('criterion_text', '').strip() for c in backlog.get('acceptance_criteria', [])):
            reasons.append('Acceptance criteria missing')
        blocking = [i for i in own if i.get('severity') in BLOCKING]
        review = [i for i in own if i.get('issue_type') in REVIEW_KINDS or i.get('severity') == 'medium']
        if any(not i.get('story_key') for i in issues if i.get('severity') in BLOCKING):
            reasons.append('Backlog-level blocking quality finding')
        if blocking or reasons:
            status = 'blocked'
        elif review:
            status = 'review_required'
        else:
            status = 'quality_cleared'
        results[key] = {'status': status, 'reasons': reasons + [i.get('description', '') for i in blocking + review],
                        'blocking_findings': len(blocking), 'review_findings': len(review)}
    return results, validation


def require_clearance(clearances, story_key):
    result = clearances.get(story_key)
    if not result or result['status'] != 'quality_cleared':
        raise ValueError(f'Story {story_key} is not quality-cleared: {result["status"] if result else "not found"}.')
    return result
