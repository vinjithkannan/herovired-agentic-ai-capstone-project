import unittest

from agents.requirements_analysis.nodes import (
    _canonical_source_refs, _normalise_requirement, _explicit_requirements_from_brd,
)


class EvidenceValidationTests(unittest.TestCase):
    def setUp(self):
        self.context = [{
            "filename": "student-attendance-management.md",
            "chunk_index": 0,
            "content": "- **FR-001 — Mark attendance:** Faculty can record attendance for students enrolled in a course they are assigned to teach.\n- **FR-002 — View attendance:** Students can view their attendance records and percentage for each enrolled course.",
        }]

    def test_exact_quote_is_supported(self):
        requirement = {
            "statement": "Faculty can record attendance for students enrolled in a course they are assigned to teach.",
            "source_refs": [{
                "filename": "student-attendance-management.md",
                "chunk_index": 0,
                "quote": "Faculty can record attendance for students enrolled in a course they are assigned to teach.",
            }],
        }
        refs, status = _canonical_source_refs(requirement, self.context)
        self.assertEqual(status, "supported")
        self.assertEqual(refs[0]["chunk_index"], 0)

    def test_missing_or_bad_quote_uses_source_sentence_match(self):
        requirement = {
            "statement": "Students can view their attendance records and percentage for each enrolled course.",
            "source_refs": [{"filename": "wrong-file.md", "chunk_index": 99, "quote": "invented quotation"}],
        }
        refs, status = _canonical_source_refs(requirement, self.context)
        self.assertEqual(status, "supported")
        self.assertIn("Students can view their attendance records", refs[0]["quote"])

    def test_requirement_aliases_are_normalised(self):
        item = _normalise_requirement({"id": "FR-001", "description": "Faculty can record attendance"}, 1)
        self.assertEqual(item["temporary_id"], "FR-001")
        self.assertEqual(item["statement"], "Faculty can record attendance")
        self.assertEqual(item["requirement_type"], "functional")

    def test_explicit_brd_ids_supplement_small_model_omissions(self):
        with open("data/sample_brd/student-attendance-management.md", encoding="utf-8") as source:
            content = source.read()
        context = [{"filename": "student-attendance-management.md", "chunk_index": 0, "content": content}]
        requirements = _explicit_requirements_from_brd(context)
        ids = {item["temporary_id"] for item in requirements}
        self.assertTrue({"FR-001", "FR-002", "FR-003", "FR-004", "FR-005", "NFR-001", "NFR-002", "NFR-003", "NFR-004"}.issubset(ids))

    def test_unrelated_but_verbatim_quote_is_not_supported(self):
        requirement = {
            "statement": "The system exports encrypted payroll transactions to a blockchain ledger.",
            "source_refs": [{"filename": "student-attendance-management.md", "chunk_index": 0, "quote": "Students can view their attendance records and percentage for each enrolled course."}],
        }
        refs, status = _canonical_source_refs(requirement, self.context)
        self.assertIn(status, {"partial", "unsupported"})


if __name__ == "__main__":
    unittest.main()
