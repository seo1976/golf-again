"""Storefront regression checks; run with python -m unittest discover -s tests."""
import unittest
from unittest.mock import patch
from somang_preview import app


class SomangCartFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_product_detail(self):
        r = self.client.get("/shop/product/900001")
        self.assertEqual(r.status_code, 200)
        self.assertIn("18,900".encode(), r.data)

    def test_missing_product(self):
        self.assertEqual(self.client.get("/shop/product/99999999").status_code, 404)

    def test_sorting_and_search(self):
        r = self.client.get("/shop?sort=price_asc&q=%EC%83%B4%ED%91%B8")
        self.assertEqual(r.status_code, 200)
        self.assertIn("두피 케어 샴푸".encode(), r.data)

    def test_cart_quantity_and_total(self):
        with self.client.session_transaction() as sess:
            sess["csrf"] = "testing-token"
        r = self.client.post("/cart/add", data={"csrf":"testing-token","product_id":"900001","quantity":"2"})
        self.assertEqual(r.status_code, 302)
        r = self.client.get("/cart")
        self.assertIn("37,800".encode(), r.data)
        r = self.client.post("/cart/update", data={"csrf":"testing-token","product_id":"900001","quantity":"1"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("18,900".encode(), self.client.get("/cart").data)
        r = self.client.post("/cart/remove", data={"csrf":"testing-token","product_id":"900001"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("장바구니가 비어".encode(), self.client.get("/cart").data)

    def test_reject_invalid_quantity(self):
        with self.client.session_transaction() as sess:
            sess["csrf"] = "testing-token"
        r = self.client.post("/cart/add", data={"csrf":"testing-token","product_id":"900001","quantity":"21"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
