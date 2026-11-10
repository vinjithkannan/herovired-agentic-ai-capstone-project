import importlib.util
import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('phase7_submission',Path(__file__).resolve().parents[1]/'scripts/phase7_submission_check.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Phase7SubmissionTests(unittest.TestCase):
    def test_partial_backlog_is_not_misrepresented(self):
        backlog={'stories':[{'story_key':'US-001','approval_status':'approved'},
                            {'story_key':'US-002','approval_status':'pending'},
                            {'story_key':'US-003','approval_status':'approved'}],
                 'story_clearances':{'US-001':{'status':'quality_cleared'},
                                     'US-002':{'status':'review_required'},
                                     'US-003':{'status':'blocked'}}}
        result=module.backlog_metrics(backlog)
        self.assertEqual(result['clearance_counts'],{'quality_cleared':1,'review_required':1,'blocked':1,'unknown':0})
        self.assertEqual(result['clearance_and_approval_eligible'],1)
        self.assertTrue(result['partial_demo'])
    def test_unknown_cannot_be_counted_cleared(self):
        result=module.backlog_metrics({'stories':[{'story_key':'missing','approval_status':'approved'}]})
        self.assertEqual(result['clearance_counts']['unknown'],1)
        self.assertEqual(result['clearance_and_approval_eligible'],0)
    def test_uploaded_private_data_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);uploads=root/'data/uploads';uploads.mkdir(parents=True)
            (uploads/'secret.txt').write_text('private')
            result=module.verify_files(root)
            self.assertIn('data/uploads/secret.txt',result['unexpected_local_artifacts'])
            self.assertFalse(result['local_artifacts_excluded'])
    def test_submission_files_present_in_release(self):
        root=Path(__file__).resolve().parents[1]
        result=module.verify_files(root)
        self.assertTrue(result['required_files_present'],result)
        # A developer checkout legitimately contains .env, node_modules and uploads.
        # Validate those artifacts in strict submission mode, not here.
        self.assertIsInstance(result['unexpected_local_artifacts'],list)
    def test_working_checkout_can_have_local_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in module.REQUIRED:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('placeholder')
            (root/'.env').write_text('DEVELOPMENT_ONLY=1')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=module.main(['--root',str(root)])
            report=json.loads(output.getvalue())
            self.assertEqual(code,0)
            self.assertTrue(report['working_checkout_ok'])
            self.assertFalse(report['submission_ready'])
            self.assertIn('.env',report['files']['unexpected_local_artifacts'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(['--root',str(root),'--mode','submission']),1)
    def test_clean_submission_passes_strict_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in module.REQUIRED:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('placeholder')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=module.main(['--root',str(root),'--mode','submission'])
            self.assertEqual(code,0)
            self.assertTrue(json.loads(output.getvalue())['submission_ready'])

if __name__=='__main__': unittest.main()
