"""Disposable PostgreSQL duplicate-submit and stock-race contract test only.

This is NOT production checkout. It verifies the required atomic SQL pattern
using synthetic inventory/idempotency tables that exist only in CI.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import psycopg

DSN = os.environ["SOMANG_CI_DATABASE_URL"]


def connection():
    return psycopg.connect(DSN, connect_timeout=5)


def guarded_setup():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT current_database(),current_user")
            if cur.fetchone() != ("somang_ci", "somang_ci"):
                raise RuntimeError("Only disposable CI database allowed")
            cur.execute("CREATE TABLE ci_stock (product_id BIGINT PRIMARY KEY, available INTEGER NOT NULL CHECK (available >= 0))")
            cur.execute("CREATE TABLE ci_order_requests (request_key TEXT PRIMARY KEY, product_id BIGINT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0))")
            cur.execute("INSERT INTO ci_stock VALUES (101, 1), (102, 2)")


def attempt(key, product_id, quantity, start):
    start.wait(timeout=10)
    with connection() as db:
        with db.cursor() as cur:
            # A unique idempotency key avoids charging/committing a repeated request.
            cur.execute(
                "INSERT INTO ci_order_requests(request_key,product_id,quantity) "
                "VALUES (%s,%s,%s) ON CONFLICT (request_key) DO NOTHING RETURNING request_key",
                (key, product_id, quantity),
            )
            if cur.fetchone() is None:
                return "duplicate"
            # Conditional UPDATE atomically reserves stock. Failed reservation
            # must roll back the request key to allow a later retry.
            cur.execute(
                "UPDATE ci_stock SET available=available-%s "
                "WHERE product_id=%s AND available >= %s RETURNING available",
                (quantity, product_id, quantity),
            )
            if cur.fetchone() is None:
                db.rollback()
                return "out_of_stock"
            return "accepted"


def paired_attempts(first, second):
    start = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, *args, start) for args in (first, second)]
        return sorted(f.result(timeout=20) for f in futures)


def main():
    guarded_setup()
    # Two distinct orders race for the final single item.
    assert paired_attempts(("single-a", 101, 1), ("single-b", 101, 1)) == [
        "accepted", "out_of_stock"
    ]
    # Two retries share the same idempotency key; reserve only once.
    assert paired_attempts(("same-key", 102, 1), ("same-key", 102, 1)) == [
        "accepted", "duplicate"
    ]
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT product_id,available FROM ci_stock ORDER BY product_id")
            assert cur.fetchall() == [(101, 0), (102, 1)]
            cur.execute("SELECT count(*) FROM ci_order_requests")
            assert cur.fetchone()[0] == 2
    print("PASS: stock cannot go negative; duplicate key reserves only once")


if __name__ == "__main__":
    main()
