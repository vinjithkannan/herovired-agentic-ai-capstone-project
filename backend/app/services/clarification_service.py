"""Immutable, PO-approved story corrections. Does not approve stories or write to Jira/GitHub."""
from __future__ import annotations
from copy import deepcopy
import re
from agents.story_generation.quality import validate
from app.services.story_clearance import clearance_report

GWT = re.compile(r'\bgiven\b.+\bwhen\b.+\bthen\b', re.I | re.S)


def validate_proposal(proposal: dict) -> dict:
    """Require explicit story and testable criteria; do not accept a checkbox-only waiver."""
    if not isinstance(proposal, dict):
        raise ValueError('Proposal must be an object')
    required = ('title', 'story_text', 'rationale', 'acceptance_criteria')
    if any(not proposal.get(k) for k in required):
        raise ValueError('Title, story text, rationale, and criteria are required')
    if any(not isinstance(proposal[k], str) or len(proposal[k].strip()) < 15 or len(proposal[k]) > 5000 for k in required[:3]):
        raise ValueError('Story text/title/rationale must contain 15–5000 characters')
    criteria = proposal['acceptance_criteria']
    if not isinstance(criteria,list) or not 1 <= len(criteria) <= 12:
        raise ValueError('Provide between 1 and 12 acceptance criteria')
    clean=[]
    for criterion in criteria:
        if not isinstance(criterion,dict):
            raise ValueError('Criterion must contain test_type and criterion_text')
        text=criterion.get('criterion_text','')
        typ=criterion.get('test_type','functional')
        if not isinstance(text,str) or not GWT.search(text) or len(text.strip()) < 45 or len(text)>4000:
            raise ValueError('Each acceptance criterion must be a substantive Given/When/Then statement')
        if typ not in ('functional','security','audit','availability','performance','non_functional'):
            raise ValueError('Invalid test type')
        # Refuse unresolved conditional promises, not merely missing syntax.
        if re.search(r'\b(to be (defined|agreed|confirmed)|awaiting clarification|target unspecified|TBD)\b',text,re.I):
            raise ValueError('Acceptance criterion is unresolved')
        clean.append({'criterion_text':text.strip(),'test_type':typ})
    return {'title':proposal['title'].strip(),'story_text':proposal['story_text'].strip(),
            'rationale':proposal['rationale'].strip(),'acceptance_criteria':clean}


def apply_approved(original:dict, approved:dict[str,dict], requirements:list[dict], evidence:dict|None=None):
    """Return a new snapshot; never mutate the original or change requirement links."""
    revised=deepcopy(original)
    keys={s['story_key'] for s in revised.get('stories',[])}
    if set(approved)-keys: raise ValueError('Unknown story in approved clarifications')
    key_map={}
    for story in revised['stories']:
        old=story['story_key']
        if old not in approved: continue
        proposal=validate_proposal(approved[old])
        # Performance NFRs require explicit measurable and workload conditions;
        # syntax-only Given/When/Then is not sufficient.
        if 'NFR-004' in story.get('source_requirement_ids',[]):
            criterion_text=' '.join(c['criterion_text'].lower() for c in proposal['acceptance_criteria'])
            if not (re.search(r'\b(p95|95th percentile|p99|99th percentile)\b',criterion_text)
                    and re.search(r'\b\d+(?:\.\d+)?\s*(?:s|sec|seconds|ms|milliseconds)\b',criterion_text)
                    and re.search(r'\b\d+\s+(?:concurrent )?(?:users|requests)\b',criterion_text)):
                raise ValueError('NFR-004 requires an approved percentile, numeric response-time target and test workload')
        # Fallback is an unresolved-generation marker. Replace only after PO-approved correction.
        new=re.sub(r'^US-FALLBACK-', 'US-REVIEWED-',old)
        if new != old and new in keys: raise ValueError('Reviewed story key conflicts with an existing story')
        key_map[old]=new
        story['story_key']=new
        story['title']=proposal['title']
        story['story_text']=proposal['story_text']
        story['description']=proposal['rationale']
        story['assumptions']=[]
        story.pop('approval_status',None)
        story['clarification_of_story_key']=old
        story['clarification_rationale']=proposal['rationale']
    revised['acceptance_criteria']=[c for c in revised.get('acceptance_criteria',[]) if c.get('story_key') not in approved]
    for old,proposal in approved.items():
        for index,item in enumerate(validate_proposal(proposal)['acceptance_criteria'],1):
            revised['acceptance_criteria'].append({'story_key':key_map[old],
                 'criterion_key':f'AC-PO-{re.sub(r"[^0-9]","",old) or str(index)}-{index:02d}',**item})
    for dep in revised.get('dependencies',[]):
        for field in ('story_key','depends_on_story_key'):
            dep[field]=key_map.get(dep.get(field),dep.get(field))
    validation=validate({**revised,'requirements':requirements})
    clearances,validation=clearance_report(revised,requirements,evidence)
    revised['validation']=validation
    revised['story_clearances']=clearances
    return revised
