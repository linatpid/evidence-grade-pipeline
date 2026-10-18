"""
evidence-grade-pipeline (egp)
=============================

A small, dependency-free reference implementation of the engineering guarantees
that matter for evidence-grade document analysis:

  * provenance spine        -> identity.py, model.py
  * ingestion accounting     -> ingest.py
  * fail-closed state model  -> states.py
  * run-level execution ledger -> ledger.py
  * citation/quote verification -> citations.py
  * tenant isolation          -> tenancy.py
  * pseudonymisation + egress gate -> pseudonymize.py

Everything here is stdlib-only and runs on synthetic data. It is a public
demonstration of *patterns*, not a product and not anyone's proprietary code.
See EVIDENCE.txt for how each module maps to the guarantees it demonstrates.
"""
from . import identity, model, states, ledger, ingest, citations, tenancy, pseudonymize  # noqa: F401

__all__ = ["identity", "model", "states", "ledger", "ingest", "citations",
           "tenancy", "pseudonymize"]
__version__ = "0.1.0"
