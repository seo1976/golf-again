"""Persistent member storage for Somang Pharmacy.

This module is NOT activated by the preview. It must be connected, migrated,
and integration-tested before any real customer data is accepted.
"""
import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash


def configured():
    return bool(os.environ.get("SOMANG_MEMBERS_DATABASE_URL"))


def connect():
    url = os.environ.get("SOMANG_MEMBERS_DATABASE_URL")
    if not url:
        raise RuntimeError("Dedicated member database is not configured")
    import psycopg
    return psycopg.connect(url, connect_timeout=8)


def normalize_email(value):
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Invalid email")
    return email


def create_pending_member(email, password):
    """Create an unverified member; never allow login until verified."""
    email = normalize_email(email)
    if not 12 <= len(password) <= 200:
        raise ValueError("Password length must be between 12 and 200")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO members (email,password_hash) VALUES (%s,%s) RETURNING id",
                (email, generate_password_hash(password)),
            )
            return cur.fetchone()[0]


def verify_password(email, password):
    email = normalize_email(email)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,password_hash,status,email_verified_at FROM members WHERE email=%s",
                (email,),
            )
            row = cur.fetchone()
    if not row or row[2] != "active" or row[3] is None:
        return None
    return row[0] if check_password_hash(row[1], password) else None


def issue_email_token(member_id, purpose, minutes=30):
    """Return one-time secret for out-of-band delivery; store only SHA-256 digest."""
    if purpose not in ("verify", "reset"):
        raise ValueError("Unsupported token purpose")
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO member_email_tokens(member_id,purpose,token_digest,expires_at) "
                "VALUES (%s,%s,%s,%s)",
                (member_id, purpose, digest, expires),
            )
    return token


def consume_email_token(token, purpose):
    if purpose not in ("verify", "reset"):
        raise ValueError("Unsupported token purpose")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE member_email_tokens SET consumed_at=now() "
                "WHERE token_digest=%s AND purpose=%s AND consumed_at IS NULL "
                "AND expires_at>now() RETURNING member_id",
                (digest, purpose),
            )
            row = cur.fetchone()
            if row and purpose == "verify":
                cur.execute(
                    "UPDATE members SET email_verified_at=now(),status='active',"
                    "updated_at=now() WHERE id=%s AND status='pending'",
                    (row[0],),
                )
            return row[0] if row else None
