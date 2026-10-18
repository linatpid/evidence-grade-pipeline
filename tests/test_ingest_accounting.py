"""Ingestion accounting, count reconciliation, OCR confidence (section 3)."""
import unittest

import _bootstrap  # noqa: F401
from egp.model import Source
from egp.ingest import Manifest, ingest_page, OCR_REVIEW_THRESHOLD
from egp.states import ResultStatus


def _source(name="f.pdf"):
    return Source.from_bytes(b"bytes-of-" + name.encode(), name, "application/pdf")


class TestIngestionAccounting(unittest.TestCase):
    def test_every_page_accounted_and_counts_reconcile(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=3)
        ingest_page(item, 1, "page one text")
        ingest_page(item, 2, "page two text")
        ingest_page(item, 3, "page three text")
        self.assertTrue(item.counts_reconcile)
        self.assertTrue(m.coverage()["all_counts_reconcile"])
        self.assertTrue(m.coverage()["clean"])

    def test_missing_page_breaks_reconciliation(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=3)
        ingest_page(item, 1, "page one")
        ingest_page(item, 2, "page two")  # page 3 never arrives
        self.assertFalse(item.counts_reconcile)
        self.assertFalse(m.coverage()["clean"])

    def test_empty_page_is_a_true_zero_not_a_failure(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=1)
        outcome = ingest_page(item, 1, "   ")  # genuinely blank page
        self.assertEqual(outcome.status, ResultStatus.COMPLETE_ZERO)
        self.assertIsNotNone(outcome.page)  # it still exists and is accounted for

    def test_low_confidence_material_ocr_forces_remediation(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=1)
        outcome = ingest_page(item, 1, "garbl3d t3xt", is_ocr=True,
                              ocr_confidence=0.40, material=True)
        # The decisive distinction: this is UNVERIFIED, not COMPLETE_ZERO.
        self.assertEqual(outcome.status, ResultStatus.UNVERIFIED)
        self.assertTrue(item.needs_remediation)
        cov = m.coverage()
        self.assertFalse(cov["clean"])
        self.assertEqual(len(cov["unverified_pages"]), 1)
        self.assertEqual(len(cov["remediation_worklist"]), 1)

    def test_high_confidence_ocr_passes(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=1)
        outcome = ingest_page(item, 1, "clean recognised text", is_ocr=True,
                              ocr_confidence=0.98, material=True)
        self.assertEqual(outcome.status, ResultStatus.COMPLETE_NONZERO)
        self.assertFalse(item.needs_remediation)

    def test_failed_extraction_is_flagged_not_silent(self):
        m = Manifest()
        item = m.register_source(_source(), expected_pages=1)
        outcome = ingest_page(item, 1, None)  # extraction returned nothing
        self.assertEqual(outcome.status, ResultStatus.FAILED)
        self.assertTrue(item.needs_remediation)

    def test_threshold_is_sane(self):
        self.assertTrue(0 < OCR_REVIEW_THRESHOLD < 1)


if __name__ == "__main__":
    unittest.main()
