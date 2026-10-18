"""
Content-addressable stable identity.

Every artifact in an evidence-grade pipeline (a source file, a page, an
extracted passage, a finding) is identified by a cryptographic hash of its
*canonicalised* content, never by a mutable path or a sequence number.

Why this matters (and what Verdictum asked about):
  - The identifier is intrinsic to the content, so it is identical across
    retries, deduplication and reprocessing. Reprocessing the same page
    yields the same page id; a new extraction run is a new *version* linked
    to that same id.
  - Any mutation of the content produces a different id, which makes the
    chain tamper-evident for free (the Git / IPFS Merkle-DAG property).
  - Findings are chained to the evidence that produced them:
        finding_id = H(passage_id + rule + model_version)
    so a finding can always be resolved back to its exact source.

Common mistakes this module deliberately avoids:
  - Hashing non-canonical content (whitespace / encoding drift silently
    breaks deduplication). We canonicalise before hashing.
  - Using random UUIDs as "stable" ids (they do not survive reprocessing).
  - Embedding timestamps or run-order into the hashed payload.
"""
from __future__ import annotations

import hashlib
import unicodedata

# Short, human-readable prefixes make ids self-describing in logs and reports
# without weakening the hash. (Cf. multicodec / self-describing CIDs in IPFS.)
_KIND_PREFIX = {
    "source": "src",
    "document": "doc",
    "page": "pg",
    "passage": "psg",
    "finding": "fnd",
    "run": "run",
    "blob": "blob",
}


def canonicalize_text(text: str) -> str:
    """Normalise text so that cosmetically-identical content hashes identically.

    - Unicode NFC normalisation (so composed/decomposed forms match).
    - Normalise line endings to "\\n".
    - Strip trailing whitespace on each line and collapse a trailing newline.

    We intentionally do NOT lowercase or collapse internal whitespace: in legal
    text those differences can be semantically meaningful, so they must change
    the id. Canonicalisation removes only cosmetic, non-semantic variance.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).rstrip("\n")


def hash_bytes(data: bytes) -> str:
    """Raw SHA-256 of bytes, hex-encoded. Used for original source files."""
    return hashlib.sha256(data).hexdigest()


def content_id(kind: str, *parts: str | bytes) -> str:
    """Derive a stable id for an artifact of ``kind`` from its content parts.

    The parts are joined with a 0x1f separator (ASCII unit separator) so that
    ("a", "bc") and ("ab", "c") cannot collide.
    """
    if kind not in _KIND_PREFIX:
        raise ValueError(f"unknown artifact kind: {kind!r}")
    h = hashlib.sha256()
    for i, part in enumerate(parts):
        if i:
            h.update(b"\x1f")
        if isinstance(part, str):
            part = canonicalize_text(part).encode("utf-8")
        h.update(part)
    return f"{_KIND_PREFIX[kind]}_{h.hexdigest()[:40]}"


def finding_id(passage_id: str, rule: str, model_version: str) -> str:
    """A finding's id is derived from exactly what produced it.

    Same passage + same rule + same model version => same finding id
    (idempotent). Change any input and the id changes, so a finding can never
    be silently re-pointed at different evidence.
    """
    return content_id("finding", passage_id, rule, model_version)
