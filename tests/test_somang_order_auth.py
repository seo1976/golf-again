"""Offline session boundary checks; fake accounts only, no DB access."""
import unittest
import sys
import types
from unittest.mock import MagicMock
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

    def test_fresh_member_status_reads_database_each_time(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [("active", "verified"), ("suspended", "verified")]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        fake_store = types.ModuleType("somang_member_store")
        fake_store.connect = lambda: conn
        session = {"somang_auth_kind": "persistent_member", "somang_auth_member_id": 7}
        with patch.dict(sys.modules, {"somang_member_store": fake_store}):
            self.assertEqual(auth.member_id_from_verified_session(
                session, auth.load_current_member_status), 7)
            with self.assertRaises(PermissionError):
                auth.member_id_from_verified_session(session, auth.load_current_member_status)
        self.assertEqual(cursor.execute.call_count, 2)
        sql, params = cursor.execute.call_args.args
        self.assertIn("WHERE id=%s", sql)
        self.assertEqual(params, (7,))

    def test_missing_member_is_rejected(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        fake_store = types.ModuleType("somang_member_store")
        fake_store.connect = lambda: conn
        with patch.dict(sys.modules, {"somang_member_store": fake_store}):
            with self.assertRaises(PermissionError):
                auth.member_id_from_verified_session(
                    {"somang_auth_kind": "persistent_member", "somang_auth_member_id": 7},
                    auth.load_current_member_status)

    def test_rejected_session_never_queries_orders(self):
        with patch("somang_order_store.list_member_orders") as read:
            with self.assertRaises(PermissionError):
                auth.list_orders_for_session({"demo_member": True}, lambda _: ("active", "verified"))
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
