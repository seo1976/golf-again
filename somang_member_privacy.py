"""Dormant, explicitly gated cleanup of saved addresses after account soft deletion.

NOT called from the preview, member deletion endpoint, or any scheduled job.
Requires a separate privacy approval before any live use. Order snapshots are
not modified; their legal retention and deletion need a separate approved policy.
"""
import os


def purge_deleted_member_saved_addresses(member_id):
    """Delete saved address-book entries ONLY for an already deleted member.

    Returns the number of deleted addresses. The member row is locked to
    prevent a concurrent status change. Uses bound parameters and one
    transaction. Does not touch historical orders or their delivery snapshots.
    """
    if (os.environ.get("SOMANG_ENABLE_ADDRESS_PURGE") != "1"
            or os.environ.get("SOMANG_ADDRESS_PURGE_PRIVACY_APPROVED") != "1"):
        raise RuntimeError("Address purge is disabled pending privacy approval")
    if isinstance(member_id, bool) or not isinstance(member_id, int) or member_id <= 0:
        raise ValueError("Valid member ID required")
    from somang_member_store import connect
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM members WHERE id=%s FOR UPDATE", (member_id,))
            row = cur.fetchone()
            if row is None or row[0] != "deleted":
                raise PermissionError("Only already deleted members are eligible")
            cur.execute(
                "DELETE FROM somang_shipping_addresses WHERE member_id=%s",
                (member_id,),
            )
            return cur.rowcount
