"""
Tenant-scoped passage retrieval.

Covers the "retrieval" capability Tom asked about, and closes the leak the
research flagged: retrieval is filtered by the active tenant BEFORE scoring, so
another firm's passages are never even candidates (no post-filtering of a shared
index). Scoring is a small, transparent TF-IDF-lite over passages — deterministic
and inspectable, not a black box.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .model import Passage
from .tenancy import require_tenant

_WORD = re.compile(r"[\w']+", re.UNICODE)


def _tokens(text: str) -> list:
    return _WORD.findall(text.lower())


@dataclass
class PassageIndex:
    """An inverted-index-backed passage store, scoped per tenant.

    Every passage is stamped with the tenant that indexed it. Queries derive the
    tenant from the active context (never from a caller argument), so a query
    cannot reach across firms.
    """
    _by_tenant: dict = field(default_factory=dict)   # tenant -> list[(Passage, Counter)]
    _df: dict = field(default_factory=dict)          # tenant -> {term: doc_freq}

    def add(self, passage: Passage) -> None:
        tid = require_tenant()
        toks = _tokens(passage.text)
        tf = Counter(toks)
        self._by_tenant.setdefault(tid, []).append((passage, tf))
        df = self._df.setdefault(tid, Counter())
        for term in set(toks):
            df[term] += 1

    def search(self, query: str, top_k: int = 5) -> list:
        """Return up to top_k (passage, score) for the ACTIVE tenant only."""
        tid = require_tenant()
        docs = self._by_tenant.get(tid, [])
        if not docs:
            return []
        n = len(docs)
        df = self._df.get(tid, {})
        q_terms = set(_tokens(query))
        scored = []
        for passage, tf in docs:
            score = 0.0
            for term in q_terms:
                if term in tf:
                    idf = math.log((n + 1) / (df.get(term, 0) + 1)) + 1.0
                    score += tf[term] * idf
            if score > 0:
                scored.append((passage, round(score, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
