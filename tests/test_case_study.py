"""
Worked brownfield-stabilisation case: expose the defect, then prove the fix.

These tests mirror the written account in CASE_STUDY.md:
  - the BEFORE tests characterise the legacy behaviour and demonstrate the silent
    data loss (the failure);
  - the AFTER tests prove the stabilised behaviour and guard it against regression.
"""
import unittest

import _bootstrap  # noqa: F401
from egp.case_study import before, after


# One malformed record (page 2 has no 'text') in an otherwise clean batch.
BATCH = [
    {"page": 1, "text": "The agreement is dated 3 March 2026."},
    {"page": 2},  # malformed: a partial/corrupt record
    {"page": 3, "text": "The fee is EUR 10,000."},
]


class TestLegacyDefect(unittest.TestCase):
    """Characterisation tests: capture how the inherited code actually behaves."""

    def test_before_silently_drops_the_malformed_record(self):
        out = before.process_batch(BATCH)
        # 3 records in, only 2 out...
        self.assertEqual(len(BATCH), 3)
        self.assertEqual(len(out), 2)

    def test_before_gives_the_caller_no_way_to_know(self):
        # ...and the return value carries no error, no flag, no count: the loss
        # is invisible. This is the failure an evidence-grade system cannot ship.
        out = before.process_batch(BATCH)
        self.assertNotIn(2, [p["page"] for p in out])   # page 2 is gone
        self.assertIsInstance(out, list)                 # nothing signals the drop


class TestStabilised(unittest.TestCase):
    """Prove the fix and lock it in."""

    def test_after_fails_closed_instead_of_reporting_success(self):
        with self.assertRaises(after.BatchNotReconciled):
            after.process_batch(BATCH)  # fail_closed=True by default

    def test_after_accounts_for_every_record(self):
        res = after.process_batch(BATCH, fail_closed=False)
        self.assertEqual(len(res.pages), 2)
        self.assertEqual(len(res.remediation), 1)
        # The decisive property: every input is accounted for, nothing vanishes.
        self.assertTrue(res.reconciles(len(BATCH)))
        idx, reason = res.remediation[0]
        self.assertEqual(idx, 1)                 # the malformed record's position
        self.assertIn("text", reason)            # with a diagnosable reason

    def test_after_leaves_clean_input_unchanged(self):
        clean = [{"page": 1, "text": "a"}, {"page": 2, "text": "b"}]
        res = after.process_batch(clean)
        self.assertEqual(len(res.pages), 2)
        self.assertEqual(res.remediation, [])
        self.assertTrue(res.reconciles(2))

    def test_after_never_loses_data_even_when_all_malformed(self):
        allbad = [{"page": 1}, {"page": 2}]
        res = after.process_batch(allbad, fail_closed=False)
        self.assertEqual(len(res.pages), 0)
        self.assertEqual(len(res.remediation), 2)
        self.assertTrue(res.reconciles(2))       # still fully accounted for


if __name__ == "__main__":
    unittest.main()
