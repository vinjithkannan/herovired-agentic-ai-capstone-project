import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
from app.services.story_clearance import clearance_report, require_clearance


def sample(title='Record attendance', statement='Faculty members record attendance'):
    return {'epics': [], 'stories': [{'story_key':'US-001','epic_key':'EPIC-001','title': title,
          'story_text':'As faculty, I want to record attendance, so that records are accurate.',
          'source_requirement_ids':['FR-001'],'story_points':3, 'assumptions':[]}],
          'acceptance_criteria':[{'story_key':'US-001','criterion_key':'AC-001','criterion_text':'Given faculty access, When attendance is submitted, Then it is saved.'}],
          'dependencies':[]}, [{'temporary_id':'FR-001','statement':statement}]

class StoryClearanceTests(unittest.TestCase):
    def test_clean_story_clearance_independent_of_approval(self):
        backlog, reqs=sample()
        backlog['stories'][0]['approval_status']='pending'
        result, validation=clearance_report(backlog, reqs, {'FR-001':'supported'})
        self.assertEqual(result['US-001']['status'],'quality_cleared')
        self.assertTrue(validation['quality_gate_version'])
        self.assertEqual(require_clearance(result,'US-001')['status'],'quality_cleared')

    def test_low_estimate_findings_do_not_block(self):
        backlog,reqs=sample();backlog['stories'][0]['story_points']=None
        result,_=clearance_report(backlog,reqs,{'FR-001':'supported'})
        self.assertEqual(result['US-001']['status'],'quality_cleared')

    def test_unresolved_assumptions_require_review(self):
        backlog,reqs=sample();backlog['stories'][0]['assumptions']=['Actor confirmation required']
        result,_=clearance_report(backlog,reqs,{'FR-001':'supported'})
        self.assertEqual(result['US-001']['status'],'review_required')
        with self.assertRaises(ValueError): require_clearance(result,'US-001')

    def test_unsupported_evidence_blocks(self):
        backlog,reqs=sample()
        result,_=clearance_report(backlog,reqs,{'FR-001':'unsupported'})
        self.assertEqual(result['US-001']['status'],'blocked')

    def test_missing_acceptance_criteria_blocks(self):
        backlog,reqs=sample();backlog['acceptance_criteria']=[]
        result,_=clearance_report(backlog,reqs,{'FR-001':'supported'})
        self.assertEqual(result['US-001']['status'],'blocked')

    def test_scope_finding_blocks_individual_story(self):
        backlog,reqs=sample();backlog['acceptance_criteria'][0]['criterion_text']='Given faculty access, When attendance is submitted, Then the system allows download and export.'
        result,_=clearance_report(backlog,reqs,{'FR-001':'supported'})
        self.assertEqual(result['US-001']['status'],'blocked')

if __name__=='__main__':unittest.main()
