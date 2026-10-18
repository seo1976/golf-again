"""Smoke tests for the independent Somang pharmacy preview account flow."""
import os
import re
import unittest

os.environ.pop("SOMANG_ENABLE_DEMO_REGISTRATION", None)
from somang_preview import app


class DemoMemberTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def token(self):
        self.client.get("/account")
        with self.client.session_transaction() as sess:
            return sess["csrf"]

    def test_demo_registration_rename_and_delete(self):
        token = self.token()
        response = self.client.post("/demo/register", data={
            "csrf": token, "nickname": "테스트손님"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("테스트손님".encode(), response.data)

        response = self.client.post("/demo/rename", data={
            "csrf": token, "nickname": "새별명"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("새별명".encode(), response.data)

        response = self.client.post("/demo/delete", data={
            "csrf": token
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn("demo_member", sess)
            self.assertNotIn("demo_nickname", sess)

    def test_rejects_invalid_nickname_and_missing_csrf(self):
        token = self.token()
        self.assertEqual(self.client.post("/demo/register", data={
            "csrf": token, "nickname": "!"
        }).status_code, 400)
        self.assertEqual(self.client.post("/demo/register", data={
            "nickname": "테스트"
        }).status_code, 400)
        self.assertEqual(self.client.post("/demo/rename", data={
            "csrf": token, "nickname": "테스트"
        }).status_code, 403)

    def test_real_registration_disabled(self):
        token = self.token()
        response = self.client.post("/register", data={"csrf": token})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
