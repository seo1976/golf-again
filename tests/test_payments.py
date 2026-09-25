import os
import tempfile
import unittest


TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DB.close()
os.environ["DATABASE_PATH"] = TEST_DB.name
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MOCK_ENABLED"] = "1"

import app as store


class PaymentFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = store.app.test_client()
        con = store.db()
        con.executescript("DELETE FROM payment_transactions; DELETE FROM order_items; DELETE FROM orders; DELETE FROM products; DELETE FROM users;")
        con.execute(
            """INSERT INTO products(name,category,price,stock,status,created_at,updated_at)
               VALUES('RUBIE 테스트 오일','천연오일',30000,10,'active',?,?)""",
            (store.now(), store.now()),
        )
        con.commit()
        self.product_id = con.execute("SELECT id FROM products").fetchone()[0]
        con.close()
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf-test"

    def post(self, url, data=None, **kwargs):
        form = {"csrf_token": "csrf-test"}
        form.update(data or {})
        return self.client.post(url, data=form, **kwargs)

    def create_ready_order(self):
        self.post(f"/cart/add/{self.product_id}", {"quantity": "2"})
        response = self.post(
            "/checkout",
            {
                "buyer_name": "테스터",
                "email": "buyer@example.com",
                "phone": "01012345678",
                "postcode": "04700",
                "address1": "서울시 테스트로 1",
                "address2": "101호",
                "memo": "문 앞",
                "privacy_agree": "1",
                "purchase_agree": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        order_no = response.headers["Location"].rsplit("/", 1)[-1]
        return order_no

    def test_order_reserves_stock_and_mock_payment_marks_paid(self):
        order_no = self.create_ready_order()
        con = store.db()
        order = con.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
        stock = con.execute("SELECT stock FROM products WHERE id=?", (self.product_id,)).fetchone()[0]
        con.close()
        self.assertEqual(order["payment_status"], "READY")
        self.assertEqual(order["status"], "결제대기")
        self.assertEqual(stock, 8)

        response = self.post(f"/payments/mock/{order_no}")
        self.assertEqual(response.status_code, 302)
        con = store.db()
        order = con.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
        transactions = con.execute("SELECT COUNT(*) FROM payment_transactions WHERE order_id=?", (order["id"],)).fetchone()[0]
        con.close()
        self.assertEqual(order["payment_status"], "PAID")
        self.assertEqual(order["status"], "결제완료")
        self.assertEqual(transactions, 1)

    def test_failed_payment_releases_stock_and_restores_cart(self):
        order_no = self.create_ready_order()
        response = self.client.get(f"/payments/toss/fail?orderNo={order_no}&code=USER_CANCEL&message=cancel")
        self.assertEqual(response.status_code, 200)
        con = store.db()
        order = con.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
        stock = con.execute("SELECT stock FROM products WHERE id=?", (self.product_id,)).fetchone()[0]
        con.close()
        self.assertEqual(order["payment_status"], "FAILED")
        self.assertEqual(order["inventory_restored"], 1)
        self.assertEqual(stock, 10)
        with self.client.session_transaction() as session:
            self.assertEqual(session["cart"][str(self.product_id)], 2)

    def test_tampered_amount_is_rejected_before_gateway_call(self):
        order_no = self.create_ready_order()
        response = self.client.get(f"/payments/toss/success?paymentKey=p_test&orderId={order_no}&amount=1")
        self.assertEqual(response.status_code, 400)
        con = store.db()
        status = con.execute("SELECT payment_status FROM orders WHERE order_no=?", (order_no,)).fetchone()[0]
        con.close()
        self.assertEqual(status, "READY")

    def test_admin_full_refund_restores_stock(self):
        order_no = self.create_ready_order()
        self.post(f"/payments/mock/{order_no}")
        con = store.db()
        cur = con.execute(
            "INSERT INTO users(email,password_hash,name,phone,role,created_at) VALUES(?,?,?,?,?,?)",
            ("admin@example.com", "unused", "관리자", "01000000000", "admin", store.now()),
        )
        admin_id = cur.lastrowid
        order_id = con.execute("SELECT id FROM orders WHERE order_no=?", (order_no,)).fetchone()[0]
        con.commit(); con.close()
        with self.client.session_transaction() as session:
            session["user_id"] = admin_id
        original_api = store.toss_api
        store.toss_api = lambda *args, **kwargs: {"status": "CANCELED", "cancels": [{"cancelAmount": 60000}]}
        try:
            response = self.post(f"/admin/order/{order_id}/cancel", {"cancel_reason": "테스트 환불"})
        finally:
            store.toss_api = original_api
        self.assertEqual(response.status_code, 302)
        con = store.db()
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        stock = con.execute("SELECT stock FROM products WHERE id=?", (self.product_id,)).fetchone()[0]
        con.close()
        self.assertEqual(order["payment_status"], "CANCELED")
        self.assertEqual(order["status"], "환불완료")
        self.assertEqual(stock, 10)

    def test_post_without_csrf_is_blocked(self):
        response = self.client.post(f"/cart/add/{self.product_id}", data={"quantity": "1"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
