"""
Tenant isolation — "prevent data from one client appearing in another client's
results" (Verdictum requirement + section 6).

This is an in-memory model of the defence-in-depth pattern the research points to
for a legal SaaS where leakage is unacceptable:

  - A tenant context must be ACTIVE for any data access. No context => deny
    (fail-closed). This mirrors PostgreSQL RLS where, with FORCE ROW LEVEL
    SECURITY and a non-owner role, an absent/invalid tenant context returns no
    rows rather than all rows.
  - Every stored record is stamped with its owning tenant at WRITE time, and the
    store refuses to write a record stamped for a different tenant than the active
    context (the RLS WITH CHECK property).
  - Reads are PRE-FILTERED by the active tenant inside the store — never
    post-filtered by a caller-supplied tag (the research flags post-filtering,
    especially in vector/ANN search, as a real leak vector).
  - Retrieval, not just primary reads, goes through the same gate, so a search
    cannot surface another tenant's passages.

The accompanying negative tests (tests/test_tenant_isolation.py) deliberately
attempt cross-tenant access and assert it fails closed. Those tests are intended
to be a release-blocking CI gate: a single leaked record is a critical failure.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Optional, Iterator

# The active tenant for the current logical request. Defaults to None so that
# "forgot to set the tenant" fails closed rather than exposing everything.
_active_tenant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "active_tenant", default=None)


class TenantIsolationError(Exception):
    """Raised on any attempt to read/write across the tenant boundary."""


class NoTenantContext(TenantIsolationError):
    """Raised when data is accessed with no active tenant context."""


class tenant_context:
    """Context manager establishing the active tenant for a block of work."""
    def __init__(self, tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        self._tenant_id = tenant_id
        self._token = None

    def __enter__(self) -> str:
        self._token = _active_tenant.set(self._tenant_id)
        return self._tenant_id

    def __exit__(self, *exc) -> None:
        _active_tenant.reset(self._token)


def require_tenant() -> str:
    tid = _active_tenant.get()
    if tid is None:
        raise NoTenantContext("no active tenant context; refusing data access")
    return tid


@dataclass
class _Row:
    tenant_id: str
    key: str
    value: object
    searchable: str = ""  # text used by the retrieval index


@dataclass
class TenantStore:
    """A minimal tenant-scoped record store with a built-in retrieval index.

    All access methods derive the tenant from the active context; none accept a
    caller-supplied tenant id, so a caller cannot ask for another tenant's data.
    """
    _rows: dict = field(default_factory=dict)  # (tenant_id, key) -> _Row

    def put(self, key: str, value: object, searchable: str = "") -> None:
        tid = require_tenant()
        # WITH CHECK equivalent: you may only write rows for your active tenant.
        self._rows[(tid, key)] = _Row(tid, key, value, searchable)

    def get(self, key: str) -> object:
        tid = require_tenant()
        row = self._rows.get((tid, key))
        if row is None:
            # Either it doesn't exist or it belongs to another tenant. Either way,
            # from this context it does not exist. No cross-tenant disclosure.
            raise KeyError(key)
        return row.value

    def list_keys(self) -> list:
        tid = require_tenant()
        return [k for (t, k) in self._rows if t == tid]

    def search(self, term: str) -> list:
        """Retrieval is PRE-FILTERED by tenant inside the store.

        We filter by tenant BEFORE matching, so another tenant's rows are never
        even candidates — the fix for the ANN "post-filter leak" the research warns
        about.
        """
        tid = require_tenant()
        term_c = term.lower()
        return [row.value for (t, _), row in self._rows.items()
                if t == tid and term_c in row.searchable.lower()]

    # For tests/diagnostics only — NOT reachable from tenant-scoped request paths.
    def _raw_count(self) -> int:
        return len(self._rows)
