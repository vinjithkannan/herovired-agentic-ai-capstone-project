import sys
import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from app.services.auth_service import password_hash, password_matches, require_roles
from app.services.evaluation import evaluate
from app.services.observability import observe, snapshot

class Phase6AuthTests(unittest.TestCase):
    def test_password_hash_and_verify(self):
        encoded=password_hash('a-secure-passphrase-2026',salt=b'1234567890abcdef')
        self.assertTrue(password_matches('a-secure-passphrase-2026',encoded))
        self.assertFalse(password_matches('wrong-password-here',encoded))
        self.assertNotIn('a-secure-passphrase',encoded)

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            password_hash('123')

    def test_invalid_hash_rejected(self):
        self.assertFalse(password_matches('password','invalid'))

    def test_role_gate_denies_viewer(self):
        dep=require_roles('product_owner')
        with self.assertRaises(HTTPException) as cm:
            dep(SimpleNamespace(state=SimpleNamespace(user={'role':'viewer'})))
        self.assertEqual(cm.exception.status_code,403)

    def test_role_gate_admin_override(self):
        dep=require_roles('product_owner')
        u={'role':'admin'}
        self.assertIs(dep(SimpleNamespace(state=SimpleNamespace(user=u))),u)

    def test_role_gate_unauthenticated(self):
        dep=require_roles('engineer')
        with self.assertRaises(HTTPException) as cm:
            dep(SimpleNamespace(state=SimpleNamespace()))
        self.assertEqual(cm.exception.status_code,401)

class Phase6EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.backlog={'stories':[{'story_key':'US-001','source_requirement_ids':['FR-001','FR-002']}],
                      'acceptance_criteria':[{'story_key':'US-001','criterion_text':'Given x When y Then z'}],
                      'validation':{'issues':[]},'story_clearances':{'US-001':{'status':'quality_cleared'}}}

    def test_gold_coverage(self):
        m=evaluate(self.backlog,['FR-001','FR-003'])
        self.assertEqual(m['precision'],.5)
        self.assertEqual(m['recall'],.5)
        self.assertEqual(m['missing_requirement_ids'],['FR-003'])
        self.assertEqual(m['unexpected_requirement_ids'],['FR-002'])

    def test_source_analysis_proxy(self):
        source={'requirements':[{'temporary_id':'FR-001'},{'temporary_id':'FR-003'}],
                'validation':{'requirements':[{'temporary_id':'FR-001','evidence_status':'supported'},
                                              {'temporary_id':'FR-003','evidence_status':'unsupported'}]}}
        m=evaluate(self.backlog,['FR-001','FR-002'],source)
        self.assertEqual(m['source_supported_ratio'],0.5)
        self.assertEqual(m['given_when_then_syntax_ratio'],1)

    def test_empty_gold_rejected(self):
        with self.assertRaises(ValueError): evaluate(self.backlog,[])

    def test_zero_stories_no_divide(self):
        m=evaluate({'stories':[],'acceptance_criteria':[]},['FR-001'])
        self.assertEqual(m['recall'],0)
        self.assertIsNone(m['precision'])

    def test_metrics_not_dynamic_urls(self):
        observe('/api/v1/projects','GET',200,.12)
        self.assertTrue(any(x['route']=='/api/v1/projects' for x in snapshot()))

if __name__=='__main__':unittest.main()
