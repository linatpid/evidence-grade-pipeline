# Worked case: inheriting and stabilising a document-batch processor

A concrete, runnable demonstration of diagnosing and stabilising an inherited
defect — the failure → diagnosis → change → testing → result chain, with the code
and tests in this repo so it can be verified rather than taken on trust.

> This is a demonstration on synthetic data, not production code. Its value is
> that you can run it and see exactly how the defect is exposed and fixed.

Code: `src/egp/case_study/before.py`, `src/egp/case_study/after.py`
Tests: `tests/test_case_study.py` (run
`python -m unittest discover -s tests -p "test_case_study.py" -v`)

## 1. The initial failure / limitation

The inherited `process_batch` (see `before.py`) normalises a batch of raw page
records into clean pages. On clean input it works and its happy-path test passes.
But it contains a per-item `try/except` that swallows *any* error and continues,
and it never reconciles how many records came in against how many came out.

Effect: when a malformed record arrives (missing text, a `None` from a failed OCR
hand-off, a partial export), it is **silently dropped**. The caller receives a
shorter list — no error, no flag, no count. A run "succeeds" while discarding
evidence. For a legal/evidence system this is the worst class of bug: invisible
data loss presented as a complete result.

## 2. Diagnosis

Reproduced with a characterisation test (`TestLegacyDefect`): feed a 3-record
batch where one record is malformed; observe 2 records out and **no signal** that
one was lost. Root cause located in two places:
- the bare `except: continue` in `process_batch` — it converts a per-record
  failure into a silent skip;
- the absence of any input-vs-output reconciliation — so the skip is undetectable
  downstream.

## 3. The change implemented

Stabilised in `after.py`, without rewriting the parts that work:
1. **Remove the catch-all**; validate each record explicitly (`normalise_page`
   now raises specific `ValueError`s instead of silently coercing).
2. **Route malformed records to a remediation worklist** with the index and a
   diagnosable reason — never discard them.
3. **Reconcile**: assert every input lands in exactly one of `{pages,
   remediation}`; a count mismatch raises `CountMismatch` as a safety net.
4. **Fail closed**: if anything needs remediation, raise `BatchNotReconciled`
   rather than return a partial result that looks complete. A caller that wants
   to inspect can pass `fail_closed=False` and read the structured `BatchResult`.

## 4. How it was tested

- The **characterisation tests** stay in the suite to document the old failure.
- **Regression tests** (`TestStabilised`) prove: the batch now fails closed on a
  malformed record; every input is accounted for (`reconciles()` holds); the
  malformed record is flagged with its position and reason; clean input is
  unchanged; and even an all-malformed batch loses nothing.
- All run under the repo's zero-dependency suite:
  `python -m unittest discover -s tests -v`.

## 5. The resulting improvement

Before: 3 records in → 2 out, silently, reported as success.
After: nothing is ever dropped; malformed records are flagged for remediation;
the batch cannot be reported as complete while evidence is unaccounted for. The
failure moved from *invisible and trusted* to *visible and blocking* — which is
the whole point of fail-closed, evidence-grade processing.
