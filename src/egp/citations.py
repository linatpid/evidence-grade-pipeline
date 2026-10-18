"""
Citation / quotation verification — "answers linked to supporting source passages,
with unsupported claims flagged" (Verdictum initial requirement + sections 1, 4, 9).

The research consensus for legal defensibility (AIS; RAGAS faithfulness; the
Magesh 2025 finding that even Lexis/Westlaw RAG hallucinate 17-33%) is:
NEVER treat the presence of a citation as proof of support. Every claim must be
classified and gated:

  EVIDENCE    -> the quote exactly appears in the cited passage (deterministic
                 substring + offset match). This is the strongest, machine-checkable
                 tier and is what we implement fully here.
  INFERENCE   -> not verbatim, but entailed by the passage. Real systems verify
                 this with an NLI/entailment model; that is a model call, so here
                 it is an explicit, swappable interface (NOT faked as "verified").
  UNSUPPORTED -> neither verbatim nor entailed -> flagged, never surfaced as fact.

The verifier is fail-closed: if a quote cannot be located exactly in the cited
passage, the finding is downgraded to UNSUPPORTED and flagged for review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable

from .identity import canonicalize_text
from .model import Passage, Finding, ClaimType


@dataclass
class VerificationResult:
    verified_type: ClaimType
    located_offset: Optional[int] = None  # offset of the exact quote within the passage
    detail: str = ""


# An entailment checker maps (hypothesis_claim, premise_text) -> bool.
# In production this is an NLI model call. We keep it injectable so the gate is
# honest: with no checker provided, non-verbatim claims are UNSUPPORTED, not
# optimistically "verified".
EntailmentChecker = Callable[[str, str], bool]


def verify_quote(quote: str, passage: Passage) -> Optional[int]:
    """Return the offset of ``quote`` within the passage's canonical text, else None.

    Deterministic exact-span match — not embedding similarity. A legally usable
    quotation must literally appear in the source; a near-paraphrase is a defect.
    """
    hay = canonicalize_text(passage.text)
    needle = canonicalize_text(quote)
    if not needle:
        return None
    idx = hay.find(needle)
    return idx if idx >= 0 else None


def classify_claim(claim: str, passages: list, *, quote: Optional[str] = None,
                   entailment: Optional[EntailmentChecker] = None
                   ) -> VerificationResult:
    """Classify a claim against its cited passages, fail-closed.

    1. If a verbatim quote is offered and exactly matches a cited passage -> EVIDENCE.
    2. Else, if an entailment checker is supplied and confirms support -> INFERENCE.
    3. Else -> UNSUPPORTED (flagged).
    """
    if quote:
        for p in passages:
            off = verify_quote(quote, p)
            if off is not None:
                return VerificationResult(ClaimType.EVIDENCE, off,
                                          f"exact quote located in passage {p.id}")
        return VerificationResult(ClaimType.UNSUPPORTED, None,
                                  "offered quote does not appear verbatim in any cited passage")

    if entailment is not None:
        for p in passages:
            if entailment(claim, canonicalize_text(p.text)):
                return VerificationResult(ClaimType.INFERENCE, None,
                                          f"claim entailed by passage {p.id} (NLI)")
        return VerificationResult(ClaimType.UNSUPPORTED, None,
                                  "no cited passage entails the claim")

    # No quote and no entailment checker: we cannot establish support -> flag it.
    return VerificationResult(ClaimType.UNSUPPORTED, None,
                              "no verbatim quote and no entailment check available")


def make_verified_finding(claim: str, passages: list, rule: str, model_version: str,
                          *, quote: Optional[str] = None,
                          entailment: Optional[EntailmentChecker] = None) -> Finding:
    """Build a Finding whose claim_type reflects actual verification, not hope."""
    result = classify_claim(claim, passages, quote=quote, entailment=entailment)
    return Finding(
        claim=claim,
        claim_type=result.verified_type,
        passage_ids=tuple(p.id for p in passages),
        rule=rule,
        model_version=model_version,
        quote=quote if result.verified_type == ClaimType.EVIDENCE else None,
        note=result.detail,
    )
