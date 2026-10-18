"""
End-to-end demonstration.

Run from the repo root:   python examples/demo.py

It processes a small synthetic "case" belonging to one law firm and shows, in
one connected flow:
  1. ingestion accounting with a low-confidence OCR page forcing remediation,
  2. a coverage report that is NOT "clean" while something is unverified,
  3. tenant-scoped storage + retrieval that cannot see another firm's data,
  4. a verified (exact-quote) finding vs a flagged unsupported claim,
  5. a run-level execution ledger with a fail-closed release gate.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from egp.model import Source, Passage
from egp.ingest import Manifest, ingest_page
from egp.ledger import RunLedger
from egp.states import StepState
from egp.citations import make_verified_finding
from egp.tenancy import TenantStore, tenant_context
from egp.pseudonymize import Pseudonymizer, egress_gate, EgressBlocked
from egp.identity import content_id


def rule(title):
    print("\n" + "=" * 68 + f"\n{title}\n" + "=" * 68)


def main():
    run = RunLedger(run_id=content_id("run", "demo-case", "attempt-1"),
                    case_id="CASE-2026-001", tenant_id="firm-alpha")
    for step, produces in [("ingest", "manifest"), ("isolate", None),
                           ("analyse", "findings"), ("pseudonymise_egress", None)]:
        run.plan(step, produces=produces)

    # --- 1. Ingestion accounting ---------------------------------------
    rule("1. INGESTION ACCOUNTING")
    manifest = Manifest()
    contract = Source.from_bytes(b"Contract dated 2026-03-01 ... fee EUR 10,000.",
                                 "contract.pdf", "application/pdf")
    item = manifest.register_source(contract, expected_pages=2)
    ingest_page(item, 1, "The parties agree the fee is EUR 10,000.", is_ocr=False)
    # A scanned, low-confidence, MATERIAL page -> must not pass silently.
    ingest_page(item, 2, "sign4ture: J. Kov4cs  d4te: 2O26-O3-O1",
                is_ocr=True, ocr_confidence=0.41, material=True)
    cov = manifest.coverage()
    run.record("ingest", StepState.COMPLETED, output_hash=content_id("blob", str(cov)),
               schema_valid=True)
    print(f"pages expected={cov['pages_expected']} extracted={cov['pages_extracted']}")
    print(f"coverage clean? {cov['clean']}  (expected False — page 2 needs review)")
    print(f"remediation worklist: {cov['remediation_worklist']}")

    # --- 2. Tenant isolation -------------------------------------------
    rule("2. TENANT ISOLATION")
    store = TenantStore()
    with tenant_context("firm-alpha"):
        store.put("doc:contract", {"title": "Alpha contract"},
                  searchable="contract fee EUR 10000 Kovacs")
    with tenant_context("firm-beta"):
        store.put("doc:nda", {"title": "Beta NDA"}, searchable="nda confidential")
        # firm-beta searches the SAME store and sees only its own rows.
        hits = store.search("contract")
        print(f"firm-beta search('contract') -> {hits}  (expected [] — alpha's row is invisible)")
    with tenant_context("firm-alpha"):
        print(f"firm-alpha search('contract') -> {store.search('contract')}")

    # --- 3. Citation verification --------------------------------------
    rule("3. CITATION / QUOTE VERIFICATION")
    page_text = "The parties agree the fee is EUR 10,000."
    page_id = content_id("page", contract.id, "1", page_text)
    passage = Passage(page_id, contract.id, 1, 0, len(page_text), page_text)
    good = make_verified_finding(
        "The agreed fee is EUR 10,000.", [passage], rule="fee_extraction",
        model_version="deterministic", quote="the fee is EUR 10,000")
    bad = make_verified_finding(
        "The agreed fee is EUR 50,000.", [passage], rule="fee_extraction",
        model_version="deterministic", quote="the fee is EUR 50,000")
    print(f"exact quote present  -> {good.claim_type.value}  ({good.note})")
    print(f"quote NOT in source  -> {bad.claim_type.value}  ({bad.note})")
    run.record("analyse", StepState.COMPLETED,
               output_hash=content_id("blob", good.id + bad.id), schema_valid=True)

    # --- 4. Pseudonymisation + egress gate -----------------------------
    rule("4. PSEUDONYMISATION + EGRESS GATE")
    pz = Pseudonymizer.with_key(b"0" * 32, label="PERSON")
    raw = "J. Kovacs signed on behalf of J. Kovacs & Partners."
    masked = pz.pseudonymize_text(raw, identifiers=["J. Kovacs"])
    print(f"raw    : {raw}")
    print(f"masked : {masked}  (same entity -> same pseudonym)")
    try:
        egress_gate(raw, forbidden_identifiers=["J. Kovacs"])  # raw must be blocked
    except EgressBlocked as e:
        print(f"egress of RAW text   -> BLOCKED ({e})")
    egress_gate(masked, forbidden_identifiers=["J. Kovacs"])   # masked passes
    print("egress of MASKED text -> allowed")
    run.record("pseudonymise_egress", StepState.COMPLETED,
               output_hash=content_id("blob", masked), schema_valid=True)

    # --- 5. Fail-closed release gate -----------------------------------
    rule("5. RUN LEDGER + FAIL-CLOSED RELEASE GATE")
    # 'isolate' was planned but never completed -> the run must NOT be releasable.
    print("ledger summary:")
    for k, v in run.summary().items():
        print(f"  {k}: {v}")
    print(f"\ntotal model/processing cost recorded: ${run.total_cost_usd()}")
    print("\nThe run is correctly BLOCKED: a required step did not complete, so the"
          "\nsystem refuses to present the result as finished. That is the point.")


if __name__ == "__main__":
    main()
