import unittest
from agents.story_generation.quality import validate

REQS = [
 {'temporary_id':'FR-001','statement':'Faculty records attendance for assigned courses'},
 {'temporary_id':'FR-002','statement':'Students view their own attendance records'},
 {'temporary_id':'NFR-001','statement':'Role-based access control and scope restrictions'},
 {'temporary_id':'NFR-002','statement':'Audit trail for attendance creation and corrections'},
 {'temporary_id':'NFR-003','statement':'Service availability during university operating hours'},
 {'temporary_id':'NFR-004','statement':'Attendance report response time targets to be agreed'},
]

def story(key, rid, title, text):
 return {'story_key':key,'title':title,'story_text':text,'source_requirement_ids':[rid],'story_points':3,'assumptions':[]}

def criterion(key, text):
 return {'story_key':key,'criterion_key':'AC-'+key,'criterion_text':text}

class QualityTests(unittest.TestCase):
 def test_mismatched_nfr_and_student_write_permission(self):
  s=story('US-1','NFR-003','Access Control for Administrators','As an administrator, I want role permissions, so that access is restricted.')
  c=criterion('US-1','Given a student logs in, When they edit attendance, Then the record changes.')
  result=validate({'requirements':REQS,'stories':[s],'acceptance_criteria':[c]})
  self.assertIn('traceability', {i['issue_type'] for i in result['issues']})
  self.assertIn('permission', {i['issue_type'] for i in result['issues']})
  self.assertIn('US-1', result['approval_blocked_story_keys'])
 def test_duplicate_and_dependency_cycle(self):
  a=story('US-1','FR-001','Record Attendance','As a faculty member, I want to record attendance, so that records exist.')
  b=story('US-2','FR-002','View Attendance',a['story_text'])
  state={'requirements':REQS,'stories':[a,b], 'acceptance_criteria':[criterion('US-1','Given faculty login, When recording, Then save attendance.'),criterion('US-2','Given student login, When viewing, Then show attendance.')], 'dependencies':[{'story_key':'US-1','depends_on_story_key':'US-2','dependency_type':'blocks'}, {'story_key':'US-2','depends_on_story_key':'US-1','dependency_type':'blocks'}]}
  kinds={i['issue_type'] for i in validate(state)['issues']}
  self.assertIn('duplication', kinds)
  self.assertIn('dependency', kinds)
 def test_clean_single_story_has_no_blocking_finding(self):
  s=story('US-1','NFR-002','Audit attendance corrections','As an auditor, I want an audit trail of corrections, so that changes are traceable.')
  c=criterion('US-1','Given an authorized correction, When attendance changes, Then the audit history records the change.')
  r=validate({'requirements':[REQS[3]],'stories':[s],'acceptance_criteria':[c]})
  self.assertTrue(r['ready_for_approval'])
  self.assertEqual(r['coverage']['covered'],1)

if __name__=='__main__': unittest.main()
