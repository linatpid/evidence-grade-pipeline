"""
RELEASE-BLOCKING negative tests for tenant isolation (section 6).

Per OWASP authorization-regression guidance, a single leaked record is a critical
failure, and these tests are meant to gate merges. Each test deliberately ATTEMPTS
a cross-tenant access and asserts it fails closed.
"""
import unittest

import _bootstrap  # noqa: F401
from egp.tenancy import (TenantStore, tenant_context, require_tenant,
                         NoTenantContext, TenantIsolationError)


class TestTenantIsolationNegative(unittest.TestCase):
    def setUp(self):
        self.store = TenantStore()
        with tenant_context("firm-alpha"):
            self.store.put("case:1", {"secret": "alpha privileged strategy"},
                           searchable="alpha privileged strategy budapest")
        with tenant_context("firm-beta"):
            self.store.put("case:1", {"secret": "beta privileged strategy"},
                           searchable="beta privileged strategy vienna")

    # --- the attacks that must all fail closed -------------------------
    def test_beta_cannot_read_alpha_by_same_key(self):
        # Same key "case:1" exists for both tenants; beta must get ITS row only.
        with tenant_context("firm-beta"):
            self.assertEqual(self.store.get("case:1")["secret"],
                             "beta privileged strategy")

    def test_beta_cannot_see_alpha_in_search(self):
        with tenant_context("firm-beta"):
            hits = self.store.search("privileged")
            self.assertTrue(all(h["secret"].startswith("beta") for h in hits))
            self.assertNotIn({"secret": "alpha privileged strategy"}, hits)

    def test_beta_cannot_see_alpha_only_term(self):
        # "budapest" only tags alpha's row -> beta's search must return nothing.
        with tenant_context("firm-beta"):
            self.assertEqual(self.store.search("budapest"), [])

    def test_list_keys_is_tenant_scoped(self):
        with tenant_context("firm-alpha"):
            self.assertEqual(self.store.list_keys(), ["case:1"])
        # both tenants have a "case:1", but neither sees two rows.
        with tenant_context("firm-beta"):
            self.assertEqual(self.store.list_keys(), ["case:1"])

    def test_access_with_no_tenant_context_is_denied(self):
        # The crucial fail-closed property: no context => deny, not "return all".
        with self.assertRaises(NoTenantContext):
            self.store.get("case:1")
        with self.assertRaises(NoTenantContext):
            self.store.search("privileged")
        with self.assertRaises(NoTenantContext):
            require_tenant()

    def test_cannot_write_without_context(self):
        with self.assertRaises(TenantIsolationError):
            self.store.put("x", {"v": 1})

    def test_context_does_not_leak_across_blocks(self):
        with tenant_context("firm-alpha"):
            pass
        # After the block, there is no ambient tenant -> access denied again.
        with self.assertRaises(NoTenantContext):
            self.store.get("case:1")

    def test_empty_tenant_id_rejected(self):
        with self.assertRaises(ValueError):
            tenant_context("")


if __name__ == "__main__":
    unittest.main()
