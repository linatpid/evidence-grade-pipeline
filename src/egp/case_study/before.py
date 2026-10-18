"""
BEFORE — the inherited document-batch processor, exactly as found.

It normalises a batch of raw page records (as a scanned/exported batch would
arrive) into clean pages. On clean input it works and its happy-path test passes.
But under one specific failure condition it loses data *silently* and still
reports success — the exact failure mode an evidence-grade system must not have.

The defect is intentionally representative of real legacy code, not a strawman:
a per-item `try/except` that swallows any error and moves on, plus no
reconciliation between how many records came in and how many came out.
"""
from __future__ import annotations


def normalise_page(raw: dict) -> dict:
    """Normalise one raw record. Raises on a malformed record."""
    # A real malformed record: missing text, or text that isn't a string
    # (e.g. a corrupt cell, a None from a failed OCR hand-off, a partial export).
    return {"page": raw["page"], "text": raw["text"].strip()}


def process_batch(records: list) -> list:
    """Return the normalised pages.

    THE DEFECT: a malformed record raises inside ``normalise_page``; the bare
    ``except: continue`` drops it and the loop carries on. The caller receives a
    shorter list with no error, no flag, and no count — a run that "succeeded"
    while silently discarding evidence.
    """
    out = []
    for r in records:
        try:
            out.append(normalise_page(r))
        except Exception:
            continue  # <-- silent data loss: dropped and never reported
    return out
