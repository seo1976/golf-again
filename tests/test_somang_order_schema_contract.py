"""Offline contract checks for Somang's draft PostgreSQL order schema.

Run: python -m unittest discover -s tests -p 'test_somang_order_schema_contract.py'
No database connection, network calls, real personal data or payments.
"""
from pathlib import Path
import re
import unittest

SCHEMA = (Path(__file__).resolve().parents[1] / "somang_order_schema.sql").read_text(encoding="utf-8")


class OrderSchemaContractTests(unittest.TestCase):
    def test_three_distinct_tables(self):
        for table in ("somang_shipping_addresses", "somang_orders", "somang_order_items"):
            self.assertRegex(SCHEMA, rf"CREATE TABLE IF NOT EXISTS {table}\\s*\\(")

    def test_order_and_item_amount_constraints(self):
        for rule in (
            "payable_total_krw=merchandise_total_krw+shipping_fee_krw",
            "line_total_krw=unit_price_krw*quantity",
            "quantity>0",
            "shipping_fee_krw>=0",
        ):
            self.assertIn(rule, SCHEMA)

    def test_member_and_order_references(self):
        self.assertGreaterEqual(SCHEMA.count("REFERENCES members(id) ON DELETE SET NULL"), 2)
        self.assertIn("REFERENCES somang_orders(id) ON DELETE RESTRICT", SCHEMA)

    def test_only_one_active_default_address_per_member(self):
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS somang_shipping_addresses_one_default", SCHEMA)
        self.assertIn("WHERE is_default AND deleted_at IS NULL AND member_id IS NOT NULL", SCHEMA)

    def test_lifecycle_and_shipping_fields(self):
        for field in ("order_status", "payment_status", "shipping_status",
                      "courier_name", "tracking_number", "shipped_at", "delivered_at"):
            self.assertRegex(SCHEMA, rf"\\b{field}\\b")

    def test_schema_does_not_enable_payments(self):
        self.assertNotIn("CREATE TRIGGER", SCHEMA)
        self.assertNotIn("INSERT INTO", SCHEMA)


if __name__ == "__main__":
    unittest.main()
