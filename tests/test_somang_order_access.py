"""Fail-closed tests for dormant member order queries. No real DB or PII."""
import os
import unittest
import sys
import types
from unittest.mock import patch, MagicMock
import somang_order_store as store


class OrderAccessTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                store.list_member_orders(1)
            with self.assertRaises(RuntimeError):
                store.get_member_order_items(1, "FAKE-001")

    def test_both_flags_required(self):
        for env in ({"SOMANG_ENABLE_ORDER_READS": "1"},
                    {"SOMANG_ORDER_PRIVACY_APPROVED": "1"}):
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    store.list_member_orders(1)

    def test_invalid_member_id_and_limit(self):
        with patch.dict(os.environ, {"SOMANG_ENABLE_ORDER_READS": "1",
                                     "SOMANG_ORDER_PRIVACY_APPROVED": "1"}):
            for bad in (None, True, False, 0, -1, "1"):
                with self.assertRaises(ValueError):
                    store.list_member_orders(bad)
            for bad in (0, 51, True, "10"):
                with self.assertRaises(ValueError):
                    store.list_member_orders(1, bad)
            for bad in ("", "X" * 41, None):
                with self.assertRaises(ValueError):
                    store.get_member_order_items(1, bad)

    def test_order_queries_use_owner_scope_and_bound_parameters(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("FAKE-001",)]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        with patch.dict(os.environ, {"SOMANG_ENABLE_ORDER_READS": "1",
                                     "SOMANG_ORDER_PRIVACY_APPROVED": "1"}):
            fake_store = types.ModuleType("somang_member_store")
            fake_store.connect = lambda: conn
            with patch.dict(sys.modules, {"somang_member_store": fake_store}):
                self.assertEqual(store.list_member_orders(42, 5), [("FAKE-001",)])
                sql, args = cursor.execute.call_args.args
                self.assertIn("o.member_id=%s", sql)
                self.assertIn("m.status='active'", sql)
                self.assertIn("m.email_verified_at IS NOT NULL", sql)
                self.assertEqual(args, (42, 5))
                self.assertEqual(store.get_member_order_items(42, "FAKE-001"), [("FAKE-001",)])
                sql, args = cursor.execute.call_args.args
                self.assertIn("o.member_id=%s AND o.order_number=%s", sql)
                self.assertIn("m.status='active'", sql)
                self.assertEqual(args, (42, "FAKE-001"))


if __name__ == "__main__":
    unittest.main()
