"""Offline, synthetic-data tests for dormant member address cleanup."""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import somang_member_privacy as privacy


FLAGS = {
    "SOMANG_ENABLE_ADDRESS_PURGE": "1",
    "SOMANG_ADDRESS_PURGE_PRIVACY_APPROVED": "1",
}


class MemberAddressCleanupTests(unittest.TestCase):
    def test_disabled_by_default_and_one_flag_only(self):
        for env in ({}, {"SOMANG_ENABLE_ADDRESS_PURGE": "1"},
                    {"SOMANG_ADDRESS_PURGE_PRIVACY_APPROVED": "1"}):
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    privacy.purge_deleted_member_saved_addresses(7)

    def _mock_db(self, status):
        cursor = MagicMock()
        cursor.fetchone.return_value = (status,) if status is not None else None
        cursor.rowcount = 2
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        module = types.ModuleType("somang_member_store")
        module.connect = lambda: conn
        return cursor, module

    def test_active_pending_and_missing_member_never_deleted(self):
        with patch.dict(os.environ, FLAGS, clear=True):
            for status in ("active", "pending", "suspended", None):
                cursor, module = self._mock_db(status)
                with patch.dict(sys.modules, {"somang_member_store": module}):
                    with self.assertRaises(PermissionError):
                        privacy.purge_deleted_member_saved_addresses(7)
                self.assertEqual(cursor.execute.call_count, 1)
                self.assertIn("FOR UPDATE", cursor.execute.call_args.args[0])

    def test_deleted_member_address_cleanup_is_scoped(self):
        cursor, module = self._mock_db("deleted")
        with patch.dict(os.environ, FLAGS, clear=True):
            with patch.dict(sys.modules, {"somang_member_store": module}):
                self.assertEqual(privacy.purge_deleted_member_saved_addresses(7), 2)
        self.assertEqual(cursor.execute.call_count, 2)
        sql, params = cursor.execute.call_args.args
        self.assertEqual(sql, "DELETE FROM somang_shipping_addresses WHERE member_id=%s")
        self.assertEqual(params, (7,))
        self.assertNotIn("somang_orders", sql)

    def test_invalid_member_id_rejected_without_database(self):
        with patch.dict(os.environ, FLAGS, clear=True):
            for value in (None, 0, -1, True, "7"):
                with self.assertRaises(ValueError):
                    privacy.purge_deleted_member_saved_addresses(value)


if __name__ == "__main__":
    unittest.main()
