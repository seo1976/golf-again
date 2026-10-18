"""One-time member schema initialization. Run in a trusted Render shell only.

Usage: python somang_member_migrate.py
Requires SOMANG_MEMBERS_DATABASE_URL. Does not activate public signup.
"""
from pathlib import Path
from somang_member_store import connect


def main():
    sql = Path(__file__).with_name("somang_member_schema.sql").read_text(encoding="utf-8")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("SELECT to_regclass('public.members')")
            if cur.fetchone()[0] is None:
                raise RuntimeError("Membership table was not created")
    print("Member schema initialized; public registration remains disabled.")


if __name__ == "__main__":
    main()
