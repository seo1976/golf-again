"""Real two-connection PostgreSQL race test against disposable CI database only.

Never run against production. Synthetic values only. Demonstrates the locking
contract future checkout must follow, not that live checkout is implemented.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg


DSN = os.environ["SOMANG_CI_DATABASE_URL"]


def connect():
    return psycopg.connect(DSN, autocommit=True, connect_timeout=5)


def main():
    # All changes are limited to GitHub's disposable Postgres service.
    with connect() as db:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO members(email,password_hash,status,email_verified_at) "
                "VALUES ('ci-concurrent@example.invalid','fake-hash','active',now()) "
                "RETURNING id"
            )
            member_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO somang_shipping_addresses "
                "(member_id,recipient_name,recipient_phone,postal_code,address_line1) "
                "VALUES (%s,'동시성 가상 수령인','000-0000-0000','00000','가상 주소')",
                (member_id,),
            )

    locked = threading.Event()
    may_commit = threading.Event()
    checkout_started = threading.Event()

    def account_deletion():
        with connect() as db:
            with db.transaction():
                with db.cursor() as cur:
                    cur.execute("SELECT status FROM members WHERE id=%s FOR UPDATE", (member_id,))
                    assert cur.fetchone()[0] == "active"
                    cur.execute(
                        "UPDATE members SET status='deleted',email=%s,deleted_at=now() "
                        "WHERE id=%s",
                        (f"deleted-ci-concurrent-{member_id}@invalid.local", member_id),
                    )
                    cur.execute(
                        "DELETE FROM somang_shipping_addresses WHERE member_id=%s",
                        (member_id,),
                    )
                    locked.set()
                    if not may_commit.wait(timeout=15):
                        raise TimeoutError("No checkout lock wait observed")
        return True

    def checkout_attempt():
        if not locked.wait(timeout=10):
            raise TimeoutError("Deletion did not acquire lock")
        with connect() as db:
            with db.cursor() as cur:
                cur.execute("SET application_name = 'somang-race-checkout'")
                cur.execute("SELECT pg_backend_pid()")
                backend_pid = cur.fetchone()[0]
            checkout_started.set()
            with db.transaction():
                with db.cursor() as cur:
                    # Required contract: acquire the SAME member row lock before
                    # checking status or inserting an order.
                    cur.execute(
                        "SELECT status,email_verified_at FROM members WHERE id=%s FOR UPDATE",
                        (member_id,),
                    )
                    row = cur.fetchone()
                    if row and row[0] == "active" and row[1] is not None:
                        raise AssertionError("Deleted member incorrectly eligible for checkout")
                    return backend_pid, "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_future = pool.submit(account_deletion)
        checkout_future = pool.submit(checkout_attempt)
        try:
            if not checkout_started.wait(timeout=10):
                raise TimeoutError("Checkout thread not started")
            # Observe the actual PostgreSQL lock wait, not just thread scheduling.
            deadline = time.monotonic() + 10
            waited = False
            with connect() as observer:
                with observer.cursor() as cur:
                    while time.monotonic() < deadline:
                        cur.execute(
                            "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                            "WHERE application_name=%s AND wait_event_type='Lock')",
                            ("somang-race-checkout",),
                        )
                        if cur.fetchone()[0]:
                            waited = True
                            break
                        time.sleep(0.05)
            if not waited:
                raise AssertionError("No concurrent PostgreSQL row lock wait observed")
        finally:
            may_commit.set()
        assert delete_future.result(timeout=10)
        _, outcome = checkout_future.result(timeout=10)
        assert outcome == "denied"

    with connect() as db:
        with db.cursor() as cur:
            cur.execute("SELECT status FROM members WHERE id=%s", (member_id,))
            assert cur.fetchone()[0] == "deleted"
            cur.execute(
                "SELECT count(*) FROM somang_shipping_addresses WHERE member_id=%s",
                (member_id,),
            )
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM somang_orders WHERE member_id=%s", (member_id,))
            assert cur.fetchone()[0] == 0
    print("PASS: checkout blocked on member lock, deletion committed, checkout denied")


if __name__ == "__main__":
    main()
