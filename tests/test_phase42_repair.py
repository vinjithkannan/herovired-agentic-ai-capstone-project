import copy
import unittest
from unittest.mock import patch
from agents.story_generation.repair import repair_backlog
from agents.story_generation.quality import topic

REQS = [
 {'temporary_id':'FR-001','statement':'Faculty records attendance for assigned courses'},
 {'temporary_id':'FR-002','statement':'Students view their own attendance and percentage'},
 {'temporary_id':'NFR-001','statement':'Role-based access control with scope restrictions'},
 {'temporary_id':'NFR-002','statement':'Audit trails for attendance creation and correction'},
 {'temporary_id':'NFR-003','statement':'Availability during university operating hours, target not specified'},
 {'temporary_id':'NFR-004','statement':'Attendance lists and reports response time target unspecified'},
]

def story(k, rid, title, text):
 return dict(story_key=k, epic_key='E1',title=title,story_text=text,description='',source_requirement_ids=[rid],priority_recommendation='should',priority_rationale='',story_points=3,estimate_rationale='',assumptions=[])

def criteria(k, text):
 return dict(story_key=k,criterion_key='AC-'+k,criterion_text=text,test_type='functional')

class RepairTests(unittest.TestCase):
 def fixture(self):
  return dict(epics=[dict(epic_key='E1',title='Attendance',description='',business_value='',source_requirement_ids=[r['temporary_id'] for r in REQS])],
   stories=[
    story('US-001','FR-001','Record attendance','As a faculty member, I want to record attendance, so that records exist.'),
    story('US-002','FR-002','View own attendance','As a student, I want to view my attendance, so that I can track it.'),
    story('US-003','NFR-001','Access restrictions','As a user, I want access restrictions, so that access is limited.'),
    story('US-004','NFR-002','Student records','As a student, I want to view my attendance, so that I can track it.'),
    story('US-005','NFR-003','Access Control for Admins','As an admin, I want access permissions, so that data is protected.'),
    story('US-006','NFR-004','Record attendance','As a faculty member, I want to record attendance, so that records exist.')],
   acceptance_criteria=[
    criteria('US-001','Given faculty, When attendance is entered, Then it is recorded.'),
    criteria('US-002','Given a student, When attendance is viewed, Then own attendance is shown.'),
    criteria('US-003','Given a role, When access is requested, Then only permitted scope is shown.'),
    criteria('US-004','Given a student, When attendance is viewed, Then it is shown.'),
    criteria('US-005','Given an admin logs in, When an action is requested, Then access is checked.'),
    criteria('US-006','Given faculty, When attendance is entered, Then it is recorded.')],
   dependencies=[dict(story_key='US-001',depends_on_story_key='US-002',dependency_type='blocks',rationale='wrong direction')])
 def test_repair_reduces_findings_and_keeps_input_immutable(self):
  original=self.fixture(); snapshot=copy.deepcopy(original)
  fixed,audit=repair_backlog(original, REQS, use_ollama=False)
  self.assertEqual(original,snapshot)
  self.assertLess(audit['after_blocking_findings'],audit['before_blocking_findings'])
  self.assertIn('US-001', audit['preserved_story_keys'])
  self.assertIn('US-005', audit['changed_story_keys'])
  self.assertFalse(fixed['dependencies'])
  self.assertIn('availability',next(s for s in fixed['stories'] if s['story_key']=='US-005')['title'].lower())
 def test_ollama_bad_proposal_is_discarded(self):
  bad={'title':'Admin scope','story_text':'As an admin, I want to export attendance, so that I can share it.',
       'criterion_text':'Given an admin, When export is requested, Then download all data.'}
  with patch('agents.story_generation.repair.chat_json',return_value=bad):
   fixed,_=repair_backlog(self.fixture(),REQS,use_ollama=True)
  self.assertNotIn('download',str(fixed['acceptance_criteria']).lower())
 def test_avoid_false_audit_on_logged_in(self):
  self.assertEqual(topic('Given faculty is logged in, When allowed by role restrictions, Then records are visible.'),'access')

if __name__=='__main__':unittest.main()
