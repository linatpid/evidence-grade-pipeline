evidence-grade-pipeline
=======================

A small, dependency-free reference implementation of the engineering guarantees
that matter for evidence-grade document analysis - the kind a legal platform
needs, where every conclusion must trace to a source, nothing may leak between
clients, and the system must stop honestly rather than return a shallow-but-
complete-looking answer.

It is a public demonstration of patterns on synthetic data - not a product, not
anyone's proprietary code, and not tied to any specific engagement. The point is
that you can read it, run it, and verify the guarantees in a couple of minutes.


RUN IT
------
Requires only Python 3.9+ (standard library - nothing to install).

    # from the repo root
    python -m unittest discover -s tests -v   # 54 tests, all green
    python examples/demo.py                    # end-to-end walkthrough

See CASE_STUDY.txt for a worked brownfield-stabilisation example: an inherited
document-batch processor that silently drops records, the characterisation test
that exposes it, the fail-closed fix, and the regression tests that lock it in.


WHAT IT DEMONSTRATES
--------------------
- Content-addressable provenance IDs that survive retries/reprocessing
    module: src/egp/identity.py        tests: test_identity.py
- Provenance spine (Source -> Document -> Page -> Passage -> Finding)
    module: src/egp/model.py           (used throughout)
- Ingestion accounting - every file/page counted, counts reconciled, OCR
  confidence retained, low-confidence material pages flagged
    module: src/egp/ingest.py          tests: test_ingest_accounting.py
- Fail-closed state model - true zero vs missing/failed/unverified kept distinct
    module: src/egp/states.py          (used throughout)
- Run-level execution ledger - planned vs activated steps, states, retries
  preserved, cost per attempt, fail-closed release gate
    module: src/egp/ledger.py          tests: test_failclosed_ledger.py
- Citation/quote verification - exact-span match or flag; evidence vs inference
  vs unsupported
    module: src/egp/citations.py       tests: test_citation_verification.py
- Tenant isolation - fail-closed, pre-filtered retrieval, release-blocking
  negative tests
    module: src/egp/tenancy.py         tests: test_tenant_isolation.py
- Pseudonymisation + egress gate - keyed consistent pseudonyms, separated
  mapping, fail-closed boundary before any external model
    module: src/egp/pseudonymize.py    tests: test_pseudonym_egress.py
- Worked brownfield-stabilisation case (silent data loss -> fail-closed)
    module: src/egp/case_study/        tests: test_case_study.py


THE DESIGN PRINCIPLES IT EMBODIES
---------------------------------
1. Provenance is the primary key, not a label. Identifiers are derived from
   canonicalised content (SHA-256), so the same page reprocessed later keeps the
   same id, and a finding's id is derived from the exact evidence that produced it.
2. Fail-closed by default (Saltzer & Schroeder fail-safe defaults). Missing tenant
   context denies; a required step that didn't complete blocks release; a low-
   confidence OCR page on material content becomes a remediation item - the system
   never dresses up an incomplete result as finished.
3. A citation is not proof of support. Even commercial legal RAG tools still
   hallucinate; so every claim is classified - evidence (verbatim-verified),
   inference (entailment-verified), or unsupported (flagged) - and an unverified
   quote is never carried as fact.
4. Isolation is enforced, then proven. The negative tests deliberately attempt
   cross-tenant access and assert it fails closed; they are written to be a
   release-blocking CI gate (a single leaked record is a critical failure).
5. Nothing identifying leaves the boundary silently. Pseudonyms are keyed
   (HMAC-SHA-256, not a reversible plain hash), the re-identification map is held
   separately, and an egress gate re-scans every outbound payload and fails closed.


HONEST SCOPE
------------
This is a focused demonstration of mechanics, deliberately small:
- Document parsing/OCR themselves are simulated (text in, confidence in) - the
  module boundaries where a real parser/OCR/NER engine plugs in are explicit.
- Entailment ("inference" verification) is an injected interface, not a bundled
  model - so the gate stays honest (no model => non-verbatim claims are
  unsupported, never optimistically "verified").
- Storage/tenancy is in-memory and models the PostgreSQL row-level-security +
  FORCE + non-owner-role pattern rather than running a database.

See EVIDENCE.txt for the mapping to a real production architecture and the
authoritative sources behind each design choice.


LAYOUT
------
    src/egp/          identity, model, states, ledger, ingest, citations,
                      tenancy, pseudonymize, case_study
    tests/            54 unittest tests (stdlib; pytest also discovers them)
    examples/demo.py  runnable end-to-end walkthrough
    CASE_STUDY.txt    worked brownfield-stabilisation example
    EVIDENCE.txt      what each part demonstrates + production notes + sources
