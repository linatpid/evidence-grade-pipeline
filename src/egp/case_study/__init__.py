"""
A worked brownfield-stabilisation case.

This package shows, end to end, how an inherited defect is diagnosed and fixed:
  - before.py : the legacy document-batch processor exactly as "found", with a
                latent defect that loses data silently while reporting success;
  - after.py  : the stabilised version, fail-closed with reconciliation.

The accompanying tests (tests/test_case_study.py) first EXPOSE the defect with a
characterisation test, then prove the fix and guard it against regression. See
CASE_STUDY.md at the repo root for the written failure -> diagnosis -> change ->
testing -> result account.

This is a demonstration on synthetic data, not production code.
"""
from . import before, after  # noqa: F401

__all__ = ["before", "after"]
