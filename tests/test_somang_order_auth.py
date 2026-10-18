"""Offline session boundary checks; fake accounts only, no DB access."""
import unittest
from unittest.mock import patch
import somang_order_auth as auth


class MemberSessionBoundaryTests(unittest.TestCase):
    def test_demo_and_untrusted_sessions_are_denied(self):
        for session in ({}, {"demo_member": True},
                        {"member_id": 7},
                        {"somang_auth_kind": "demo", "somang_auth_member_id": 7},
                        {"somang_auth_kind": "persistent_member", "somang_auth_member_id": "7"}):
            with self.assertRaises((PermissionError, ValueError)):
                auth.member_id_from_verified_session(session, lambda _: ("active", "verified"))

    def test_inactive_or_unverified_account_denied(self):
        session = {"somang_auth_kind": "persistent_member", "somang_auth_member_id": 7}
        for status in (("pending", "verified"), ("suspended", "verified"),
                       ("deleted", "verified"), ("active", None)):
            with self.assertRaises(PermissionError):
                auth.member_id_from_verified_session(session, lambda _: status)

    def test_valid_account_passes_verified_member_id(self):
        session = {"somang_auth_kind": "persistent_member", "somang_auth_member_id": 7}
        with patch("somang_order_store.list_member_orders", return_value=[("FAKE",)]) as read:
            self.assertEqual(auth.list_orders_for_session(session, lambda _: ("active", "verified"), 5),
                             [("FAKE",)])
            read.assert_called_once_with(7, limit=5)
        with patch("somang_order_store.get_member_order_items", return_value=[("FAKE PRODUCT",)]) as read:
            self.assertEqual(auth.get_order_items_for_session(
                session, lambda _: ("active", "verified"), "FAKE-001"), [("FAKE PRODUCT",)])
            read.assert_called_once_with(7, "FAKE-001")

    def test_rejected_session_never_queries_orders(self):
        with patch("somang_order_store.list_member_orders") as read:
            with self.assertRaises(PermissionError):
                auth.list_orders_for_session({"demo_member": True}, lambda _: ("active", "verified"))
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
