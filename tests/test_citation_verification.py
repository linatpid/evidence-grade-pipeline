"""Exact-quote verification and unsupported-claim flagging (sections 1, 4, 9)."""
import unittest

import _bootstrap  # noqa: F401
from egp.model import Passage, ClaimType
from egp.citations import classify_claim, make_verified_finding, verify_quote
from egp.identity import content_id


def _passage(text):
    pid = content_id("page", "src", "1", text)
    return Passage(pid, "src", 1, 0, len(text), text)


class TestCitationVerification(unittest.TestCase):
    def setUp(self):
        self.p = _passage("The defendant signed the agreement on 3 March 2026 in Budapest.")

    def test_exact_quote_is_evidence(self):
        r = classify_claim("signing date claim", [self.p],
                           quote="signed the agreement on 3 March 2026")
        self.assertEqual(r.verified_type, ClaimType.EVIDENCE)
        self.assertIsNotNone(r.located_offset)

    def test_quote_not_present_is_unsupported(self):
        r = classify_claim("signing date claim", [self.p],
                           quote="signed the agreement on 4 April 2026")
        self.assertEqual(r.verified_type, ClaimType.UNSUPPORTED)

    def test_paraphrase_without_entailment_checker_is_unsupported(self):
        # No verbatim quote and no NLI available -> we must NOT claim support.
        r = classify_claim("The defendant executed the contract in Hungary.", [self.p])
        self.assertEqual(r.verified_type, ClaimType.UNSUPPORTED)

    def test_paraphrase_with_entailment_checker_is_inference(self):
        # Injected NLI confirms support -> INFERENCE (not EVIDENCE, not UNSUPPORTED).
        always_entails = lambda claim, premise: True
        r = classify_claim("The defendant executed the contract in Hungary.", [self.p],
                           entailment=always_entails)
        self.assertEqual(r.verified_type, ClaimType.INFERENCE)

    def test_cosmetic_whitespace_differences_still_match(self):
        p = _passage("fee is   EUR 10,000")  # internal double space is preserved...
        # ...so an exact-span quote must match the real text.
        self.assertIsNotNone(verify_quote("fee is   EUR 10,000", p))

    def test_finding_only_keeps_quote_when_verified(self):
        good = make_verified_finding("date", [self.p], "extract", "deterministic",
                                     quote="3 March 2026")
        bad = make_verified_finding("date", [self.p], "extract", "deterministic",
                                    quote="9 September 2099")
        self.assertEqual(good.claim_type, ClaimType.EVIDENCE)
        self.assertIsNotNone(good.quote)
        self.assertEqual(bad.claim_type, ClaimType.UNSUPPORTED)
        self.assertIsNone(bad.quote)  # an unverified quote is never carried as fact

    def test_finding_references_passages_not_loose_text(self):
        f = make_verified_finding("date", [self.p], "extract", "deterministic",
                                  quote="3 March 2026")
        self.assertEqual(f.passage_ids, (self.p.id,))


if __name__ == "__main__":
    unittest.main()
