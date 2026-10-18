"""Run-level ledger, fail-closed release gate, preserved retries (section 7)."""
import unittest

import _bootstrap  # noqa: F401
from egp.ledger import RunLedger, ReleaseBlocked
from egp.states import StepState


def _run():
    r = RunLedger(run_id="run_1", case_id="C1", tenant_id="firm-a")
    r.plan("ingest", produces="manifest")
    r.plan("analyse", produces="findings")
    r.plan("optional_enrich", required=False)
    return r


class TestFailClosedLedger(unittest.TestCase):
    def test_clean_run_is_releasable(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        r.record("analyse", StepState.COMPLETED, output_hash="h2", schema_valid=True)
        r.record("optional_enrich", StepState.SKIPPED, reason="not requested")
        self.assertTrue(r.is_releasable())
        self.assertEqual(r.broken_links(), [])

    def test_planned_but_never_activated_blocks_release(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        # 'analyse' is required but never recorded -> must block.
        self.assertFalse(r.is_releasable())
        with self.assertRaises(ReleaseBlocked):
            r.assert_releasable()

    def test_failed_required_step_blocks_and_names_the_link(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        r.record("analyse", StepState.FAILED, reason="model timeout")
        problems = r.broken_links()
        self.assertFalse(r.is_releasable())
        self.assertTrue(any(p["step"] == "analyse" for p in problems))

    def test_missing_required_output_blocks_even_if_completed(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, schema_valid=True)  # no output_hash!
        r.record("analyse", StepState.COMPLETED, output_hash="h2", schema_valid=True)
        self.assertFalse(r.is_releasable())
        self.assertTrue(any("manifest" in p.get("problem", "") for p in r.broken_links()))

    def test_schema_invalid_output_blocks(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        r.record("analyse", StepState.COMPLETED, output_hash="h2", schema_valid=False)
        self.assertFalse(r.is_releasable())

    def test_reason_required_for_nonterminal_states(self):
        r = _run()
        with self.assertRaises(ValueError):
            r.record("analyse", StepState.FAILED)  # no reason

    def test_retries_are_appended_not_overwritten(self):
        r = _run()
        r.record("ingest", StepState.FAILED, reason="transient read error")
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        attempts = r.steps["ingest"].attempts
        self.assertEqual(len(attempts), 2)                 # prior attempt preserved
        self.assertEqual(attempts[0].state, StepState.FAILED)
        self.assertEqual(attempts[-1].state, StepState.COMPLETED)

    def test_cost_is_recorded_per_attempt(self):
        r = _run()
        r.record("ingest", StepState.COMPLETED, output_hash="h1", schema_valid=True)
        r.record("analyse", StepState.COMPLETED, output_hash="h2", schema_valid=True,
                 model="claude-opus", tokens_in=1000, tokens_out=500, cost_usd=0.0225)
        self.assertAlmostEqual(r.total_cost_usd(), 0.0225)
        self.assertEqual(len(r.cost_breakdown()), 2)

    def test_recording_unplanned_step_rejected(self):
        r = _run()
        with self.assertRaises(ValueError):
            r.record("ghost_step", StepState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
