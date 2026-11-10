"""Phase 4.2: grounded, versioned targeted repair.

Deterministic rules are the safety fallback; Ollama is only allowed to propose
improvements that survive local validation. Nothing from the source run is changed.
"""
import copy
import json
import re
from collections import defaultdict
from agents.story_generation.quality import validate, topic
from agents.requirements_analysis.ollama_client import chat_json, OllamaError

BLOCKING = {'critical', 'high'}

def _issues_for(validation):
    return {i.get('story_key') for i in validation.get('issues', [])
            if i.get('severity') in BLOCKING and i.get('story_key') and i.get('issue_type') != 'dependency'}

def _source(req):
    return str(req.get('statement') or req.get('title') or '').strip()

def _templates(req):
    """Conservative source-derived suggestions, never unstated numerical targets."""
    rid = req['temporary_id']; source = _source(req)
    kind = topic(source)
    if rid.upper().startswith('NFR-') and kind == 'access':
        return ('Enforce role and scope restrictions',
                'As an authorized user, I want role and scope restrictions enforced, so that access is limited to permitted records.',
                'Given a user requests attendance data, When access is evaluated, Then the application enforces the documented role and scope restrictions.', 'security', [])
    if rid.upper().startswith('NFR-') and kind == 'audit':
        return ('Audit attendance creation and corrections',
                'As an authorized reviewer, I want an audit trail for attendance creation and corrections, so that changes can be traced.',
                'Given attendance is created or corrected, When the action is committed, Then the application records an audit trail for that action.', 'audit', [])
    if rid.upper().startswith('NFR-') and kind == 'availability':
        return ('Meet agreed service availability requirements',
                'As a university user, I want the attendance service available during university operating hours, so that I can perform attendance tasks.',
                'Given university operating hours and an availability target are confirmed, When service availability is measured, Then the agreed availability criterion is evaluated.', 'functional', ['Availability target and measurement method require product-owner confirmation.'])
    if rid.upper().startswith('NFR-') and kind == 'performance':
        return ('Meet agreed attendance response-time targets',
                'As a university user, I want attendance lists and reports to meet agreed response-time targets, so that I can complete tasks efficiently.',
                'Given an approved response-time target and workload are defined, When attendance lists or reports are requested, Then measured response times meet that target.', 'performance', ['Response-time threshold and test load require product-owner confirmation.'])
    # FR: source-aligned conservative fallback; do not create any new actor privileges.
    src_low = source.lower()
    if 'correct' in src_low and 'audit' in src_low:
        return ('Correct attendance with an audit trail',
                'As an authorized user, I want to correct attendance with an audit trail, so that permitted corrections remain traceable.',
                'Given an authorized attendance correction, When the change is saved, Then the correction is recorded with an audit trail.', 'audit', ['Authorized correction roles must be confirmed.'])
    if 'course' in src_low and 'semester' in src_low and ('academic year' in src_low or 'year' in src_low):
        return ('Associate attendance with academic context',
                'As an authorized faculty member, I want attendance linked to its course, semester and academic year, so that records have correct academic context.',
                'Given an authorized attendance record, When it is saved, Then the record is linked to its course, semester and academic year.', 'functional', [])
    if 'report' in src_low:
        return ('Generate attendance reports',
                'As a department administrator, I want attendance reports filtered by the documented criteria, so that I can analyze attendance data.',
                'Given an authorized administrator selects documented report filters, When a report is requested, Then the resulting report uses those filters.', 'functional', [])
    if 'student' in src_low and ('view' in src_low or 'percentage' in src_low):
        return ('View own attendance records',
                'As a student, I want to view my attendance records and percentage, so that I can monitor my attendance.',
                'Given a student is authenticated, When they view attendance, Then only their own attendance records and percentage are displayed.', 'functional', [])
    if 'faculty' in src_low and ('record' in src_low or 'attendance' in src_low):
        return ('Record attendance for assigned courses',
                'As a faculty member, I want to record attendance for my assigned courses, so that attendance is maintained.',
                'Given faculty access to an assigned course, When attendance is submitted, Then attendance is recorded for that course.', 'functional', [])
    return (f'Review requirement {rid}',
            f'As a product stakeholder, I want {rid} implemented as documented, so that the requirement is satisfied.',
            'Given the source requirement is reviewed, When expected behavior is agreed, Then testable acceptance criteria are documented.', 'functional',
            [f'Manual refinement required: {source}'])

