"""Owner-scoped Somang order queries, dormant until privacy review.

No Flask routes import or call this module. The preview remains demo-only.
This module deliberately exposes no unrestricted order listing.
"""
import os

def _require_member_id(member_id):
    if isinstance(member_id, bool) or not isinstance(member_id, int) or member_id <= 0:
        raise ValueError("Authenticated member ID required")
    return member_id

def _require_order_reads_enabled():
    if (os.environ.get("SOMANG_ENABLE_ORDER_READS") != "1"
            or os.environ.get("SOMANG_ORDER_PRIVACY_APPROVED") != "1"):
        raise RuntimeError("Member order access is disabled pending privacy review")

def list_member_orders(member_id, limit=20):
    """Only return non-sensitive order summaries belonging to this member.

    The caller MUST derive member_id from a verified server-side login session,
    never a query string, URL parameter or client-submitted form field.
    """
    _require_order_reads_enabled()
    member_id = _require_member_id(member_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Invalid order list limit")
    from somang_member_store import connect
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT o.order_number,o.created_at,o.order_status,"
                "o.payment_status,o.shipping_status,o.payable_total_krw "
                "FROM somang_orders o JOIN members m ON m.id=o.member_id "
                "WHERE o.member_id=%s AND m.status='active' AND m.email_verified_at IS NOT NULL "
                "ORDER BY o.created_at DESC,o.id DESC LIMIT %s",
                (member_id, limit),
            )
            return cur.fetchall()

def get_member_order_items(member_id, order_number):
    """Return only product lines of an order owned by a verified active member."""
    _require_order_reads_enabled()
    member_id = _require_member_id(member_id)
    if not isinstance(order_number, str) or not 1 <= len(order_number) <= 40:
        raise ValueError("Invalid order number")
    from somang_member_store import connect
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.product_name,i.unit_price_krw,i.quantity,i.line_total_krw "
                "FROM somang_order_items i "
                "JOIN somang_orders o ON o.id=i.order_id "
                "JOIN members m ON m.id=o.member_id "
                "WHERE o.member_id=%s AND o.order_number=%s "
                "AND m.status='active' AND m.email_verified_at IS NOT NULL "
                "ORDER BY i.id",
                (member_id, order_number),
            )
            return cur.fetchall()
