"""Consistent pseudonyms + fail-closed egress gate (section 6, GDPR)."""
import unittest

import _bootstrap  # noqa: F401
from egp.pseudonymize import Pseudonymizer, egress_gate, EgressBlocked


class TestPseudonymisation(unittest.TestCase):
    def setUp(self):
        self.pz = Pseudonymizer.with_key(b"x" * 32, label="PERSON")

    def test_same_entity_maps_to_same_pseudonym(self):
        # Relationships must survive: "Kovacs" is the same across documents.
        a = self.pz.pseudonym_for("Janos Kovacs")
        b = self.pz.pseudonym_for("Janos Kovacs")
        self.assertEqual(a, b)

    def test_different_entities_map_differently(self):
        self.assertNotEqual(self.pz.pseudonym_for("Janos Kovacs"),
                            self.pz.pseudonym_for("Eva Nagy"))

    def test_keyed_hash_depends_on_secret(self):
        other = Pseudonymizer.with_key(b"y" * 32, label="PERSON")
        self.assertNotEqual(self.pz.pseudonym_for("Janos Kovacs"),
                            other.pseudonym_for("Janos Kovacs"))

    def test_weak_key_rejected(self):
        with self.assertRaises(ValueError):
            Pseudonymizer.with_key(b"tooshort")

    def test_longer_identifier_replaced_first(self):
        text = "Janos Kovacs and Janos are the same person here."
        masked = self.pz.pseudonymize_text(text, ["Janos Kovacs", "Janos"])
        # "Janos Kovacs" must not be half-masked into "[PERSON_x] Kovacs".
        self.assertNotIn("Kovacs", masked)

    def test_authorised_reidentification_inside_boundary(self):
        p = self.pz.pseudonym_for("Janos Kovacs")
        self.assertEqual(self.pz.reidentify(p), "Janos Kovacs")

    def test_crypto_shred_makes_mapping_irreversible(self):
        p = self.pz.pseudonym_for("Janos Kovacs")
        self.pz.crypto_shred()
        self.assertIsNone(self.pz.reidentify(p))


class TestEgressGate(unittest.TestCase):
    def test_raw_identifier_is_blocked(self):
        with self.assertRaises(EgressBlocked):
            egress_gate("Janos Kovacs owes EUR 10,000", ["Janos Kovacs"])

    def test_error_does_not_echo_the_leaked_value(self):
        try:
            egress_gate("Janos Kovacs owes EUR 10,000", ["Janos Kovacs"])
            self.fail("expected EgressBlocked")
        except EgressBlocked as e:
            # The guard must not itself leak the identifier in the error message.
            self.assertNotIn("Kovacs", str(e))

    def test_pseudonymised_payload_passes(self):
        pz = Pseudonymizer.with_key(b"z" * 32)
        masked = pz.pseudonymize_text("Janos Kovacs owes EUR 10,000", ["Janos Kovacs"])
        # Should not raise.
        self.assertEqual(egress_gate(masked, ["Janos Kovacs"]), masked)


if __name__ == "__main__":
    unittest.main()
