"""Run: python -m unittest discover -s tests -p 'test_somang_member_store.py'"""
import unittest
from unittest.mock import patch
import somang_member_store as store


class MemberStoreTests(unittest.TestCase):
    def test_normalizes_email(self):
        self.assertEqual(store.normalize_email("  Test@Example.COM "), "test@example.com")

    def test_rejects_invalid_email(self):
        for value in ("", "bad", "a@@example.com", "bad address@example.com", "a@" + "b" * 255 + ".com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                store.normalize_email(value)

    def test_connection_is_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(store.configured())
            with self.assertRaises(RuntimeError):
                store.connect()

    def test_short_password_does_not_connect(self):
        with patch.object(store, "connect", side_effect=AssertionError("DB should not be called")):
            with self.assertRaises(ValueError):
                store.create_pending_member("a@example.com", "short")
            with self.assertRaises(ValueError):
                store.reset_password_with_token("token", "short")

    def test_invalid_purpose_does_not_connect(self):
        with patch.object(store, "connect", side_effect=AssertionError("DB should not be called")):
            with self.assertRaises(ValueError):
                store.issue_email_token(1, "unknown")
            with self.assertRaises(ValueError):
                store.consume_email_token("token", "unknown")


if __name__ == "__main__":
    unittest.main()
