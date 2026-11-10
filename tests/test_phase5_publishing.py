import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'backend'))
from integrations.publishing import validate_target, story_markdown, PublishError, jira_adf

class PublishingTests(unittest.TestCase):
    def test_github_target_rejects_bad_slug(self):
        with self.assertRaises(PublishError):
            validate_target('github',{'github_owner':'bad owner','github_repository':'repo'})
    def test_jira_url_requires_atlassian_https(self):
        with self.assertRaises(PublishError):
            validate_target('jira',{'jira_base_url':'http://localhost:3333','jira_project_key':'ABC'})
    def test_traceable_story(self):
        story={'story_key':'US-001','title':'Record','story_text':'As faculty...','epic_key':'EPIC-001','source_requirement_ids':['FR-001'],'approval_status':'approved'}
        body=story_markdown(story,[{'story_key':'US-001','criterion_key':'AC-1','criterion_text':'Given...','test_type':'functional'}],'project','backlog')
        self.assertIn('ReqFlow-Origin: project=project; backlog=backlog; story=US-001',body)
        self.assertIn('FR-001',body)
        self.assertIn('AC-1',body)
    def test_adf_format(self):
        doc=jira_adf('Hello\nWorld')
        self.assertEqual(doc['type'],'doc')
        self.assertEqual(len(doc['content']),2)

if __name__=='__main__': unittest.main()
