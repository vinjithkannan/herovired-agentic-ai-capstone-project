import unittest
from unittest.mock import Mock
import httpx
from app.services.publication_reconciliation import _github_issues, _jira_issues, ReconciliationError, _strings

class RemoteScanTests(unittest.TestCase):
    def test_github_exact_marker_found(self):
        c=Mock()
        c.get.return_value=Mock(status_code=200,json=lambda:[{'number':7,'html_url':'https://github.com/example/project/issues/7','body':'ReqFlow-Origin: exact'}],raise_for_status=lambda:None)
        found=_github_issues(c,{'github_owner':'example','github_repository':'project','github_token':'secret'},'ReqFlow-Origin: exact')
        self.assertEqual(found[0]['external_id'],'7')
        self.assertEqual(c.get.call_count,1)

    def test_github_unknown_is_not_assumed_absent(self):
        c=Mock()
        c.get.return_value.raise_for_status.side_effect=httpx.HTTPStatusError('forbidden',request=httpx.Request('GET','https://api.github.com'),response=httpx.Response(403,request=httpx.Request('GET','https://api.github.com')))
        with self.assertRaises(httpx.HTTPStatusError):
            _github_issues(c,{'github_owner':'example','github_repository':'project','github_token':'secret'},'marker')

    def test_jira_adf_marker_found(self):
        marker='ReqFlow-Origin: project=x; backlog=y; story=US-001'
        c=Mock()
        response=Mock(json=lambda:{'issues':[{'key':'RF-1','fields':{'description':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':marker}]}]}}}]},raise_for_status=lambda:None)
        c.get.return_value=response
        found=_jira_issues(c,{'jira_base_url':'https://sample.atlassian.net','jira_project_key':'RF','jira_email':'a@example.org','jira_api_token':'TOKEN'},marker,'US-001')
        self.assertEqual(found[0]['external_id'],'RF-1')

    def test_adf_nested_text(self):
        self.assertIn('hello',list(_strings({'type':'paragraph','content':[{'type':'text','text':'hello'}]})))

if __name__=='__main__':unittest.main()
