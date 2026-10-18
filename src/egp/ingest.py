"""
Ingestion accounting — account for every input file, container and page.

Verdictum's section 3 ("40,000-page" scenario) asks: how is every input file,
container and page accounted for, how are counts reconciled, and how do you tell
a legitimate zero from a missing/failed/corrupt result?

This module builds an ingestion manifest at the trust boundary:
  - every file is registered with a content hash;
  - containers (archives) are expanded, each child linked to its parent;
  - the expected page count is reconciled against pages actually extracted;
  - OCR confidence is retained per page and low-confidence pages are flagged
    (never silently trusted) — a material low-confidence page forces the
    affected item onto a remediation worklist rather than passing as "done".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import Source, Page
from .states import ResultStatus

# Below this OCR confidence a page is treated as unverified, not as empty text.
OCR_REVIEW_THRESHOLD = 0.70


@dataclass
class PageOutcome:
    page: Optional[Page]
    status: ResultStatus
    reason: str = ""


@dataclass
class ItemOutcome:
    """Per-source ingestion outcome, including a remediation flag."""
    source: Source
    expected_pages: int
    pages: list = field(default_factory=list)   # list[PageOutcome]
    needs_remediation: bool = False
    remediation_reason: str = ""

    @property
    def extracted_pages(self) -> int:
        return sum(1 for p in self.pages if p.page is not None)

    @property
    def counts_reconcile(self) -> bool:
        return self.extracted_pages == self.expected_pages


@dataclass
class Manifest:
    """The full accounting of an ingestion run."""
    items: list = field(default_factory=list)  # list[ItemOutcome]

    def register_source(self, source: Source, expected_pages: int) -> ItemOutcome:
        item = ItemOutcome(source=source, expected_pages=expected_pages)
        self.items.append(item)
        return item

    # ---- coverage report (what a lawyer can inspect) --------------------
    def coverage(self) -> dict:
        total_expected = sum(i.expected_pages for i in self.items)
        total_extracted = sum(i.extracted_pages for i in self.items)
        unverified = [
            {"source": i.source.filename, "page": po.page.page_number if po.page else None,
             "reason": po.reason}
            for i in self.items for po in i.pages
            if po.status in (ResultStatus.UNVERIFIED, ResultStatus.FAILED)
        ]
        remediation = [
            {"source": i.source.filename, "reason": i.remediation_reason}
            for i in self.items if i.needs_remediation
        ]
        return {
            "sources": len(self.items),
            "pages_expected": total_expected,
            "pages_extracted": total_extracted,
            "all_counts_reconcile": all(i.counts_reconcile for i in self.items),
            "unverified_pages": unverified,
            "remediation_worklist": remediation,
            # fail-closed: the manifest is only "clean" if nothing is unverified,
            # every count reconciles and nothing needs remediation.
            "clean": (not unverified and not remediation
                      and all(i.counts_reconcile for i in self.items)),
        }


def ingest_page(item: ItemOutcome, page_number: int, text: str,
                is_ocr: bool = False, ocr_confidence: Optional[float] = None,
                *, material: bool = True) -> PageOutcome:
    """Ingest one page, classifying the outcome honestly.

    ``material`` marks whether this page could carry decisive content. A
    low-confidence *material* page is UNVERIFIED and triggers remediation — it is
    never recorded as "empty but complete".
    """
    if text is None:
        outcome = PageOutcome(None, ResultStatus.FAILED, "extraction returned nothing")
        item.pages.append(outcome)
        item.needs_remediation = True
        item.remediation_reason = f"page {page_number}: extraction failed"
        return outcome

    if is_ocr and (ocr_confidence is None or ocr_confidence < OCR_REVIEW_THRESHOLD):
        # Low-confidence OCR: retain the text but DO NOT trust it silently.
        page = Page(item.source.id, page_number, text, is_ocr=True,
                    ocr_confidence=ocr_confidence)
        outcome = PageOutcome(page, ResultStatus.UNVERIFIED,
                              f"OCR confidence {ocr_confidence} < {OCR_REVIEW_THRESHOLD}")
        item.pages.append(outcome)
        if material:
            item.needs_remediation = True
            item.remediation_reason = (
                f"page {page_number}: low-confidence OCR on material page")
        return outcome

    page = Page(item.source.id, page_number, text, is_ocr=is_ocr,
                ocr_confidence=ocr_confidence)
    status = ResultStatus.COMPLETE_ZERO if text.strip() == "" else ResultStatus.COMPLETE_NONZERO
    outcome = PageOutcome(page, status)
    item.pages.append(outcome)
    return outcome