def _fallback_story(req, original, epic_key):
    title, story_text, criterion, test_type, assumptions = _templates(req)
    row = dict(original or {})
    row.update(title=title, story_text=story_text, description=_source(req),
               epic_key=epic_key, source_requirement_ids=[req['temporary_id']],
               assumptions=assumptions,
               priority_recommendation='should',
               priority_rationale='AI recommendation; product-owner prioritization required.',
               story_points=None, estimate_rationale='Delivery team to estimate after review.')
    return row, criterion, test_type

def _model_suggestion(req, row):
    """Allow only one requirement and one story per prompt. Invalid output is ignored."""
    prompt = ('You are correcting one Agile user story. Only use the source requirement. '
              'Never invent permissions, downloads, thresholds, workflows or policies. '
              'For missing NFR thresholds state that acceptance needs product-owner review. '
              'Return STRICT JSON with keys title, story_text, criterion_text, test_type, assumptions. '
              'criterion_text must use Given, When, Then. '
              'Keep the same requirement ID. Do not return epics or dependencies.\n'
              +json.dumps({'requirement_id': req['temporary_id'], 'requirement_text': _source(req),
                           'safe_draft': {'title':row['title'],'story_text':row['story_text']}},ensure_ascii=False))
    try:
        p=chat_json(prompt)
    except (OllamaError, ValueError, TypeError):
        return None
    if not isinstance(p,dict): return None
    story_text=p.get('story_text'); criterion=p.get('criterion_text')
    if not isinstance(story_text,str) or not isinstance(criterion,str): return None
    if not re.match(r'(?is)^as an? .+?,\s*i want .+?,\s*so that .+',story_text.strip()): return None
    if not re.search(r'(?is)\bgiven\b.+\bwhen\b.+\bthen\b', criterion): return None
    # No student writes or unsupported scope, including access to unrelated records.
    if re.search(r'(?is)\bstudent\b.{0,120}\b(associate|modify|correct|edit|delete)\b|\b(associate|modify|correct|edit|delete)\b.{0,120}\bstudent\b',criterion): return None
    if re.search(r'(?i)\b(download|export|offline)\b',criterion+' '+story_text) and not re.search(r'(?i)\b(download|export|offline)\b',_source(req)): return None
    return p

def _block_count(v):
    return sum(x['severity'] in BLOCKING for x in v['issues'])

