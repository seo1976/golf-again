"""Safe, offline order lifecycle simulation using an in-memory SQLite database.

This tests transactional behavior only. It is NOT a PostgreSQL migration test,
and never connects to a production database or accepts real customer data.
Run: python -m unittest discover -s tests -p 'test_somang_order_lifecycle_offline.py'
"""
import sqlite3
import unittest


def new_test_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE orders (
          id INTEGER PRIMARY KEY, order_number TEXT UNIQUE NOT NULL,
          merchandise_total INTEGER NOT NULL CHECK(merchandise_total >= 0),
          shipping_fee INTEGER NOT NULL CHECK(shipping_fee >= 0),
          payable_total INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','cancelled','confirmed')),
          CHECK(payable_total=merchandise_total+shipping_fee)
        );
        CREATE TABLE order_items (
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
          product_name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
          unit_price INTEGER NOT NULL CHECK(unit_price>=0),
          line_total INTEGER NOT NULL CHECK(line_total=quantity*unit_price)
        );
    """)
    return conn


def save_sample_order(conn, number, items, shipping_fee):
    # Fixed fictional merchandise; no customer details or payment.
    if (not items or shipping_fee < 0 or
            any(qty <= 0 or price < 0 or not name.strip() for name, qty, price in items)):
        raise ValueError("Invalid order")
    total = sum(qty * price for _, qty, price in items)
    with conn:
        cur = conn.execute(
            "INSERT INTO orders(order_number, merchandise_total, shipping_fee, payable_total) VALUES(?,?,?,?)",
            (number, total, shipping_fee, total + shipping_fee),
        )
        for name, qty, price in items:
            conn.execute(
                "INSERT INTO order_items(order_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?)",
                (cur.lastrowid, name, qty, price, qty * price),
            )
    return cur.lastrowid


class OfflineOrderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = new_test_db()

    def tearDown(self):
        self.db.close()

    def test_save_and_read_sample_order(self):
        order_id = save_sample_order(self.db, "SAMPLE-001", [("샘플 보습 크림", 2, 18900)], 3000)
        order = self.db.execute(
            "SELECT merchandise_total, shipping_fee, payable_total, status FROM orders WHERE id=?",
            (order_id,),
        ).fetchone()
        self.assertEqual(order, (37800, 3000, 40800, "pending"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM order_items WHERE order_id=?", (order_id,)).fetchone()[0], 1)

    def test_cancel_sample_order(self):
        order_id = save_sample_order(self.db, "SAMPLE-002", [("샘플 핸드크림", 1, 7900)], 0)
        with self.db:
            self.db.execute("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (order_id,))
        self.assertEqual(self.db.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()[0], "cancelled")

    def test_duplicate_order_number_rejected_without_extra_items(self):
        sample = [("샘플 크림", 1, 18900)]
        save_sample_order(self.db, "SAMPLE-003", sample, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            save_sample_order(self.db, "SAMPLE-003", sample, 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 1)

    def test_invalid_line_item_rolls_back_order(self):
        with self.assertRaises(ValueError):
            save_sample_order(self.db, "SAMPLE-004", [("샘플", 0, 1000)], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)

    def test_total_mismatch_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute(
                    "INSERT INTO orders(order_number,merchandise_total,shipping_fee,payable_total) VALUES(?,?,?,?)",
                    ("SAMPLE-005", 1000, 3000, 1000),
                )


if __name__ == "__main__":
    unittest.main()
