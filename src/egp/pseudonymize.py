"""
Pseudonymisation + an egress verification gate (Verdictum section 6; GDPR).

Grounded in the EDPB Guidelines 01/2025 (draft) and GDPR Art. 4(5)/25/32:
  - Pseudonymised data is STILL personal data; the goal here is only to ensure
    nothing that could identify a person leaves the controlled environment on the
    way to an external model.
  - Consistent pseudonyms must preserve analytical relationships: the same entity
    maps to the same pseudonym across every document, so "Person A" stays "Person
    A" and relationships survive. We use a KEYED hash (HMAC-SHA-256 with a 256-bit
    secret) — NOT a plain hash, which is reversible for small input spaces (names,
    case numbers) and is therefore not a privacy control.
  - The re-identification map (the "additional information" of Art. 4(5)) is held
    SEPARATELY from the pseudonymised text and is never emitted.
  - An EGRESS GATE re-scans every outbound payload and FAILS CLOSED if any known
    raw identifier is still present — enforcing the provider boundary in code,
    not merely documenting it.

Scope note (honest): real pseudonymisation needs NER to *find* identifiers in
free text and careful quasi-identifier handling (date-shifting, banding). This
module demonstrates the keyed-mapping, separation and egress-gate mechanics on a
known identifier set; the NER step is an explicit, swappable input.
"""
from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Optional


class EgressBlocked(Exception):
    """Raised when an outbound payload still contains a raw identifier."""


@dataclass
class Pseudonymizer:
    """Deterministic, keyed pseudonymisation with a separately-held mapping.

    The secret key is the "additional information". Destroying it (crypto-shredding)
    makes every pseudonym irreversible — a verifiable-deletion lever.
    """
    _secret: bytes
    label: str = "PERSON"
    # The re-identification map lives on this object only. In production it belongs
    # in a separate datastore/trust boundary with its own KMS-managed key.
    _forward: dict = field(default_factory=dict)   # original -> pseudonym
    _reverse: dict = field(default_factory=dict)   # pseudonym -> original

    @classmethod
    def with_key(cls, secret: bytes, label: str = "PERSON") -> "Pseudonymizer":
        if len(secret) < 32:
            raise ValueError("pseudonymisation secret must be >= 256 bits (32 bytes)")
        return cls(_secret=secret, label=label)

    def pseudonym_for(self, original: str) -> str:
        if original in self._forward:
            return self._forward[original]
        digest = hmac.new(self._secret, original.encode("utf-8"),
                          hashlib.sha256).hexdigest()[:12]
        pseudonym = f"[{self.label}_{digest}]"
        self._forward[original] = pseudonym
        self._reverse[pseudonym] = original
        return pseudonym

    def pseudonymize_text(self, text: str, identifiers: list) -> str:
        """Replace each known identifier with its stable pseudonym.

        Longer identifiers first, so "John Smith" is replaced before "John".
        """
        out = text
        for ident in sorted(set(identifiers), key=len, reverse=True):
            if ident:
                out = out.replace(ident, self.pseudonym_for(ident))
        return out

    def reidentify(self, pseudonym: str) -> Optional[str]:
        """Authorised re-identification — only inside the controlled environment."""
        return self._reverse.get(pseudonym)

    def crypto_shred(self) -> None:
        """Destroy the mapping and key so pseudonyms become irreversible."""
        self._secret = b"\x00" * len(self._secret)
        self._forward.clear()
        self._reverse.clear()


def egress_gate(payload: str, forbidden_identifiers: list) -> str:
    """Final boundary check before a payload leaves for an external model.

    Fails closed: if any raw identifier is still present, nothing is sent.
    This is the "enforce the boundary, don't just document it" control.
    """
    leaked = [ident for ident in forbidden_identifiers if ident and ident in payload]
    if leaked:
        # Do NOT echo the leaked values in the error (that would itself be a leak).
        raise EgressBlocked(
            f"egress blocked: {len(leaked)} raw identifier(s) present in payload")
    return payload
