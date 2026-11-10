import unittest
from app.services.evaluation import evaluate


class TestEvaluationCategories(unittest.TestCase):
    def setUp(self):
        ids = ['BRD-ATT-001'] + [f'FR-{i:03}' for i in range(1, 6)] + [f'NFR-{i:03}' for i in range(1, 5)]
        self.ids = ids
        self.backlog = {
            'stories': [{'story_key': f'US-{i:03}', 'source_requirement_ids': [rid]} for i, rid in enumerate(ids, 1)],
            'acceptance_criteria': [
                {'story_key': f'US-{i:03}', 'criterion_text': 'Given X When Y Then Z'}
                for i in range(1, 11)
            ],
            'validation': {'issues': []},
            'story_clearances': {'US-001': {'status': 'quality_cleared'}}
        }
        self.analysis = {
            'requirements': [{'temporary_id': rid} for rid in ids],
            'validation': {'requirements': [{'temporary_id': rid, 'evidence_status': 'supported'} for rid in ids]}
        }

    def test_ten_gold(self):
        res = evaluate(self.backlog, self.ids, self.analysis)
        self.assertEqual(res['f1'], 1.0)
        self.assertEqual(res['requirement_categories']['business']['true_positive'], 1)
        self.assertEqual(res['implementation_backlog_coverage']['golden_count'], 9)
        self.assertEqual(res['implementation_backlog_coverage']['f1'], 1.0)
        self.assertEqual(res['story_count'], 10)

    def test_nine_gold(self):
        res = evaluate(self.backlog, self.ids[1:], self.analysis)
        self.assertEqual(res['f1'], 0.9474)
        self.assertEqual(res['unexpected_requirement_ids'], ['BRD-ATT-001'])
        self.assertEqual(res['implementation_backlog_coverage']['f1'], 1.0)
        self.assertIsNone(res['requirement_categories']['business']['recall'])
        self.assertEqual(res['requirement_categories']['business']['unexpected_requirement_ids'], ['BRD-ATT-001'])

    def test_empty_gold(self):
        with self.assertRaises(ValueError):
            evaluate(self.backlog, [])

    def test_no_stories(self):
        res = evaluate({'stories': [], 'acceptance_criteria': []}, ['FR-001'])
        self.assertEqual(res['f1'], 0.0)
        self.assertIsNone(res['precision'])
        self.assertIsNone(res['stories_with_criteria_ratio'])


if __name__ == '__main__':
    unittest.main()
