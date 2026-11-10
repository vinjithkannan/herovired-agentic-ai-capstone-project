import copy
import unittest
from app.services.clarification_service import validate_proposal, apply_approved

REQ=[{'temporary_id':'NFR-004','statement':'Attendance lists and reports must have acceptable response time targets'}]
SAMPLE={
 'stories':[{'story_key':'US-FALLBACK-010','epic_key':'EPIC-REVIEW','title':'Performance','story_text':'As a user I want quick reports.', 'description':'', 'source_requirement_ids':['NFR-004'],'assumptions':['Target undefined'],'story_points':None}],
 'acceptance_criteria':[{'story_key':'US-FALLBACK-010','criterion_key':'AC-REVIEW-US-FALLBACK-010','criterion_text':'Given targets when requested then meet them','test_type':'performance'}],
 'dependencies':[], 'epics':[{'epic_key':'EPIC-REVIEW'}]
}
PROPOSAL={'title':'Measured attendance performance',
'story_text':'As a university user, I want attendance lists and reports to meet explicit response-time goals, so that my work remains efficient.',
'rationale':'Product Owner confirmed the explicit performance targets under a representative test load.',
'acceptance_criteria':[{'criterion_text':'Given an approved attendance dataset and 50 concurrent users over 10 minutes, When attendance reports are requested, Then the p95 response time is at most 5 seconds.','test_type':'performance'}]}

class ClarificationTests(unittest.TestCase):
 def test_accepts_valid_proposal(self):
  self.assertEqual(len(validate_proposal(PROPOSAL)['acceptance_criteria']),1)
 def test_rejects_empty_criteria(self):
  p=copy.deepcopy(PROPOSAL);p['acceptance_criteria']=[]
  with self.assertRaises(ValueError):validate_proposal(p)
 def test_rejects_non_gwt(self):
  p=copy.deepcopy(PROPOSAL);p['acceptance_criteria'][0]['criterion_text']='This does not describe a measurable test.'
  with self.assertRaises(ValueError):validate_proposal(p)
 def test_rejects_unmeasured_performance(self):
  p=copy.deepcopy(PROPOSAL);p['acceptance_criteria'][0]['criterion_text']='Given targets to be defined, When a user requests reports, Then the service meets an acceptable response time.'
  with self.assertRaises(ValueError):apply_approved(SAMPLE,{'US-FALLBACK-010':p},REQ)
 def test_renames_fallback_and_preserves_original(self):
  original=copy.deepcopy(SAMPLE)
  new=apply_approved(SAMPLE,{'US-FALLBACK-010':PROPOSAL},REQ)
  self.assertEqual(new['stories'][0]['story_key'],'US-REVIEWED-010')
  self.assertEqual(new['stories'][0]['assumptions'],[])
  self.assertEqual(new['story_clearances']['US-REVIEWED-010']['status'],'quality_cleared')
  self.assertEqual(SAMPLE,original)
 def test_rejects_unknown_story(self):
  with self.assertRaises(ValueError):apply_approved(SAMPLE,{'US-FALLBACK-999':PROPOSAL},REQ)
 def test_rejects_unresolved_criteria(self):
  p=copy.deepcopy(PROPOSAL);p['acceptance_criteria'][0]['criterion_text']='Given a test target to be defined, When users request reports, Then it must complete on time.'
  with self.assertRaises(ValueError):validate_proposal(p)

if __name__=='__main__':unittest.main()
