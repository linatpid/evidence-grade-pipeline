"""
AFTER — the stabilised document-batch processor.

Diagnosis (see CASE_STUDY.md): the legacy ``process_batch`` swallowed any
malformed record with a bare ``except: continue`` and never reconciled input
count against output count, so malformed evidence was dropped silently while the
run reported success.

The change, implemented without rewriting the working parts:
  1. remove the catch-all; classify each item explicitly (ok vs malformed);
  2. route malformed items to a remediation list with a reason — never discard;
  3. reconcile: every input must land in exactly one of {pages, remediation};
  4. fail closed — if anything needs remediation, the batch is not reported as a
     clean success; the caller gets a structured, trustworthy result instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class BatchNotReconciled(Exception):
    """Raised when a batch cannot be reported as a clean success."""


class CountMismatch(Exception):
    """Safety net: raised if inputs are not fully accounted for (should never fire)."""


@dataclass
class BatchResult:
    pages: list = field(default_factory=list)
    remediation: list = field(default_factory=list)  # list[(index, reason)]

    @property
    def accounted(self) -> int:
        return len(self.pages) + len(self.remediation)

    def reconciles(self, n_input: int) -> bool:
        return self.accounted == n_input


def normalise_page(raw: dict) -> dict:
    """Normalise one raw record, with explicit validation (no silent coercion)."""
    if "page" not in raw:
        raise ValueError("missing 'page'")
    if "text" not in raw or not isinstance(raw["text"], str):
        raise ValueError("missing or non-string 'text'")
    return {"page": raw["page"], "text": raw["text"].strip()}


def process_batch(records: list, *, fail_closed: bool = True) -> BatchResult:
    """Process a batch, accounting for every record.

    With ``fail_closed=True`` (the default), a batch that produced any remediation
    item raises ``BatchNotReconciled`` rather than returning a partial result that
    looks complete. With ``fail_closed=False`` the caller gets the full
    ``BatchResult`` to inspect, including the remediation worklist.
    """
    result = BatchResult()
    for i, r in enumerate(records):
        try:
            result.pages.append(normalise_page(r))
        except Exception as e:
            result.remediation.append((i, str(e)))  # flagged, not dropped

    # Reconciliation: nothing may vanish. Every input is a page or a remediation item.
    if not result.reconciles(len(records)):
        raise CountMismatch(
            f"expected {len(records)} accounted, got {result.accounted}")

    if fail_closed and result.remediation:
        raise BatchNotReconciled(
            f"{len(result.remediation)} record(s) need remediation; "
            f"batch not reported as complete")
    return result
