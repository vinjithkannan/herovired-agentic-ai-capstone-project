"""Deterministic quality gate. Heuristics flag risks; they do not certify semantic correctness."""
import re
from collections import defaultdict

NFR_TOPICS = {
    'access': ('access', 'role', 'permission', 'authoriz', 'scope', 'restrict'),
    'audit': ('audit', 'log', 'trace', 'history', 'correction', 'change'),
    'availability': ('availab', 'uptime', 'operating hours', 'service hours'),
    'performance': ('perform', 'response time', 'latency', 'load time', 'throughput'),
}

def topic(text):
    value = (text or '').lower()
    scores = {k: sum(bool(re.search(r'(?<![a-z])'+re.escape(token)+r'(?![a-z])', value)) if token in {'log','role','change','scope','audit'} else token in value for token in tokens) for k, tokens in NFR_TOPICS.items()}
    winner = max(scores, key=scores.get)
    return winner if scores[winner] else None

def issue(key, severity, kind, description, recommendation):
    return {'story_key': key, 'severity': severity, 'issue_type': kind,
            'description': description, 'recommendation': recommendation}

def validate(state):
    requirements = {r['temporary_id']: r for r in state.get('requirements', [])}
    stories = state.get('stories', [])
    criteria = state.get('acceptance_criteria', [])
    dependencies = state.get('dependencies', [])
    issues = []
    keys = {s['story_key'] for s in stories}
    seen = {}
    for story in stories:
        key = story['story_key']
        refs = story.get('source_requirement_ids', [])
        if not refs or any(r not in requirements for r in refs):
            issues.append(issue(key, 'critical', 'traceability', 'Missing/unknown requirement IDs.', 'Link to validated source requirements.'))
        text = ' '.join([story.get('title', ''), story.get('story_text', ''), story.get('description', '')]).lower()
        norm = re.sub(r'[^a-z0-9]+', ' ', story.get('story_text', '').lower()).strip()
        if norm in seen:
            issues.append(issue(key, 'high', 'duplication', f'Duplicate of {seen[norm]}.', 'Merge or rewrite distinct capability.'))
        seen[norm] = key
        for rid in refs:
            req = requirements.get(rid)
            if not req: continue
            source = ' '.join(str(req.get(k, '')) for k in ('statement','title','description'))
            expected = topic(source)
            if rid.upper().startswith('NFR-') and expected:
                actual = topic(text)
                if actual != expected:
                    issues.append(issue(key, 'critical', 'traceability', f'{rid} concerns {expected}, but story concerns {actual or "another topic"}.', 'Regenerate story for the source NFR.'))
            if rid.upper().startswith('NFR-') and not expected:
                issues.append(issue(key, 'high', 'traceability', f'Cannot classify {rid} automatically.', 'Review requirement meaning manually.'))
        own = [c for c in criteria if c.get('story_key') == key]
        if not own or any('REVIEW' in c.get('criterion_key','') for c in own):
            issues.append(issue(key, 'high', 'testability', 'Acceptance criteria missing or awaiting clarification.', 'Product owner must finalize criteria.'))
        for c in own:
            ct = c.get('criterion_text', '').lower()
            if not re.search(r'\bgiven\b.+\bwhen\b.+\bthen\b', ct, re.S):
                issues.append(issue(key, 'high', 'testability', f'{c.get("criterion_key")} is not Given-When-Then.', 'Rewrite testably.'))
            if re.search(r'\bstudent\b.{0,110}\b(associate|modify|correct|edit|delete)\b|\b(associate|modify|correct|edit|delete)\b.{0,110}\bstudent\b', ct):
                issues.append(issue(key, 'critical', 'permission', f'{c.get("criterion_key")} may grant students write privileges.', 'Verify explicit source authorization before approval.'))
            if re.search(r'\b(download|export|offline|approval workflow)\b', ct):
                source = ' '.join(str(requirements[r].get('statement','')) for r in refs if r in requirements).lower()
                if not any(term in source for term in ('download','export','offline','approval workflow')):
                    issues.append(issue(key, 'high', 'scope', f'{c.get("criterion_key")} may introduce unsupported scope.', 'Confirm source evidence or remove the behavior.'))
            for rid in refs:
                req = requirements.get(rid)
                if req and rid.upper().startswith('NFR-'):
                    expected = topic(' '.join(str(req.get(k,'')) for k in ('statement','title')))
                    actual = topic(ct)
                    if expected and actual and expected != actual:
                        issues.append(issue(key, 'critical', 'traceability', f'{c.get("criterion_key")} addresses {actual} rather than {rid} ({expected}).', 'Rewrite criterion to match source.'))
        if story.get('story_points') not in {1,2,3,5,8,13}:
            issues.append(issue(key, 'low', 'estimation', 'Estimate pending.', 'Refine with delivery team.'))
        if key.startswith('US-FALLBACK') or story.get('assumptions'):
            issues.append(issue(key, 'medium', 'assumptions', 'Generated fallback or unresolved assumptions.', 'Review actor, benefit and assumptions.'))
    graph = defaultdict(list)
    for dep in dependencies:
        a,b = dep.get('story_key'),dep.get('depends_on_story_key')
        if a not in keys or b not in keys or a == b:
            issues.append(issue(a or '', 'high', 'dependency', 'Invalid or self-referential dependency.', 'Remove dependency.'))
        elif dep.get('dependency_type') == 'blocks':
            # Canonical meaning: story_key is blocked by depends_on_story_key.
            graph[a].append(b)
            if re.search(r'\bview\b', next((s['title'].lower() for s in stories if s['story_key']==b),'')) and re.search(r'\brecord\b', next((s['title'].lower() for s in stories if s['story_key']==a),'')):
                issues.append(issue(a,'high','dependency','Recording depends on viewing; direction may be reversed.','Verify prerequisite direction.'))
    visited, active = set(), set()
    def visit(node):
        if node in active: return True
        if node in visited: return False
        active.add(node)
        cyc = any(visit(n) for n in graph[node])
        active.remove(node); visited.add(node)
        return cyc
    if any(visit(k) for k in keys):
        issues.append(issue('', 'critical', 'dependency', 'Dependency cycle detected.', 'Remove cyclic prerequisites.'))
    covered = {r for s in stories for r in s.get('source_requirement_ids',[]) if r in requirements}
    missing = sorted(set(requirements)-covered)
    for rid in missing:
        issues.append(issue('', 'critical', 'coverage', f'{rid} has no user story.', 'Generate a traceable story.'))
    critical = sum(i['severity']=='critical' for i in issues)
    high = sum(i['severity']=='high' for i in issues)
    blocked = {i['story_key'] for i in issues if i['severity'] in {'critical','high'}}
    return {'issues': issues, 'summary': f'{len(stories)} stories; {len(covered)}/{len(requirements)} requirements covered; {critical} critical and {high} high findings.',
            'coverage': {'covered':len(covered),'total':len(requirements),'missing_requirement_ids':missing},
            'approval_blocked_story_keys': sorted(blocked),
            'ready_for_approval': not (critical or high),
            'quality_gate_version': '4.1'}