def repair_backlog(original, requirements, use_ollama=True):
    """Return (new result, audit metadata). Never mutates arguments."""
    state=copy.deepcopy(original)
    reqs={r['temporary_id']:r for r in requirements}
    state['requirements']=list(reqs.values())
    source_validation=validate(state)
    blocked=_issues_for(source_validation)
    # Coverage gaps also become new review stories, not silent omissions.
    missing=source_validation['coverage']['missing_requirement_ids']
    old_stories={s['story_key']:s for s in state.get('stories',[])}
    story_keys=set(old_stories)
    epics=state.get('epics',[])
    if not epics:
        epics=[{'epic_key':'EPIC-REPAIR','title':'Requirements requiring review','description':'Unassigned requirements','business_value':'','source_requirement_ids':list(reqs)}]
        state['epics']=epics
    epic_for={rid:e['epic_key'] for e in epics for rid in e.get('source_requirement_ids',[]) if rid in reqs}
    fallback_epic=epics[0]['epic_key']
    for rid in missing:
        if rid not in epic_for:
            epics[0].setdefault('source_requirement_ids',[]).append(rid)
            epic_for[rid]=fallback_epic
        key=f'US-REPAIR-{rid}'
        if key not in story_keys:
            old_stories[key]={'story_key':key,'source_requirement_ids':[rid],'epic_key':epic_for[rid]}
            story_keys.add(key);blocked.add(key)
    changed=[]; kept=[]; notes=[]
    criteria=list(state.get('acceptance_criteria',[]))
    for key,old in old_stories.items():
        if key not in blocked:
            kept.append(key); continue
        refs=[rid for rid in old.get('source_requirement_ids',[]) if rid in reqs]
        if not refs:
            # Untraceable old story remains for explicit review rather than assuming intent.
            kept.append(key);notes.append(f'{key}: unknown source ID; manual review needed')
            continue
        rid=refs[0];req=reqs[rid]
        new, criterion, test_type=_fallback_story(req,old,epic_for.get(rid,old.get('epic_key') or fallback_epic))
        old_c=[c for c in criteria if c.get('story_key')==key]
        criterion_key=old_c[0]['criterion_key'] if old_c else f'AC-REPAIR-{key}'
        draft_criteria=[c for c in criteria if c.get('story_key')!=key]
        draft_criteria.append({'story_key':key,'criterion_key':criterion_key,'criterion_text':criterion,'test_type':test_type})
        draft_state={**state,'stories':[new], 'acceptance_criteria':draft_criteria[-1:], 'requirements':[req], 'dependencies':[]}
        # Source-aligned fallback always wins over unsafe LLM text. Suggestions only if
        # they reduce blocking findings and preserve requirement type/topic.
        if use_ollama:
            proposed=_model_suggestion(req,new)
            if proposed:
                candidate=dict(new)
                candidate['title']=str(proposed.get('title') or new['title'])[:255]
                candidate['story_text']=proposed['story_text'].strip()
                candidate['assumptions']=list(new['assumptions']) + [str(x) for x in proposed.get('assumptions',[]) if isinstance(x,str)][:3] if isinstance(proposed.get('assumptions',[]),list) else new['assumptions']
                candidate_criterion=dict(draft_criteria[-1],criterion_text=proposed['criterion_text'].strip(),test_type=proposed.get('test_type') if proposed.get('test_type') in {'functional','security','performance','audit'} else test_type)
                cv=validate({**draft_state,'stories':[candidate],'acceptance_criteria':[candidate_criterion]})
                fv=validate(draft_state)
                # Semantic topical check: compare NFR source directly to model output.
                expected=topic(_source(req)) if rid.upper().startswith('NFR-') else None
                actual=topic(candidate['title']+' '+candidate['story_text'])
                if _block_count(cv)<_block_count(fv) or (_block_count(cv)==_block_count(fv)==0 and (not expected or expected==actual)):
                    new=candidate;draft_criteria[-1]=candidate_criterion
        old_stories[key]=new
        criteria=draft_criteria
        changed.append(key)
    # Remove only dependencies with invalid/reversed direction or cycles; do not
    # fabricate new dependencies. An unchanged, valid dependency remains intact.
    dependencies=[]
    for dep in state.get('dependencies',[]):
        a=dep.get('story_key');b=dep.get('depends_on_story_key')
        if a not in old_stories or b not in old_stories or a==b: continue
        titles={k:str(x.get('title','')).lower() for k,x in old_stories.items()}
        if dep.get('dependency_type')=='blocks' and 'record' in titles[a] and 'view' in titles[b]:
            notes.append(f'{a} -> {b}: removed reversed prerequisite');continue
        dependencies.append(dep)
    # Eliminate cyclic dependencies, preserving other edges.
    cleaned=[];links=defaultdict(set)
    def reaches(node,target,seen=None):
        if node==target: return True
        seen=seen or set()
        if node in seen:return False
        seen.add(node)
        return any(reaches(n,target,seen) for n in links[node])
    for d in dependencies:
        a,b=d['story_key'],d['depends_on_story_key']
        if d.get('dependency_type')=='blocks':
            if reaches(b,a):
                notes.append(f'{a} -> {b}: removed cyclic prerequisite');continue
            links[a].add(b)
        cleaned.append(d)
    state['stories']=list(old_stories.values())
    state['acceptance_criteria']=criteria
    state['dependencies']=cleaned
    state['validation']=validate(state)
    # Count high/critical findings for an objective before/after assessment.
    audit={'changed_story_keys':changed,'preserved_story_keys':kept,'notes':notes,
           'before_blocking_findings':_block_count(source_validation),
           'after_blocking_findings':_block_count(state['validation']),
           'source_quality_gate_version':source_validation.get('quality_gate_version')}
    state.pop('requirements',None)
    return state,audit
