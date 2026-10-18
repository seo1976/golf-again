"""Server-side membership authorization boundary for future order routes.

Not connected to Flask routes. Demo login/session keys are intentionally rejected.
The eventual login handler must set a separate authenticated membership principal
after checking a real password, email verification, and account status.
"""
from somang_order_store import _require_member_id



def load_current_member_status(member_id):
    """Fetch fresh membership status; never trust cached session status.

    This is dormant until the real authenticated login flow is approved.
    A missing/deleted member is rejected; no email or password is returned.
    """
    member_id = _require_member_id(member_id)
    from somang_member_store import connect
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status,email_verified_at FROM members WHERE id=%s",
                (member_id,),
            )
            row = cur.fetchone()
    return row if row is not None else (None, None)

def member_id_from_verified_session(session_data, load_member_status):
    """Return member ID only for a verified server-issued membership session.

    session_data must come from a cryptographically protected server-side session.
    load_member_status(member_id) must fetch fresh account status from the DB and
    return (status, email_verified_at). No request parameters are trusted.
    """
    if session_data.get("somang_auth_kind") != "persistent_member":
        raise PermissionError("Persistent membership login required")
    member_id = _require_member_id(session_data.get("somang_auth_member_id"))
    status, verified_at = load_member_status(member_id)
    if status != "active" or verified_at is None:
        raise PermissionError("Active verified membership required")
    return member_id


def list_orders_for_session(session_data, load_member_status, limit=20):
    """Deny before DB order query unless session and fresh membership are valid."""
    from somang_order_store import list_member_orders
    member_id = member_id_from_verified_session(session_data, load_member_status)
    return list_member_orders(member_id, limit=limit)


def get_order_items_for_session(session_data, load_member_status, order_number):
    from somang_order_store import get_member_order_items
    member_id = member_id_from_verified_session(session_data, load_member_status)
    return get_member_order_items(member_id, order_number)
