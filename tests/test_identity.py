"""Stable, content-addressable identity (Verdictum sections 1, 3)."""
import unittest

import _bootstrap  # noqa: F401
from egp.identity import content_id, finding_id, canonicalize_text, hash_bytes


class TestStableIdentity(unittest.TestCase):
    def test_same_content_same_id_across_reprocessing(self):
        # Reprocessing the identical page later must yield the identical id.
        a = content_id("page", "src_x", "1", "The fee is EUR 10,000.")
        b = content_id("page", "src_x", "1", "The fee is EUR 10,000.")
        self.assertEqual(a, b)

    def test_cosmetic_variance_does_not_change_id(self):
        # CRLF vs LF and trailing spaces are non-semantic -> same id.
        a = content_id("passage", "pg1", "0:10", "line one\r\nline two  ")
        b = content_id("passage", "pg1", "0:10", "line one\nline two")
        self.assertEqual(a, b)

    def test_semantic_change_changes_id(self):
        a = content_id("passage", "pg1", "0:10", "fee is EUR 10,000")
        b = content_id("passage", "pg1", "0:10", "fee is EUR 50,000")
        self.assertNotEqual(a, b)

    def test_ids_are_self_describing(self):
        self.assertTrue(content_id("source", "abc").startswith("src_"))
        self.assertTrue(content_id("finding", "abc").startswith("fnd_"))

    def test_finding_id_is_derived_from_its_evidence(self):
        # Same passage + rule + model => same finding id (idempotent).
        f1 = finding_id("psg_1", "contradiction", "claude-x")
        f2 = finding_id("psg_1", "contradiction", "claude-x")
        self.assertEqual(f1, f2)
        # Different evidence => different finding id (can't silently re-point).
        self.assertNotEqual(f1, finding_id("psg_2", "contradiction", "claude-x"))
        self.assertNotEqual(f1, finding_id("psg_1", "contradiction", "claude-y"))

    def test_hash_of_bytes_is_tamper_evident(self):
        self.assertNotEqual(hash_bytes(b"original"), hash_bytes(b"0riginal"))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            content_id("not-a-kind", "x")


if __name__ == "__main__":
    unittest.main()
