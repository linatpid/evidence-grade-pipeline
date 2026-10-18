"""
The provenance spine: Source -> Document -> Page -> Passage -> Finding.

This is the data model Verdictum kept probing: every analytical claim must be
resolvable to an exact source location, and that linkage must survive the whole
lifecycle. Each level carries:
  - a content-addressable ``id`` (see identity.py),
  - a foreign key to its parent,
  - the source content hash,
  - location metadata (page number, character offsets, bbox where available).

Findings never carry loose text. They reference passage ids and a claim_type,
so "what is this conclusion based on?" is always answerable by construction.

The optional PROV-style fields (generated_by / agent / derived_from) follow the
W3C PROV model so the lineage is queryable and standards-shaped rather than an
ad-hoc log.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from .identity import content_id, finding_id, hash_bytes, canonicalize_text


class ClaimType(str, Enum):
    """How well-supported an analytical statement is.

    Grounded in attribution research (AIS / RAGAS faithfulness): we do not
    collapse these. A verbatim quote is not the same as a model inference, and
    neither is the same as an unsupported assertion.
    """
    EVIDENCE = "evidence"        # exact span verified against the source
    INFERENCE = "inference"      # entailed/supported but not verbatim
    UNSUPPORTED = "unsupported"  # neither — must be flagged, never surfaced as fact
    OPEN_QUESTION = "open_question"  # explicitly unresolved


@dataclass(frozen=True)
class Source:
    """An original input artifact, retained immutably (content hash of bytes)."""
    content_hash: str
    filename: str
    media_type: str
    byte_len: int
    container_id: Optional[str] = None  # parent archive, if extracted from one

    @property
    def id(self) -> str:
        return content_id("source", self.content_hash, self.filename)

    @classmethod
    def from_bytes(cls, data: bytes, filename: str, media_type: str,
                   container_id: Optional[str] = None) -> "Source":
        return cls(hash_bytes(data), filename, media_type, len(data), container_id)


@dataclass(frozen=True)
class Page:
    """A page within a source, with retained OCR confidence where applicable."""
    source_id: str
    page_number: int
    text: str
    is_ocr: bool = False
    ocr_confidence: Optional[float] = None  # 0..1, retained through the chain

    @property
    def id(self) -> str:
        return content_id("page", self.source_id, str(self.page_number),
                          canonicalize_text(self.text))


@dataclass(frozen=True)
class Passage:
    """A located span of text. Offsets are into the *page* canonical text."""
    page_id: str
    source_id: str
    page_number: int
    start_offset: int
    end_offset: int
    text: str
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1) for PDFs, if available

    @property
    def id(self) -> str:
        return content_id("passage", self.page_id,
                          f"{self.start_offset}:{self.end_offset}",
                          canonicalize_text(self.text))


@dataclass(frozen=True)
class Finding:
    """An analytical statement bound to the evidence that produced it."""
    claim: str
    claim_type: ClaimType
    passage_ids: tuple           # the exact passages this rests on
    rule: str                    # which analysis produced it
    model_version: str           # which model/version (or "deterministic")
    quote: Optional[str] = None  # the verbatim quote, when claim_type == EVIDENCE
    note: Optional[str] = None

    @property
    def id(self) -> str:
        # Derived from the first supporting passage + rule + model version.
        anchor = self.passage_ids[0] if self.passage_ids else ""
        return finding_id(anchor, self.rule, self.model_version)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["claim_type"] = self.claim_type.value
        d["id"] = self.id
        return d
