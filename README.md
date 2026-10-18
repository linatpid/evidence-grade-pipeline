# evidence-grade-pipeline

A small, **dependency-free** reference implementation of the engineering
guarantees that matter for evidence-grade document analysis — the kind a legal
platform needs, where every conclusion must trace to a source, nothing may leak
between clients, and the system must stop honestly rather than return a
shallow-but-complete-looking answer.

It is a **public demonstration of patterns on synthetic data** — not a product,
not anyone's proprietary code, and not tied to any specific engagement. The point
is that you can read it, run it, and verify the guarantees in a couple of minutes.

## Run it

Requires only Python 3.9+ (standard library — nothing to install).

```bash
# from the repo root
python -m unittest discover -s tests -v   # 48 tests, all green
python examples/demo.py                    # end-to-end walkthrough
```

## What it demonstrates

| Capability | Module | What's proven (tests) |
|---|---|---|
| **Content-addressable provenance IDs** that survive retries/reprocessing | `src/egp/identity.py` | `test_identity.py` |
| **Provenance spine** Source→Document→Page→Passage→Finding | `src/egp/model.py` | (used throughout) |
| **Ingestion accounting** — every file/page counted, counts reconciled, OCR confidence retained, low-confidence material pages flagged | `src/egp/ingest.py` | `test_ingest_accounting.py` |
| **Fail-closed state model** — true zero vs missing/failed/unverified kept distinct | `src/egp/states.py` | (used throughout) |
| **Run-level execution ledger** — planned vs activated steps, states, retries preserved, cost per attempt, fail-closed release gate | `src/egp/ledger.py` | `test_failclosed_ledger.py` |
| **Citation/quote verification** — exact-span match or flag; evidence vs inference vs unsupported | `src/egp/citations.py` | `test_citation_verification.py` |
| **Tenant isolation** — fail-closed, pre-filtered retrieval, release-blocking negative tests | `src/egp/tenancy.py` | `test_tenant_isolation.py` |
| **Pseudonymisation + egress gate** — keyed consistent pseudonyms, separated mapping, fail-closed boundary before any external model | `src/egp/pseudonymize.py` | `test_pseudonym_egress.py` |

## The design principles it embodies

1. **Provenance is the primary key, not a label.** Identifiers are derived from
   canonicalised content (SHA-256), so the same page reprocessed later keeps the
   same id, and a finding's id is derived from the exact evidence that produced it.
2. **Fail-closed by default** (Saltzer & Schroeder *fail-safe defaults*). Missing
   tenant context denies; a required step that didn't complete blocks release; a
   low-confidence OCR page on material content becomes a remediation item — the
   system never dresses up an incomplete result as finished.
3. **A citation is not proof of support.** Even commercial legal RAG tools still
   hallucinate; so every claim is classified — *evidence* (verbatim-verified),
   *inference* (entailment-verified), or *unsupported* (flagged) — and an
   unverified quote is never carried as fact.
4. **Isolation is enforced, then proven.** The negative tests deliberately attempt
   cross-tenant access and assert it fails closed; they are written to be a
   release-blocking CI gate (a single leaked record is a critical failure).
5. **Nothing identifying leaves the boundary silently.** Pseudonyms are keyed
   (HMAC-SHA-256, not a reversible plain hash), the re-identification map is held
   separately, and an egress gate re-scans every outbound payload and fails closed.

## Honest scope

This is a focused demonstration of *mechanics*, deliberately small:

- Document parsing/OCR themselves are simulated (text in, confidence in) — the
  module boundaries where a real parser/OCR/NER engine plugs in are explicit.
- Entailment ("inference" verification) is an **injected interface**, not a bundled
  model — so the gate stays honest (no model => non-verbatim claims are *unsupported*,
  never optimistically "verified").
- Storage/tenancy is in-memory and models the **PostgreSQL row-level-security +
  FORCE + non-owner-role** pattern rather than running a database.

See `EVIDENCE.md` for the mapping to a real production architecture and the
authoritative sources behind each design choice.

## Layout

```
src/egp/        identity, model, states, ledger, ingest, citations, tenancy, pseudonymize
tests/          48 unittest tests (stdlib; pytest also discovers them)
examples/demo.py  runnable end-to-end walkthrough
EVIDENCE.md     what each part demonstrates + production notes + sources
```
