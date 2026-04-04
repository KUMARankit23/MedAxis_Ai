"""
Audit logger for compliance and traceability.

Gap fixed: supports before/after state snapshots on every mutation,
matching the document requirement for full mutation traceability.
Every critical action (login, stock update, billing) is recorded.
"""
import logging
import json
from datetime import datetime, timezone

audit_log = logging.getLogger("audit")
audit_log.setLevel(logging.INFO)

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
audit_log.addHandler(_handler)


def log_action(
    actor_id: str,
    actor_role: str,
    action: str,
    resource: str,
    details: dict = None,
    status: str = "SUCCESS",
    before: dict = None,
    after: dict = None,
):
    """
    Write a structured audit log entry with optional before/after snapshots.

    Args:
        actor_id:   user ID performing the action
        actor_role: role of the actor
        action:     what was done (LOGIN, STOCK_UPDATE, INVOICE_CREATE, etc.)
        resource:   what was affected (medicine_id, invoice_id, etc.)
        details:    additional context dict
        status:     SUCCESS or FAILURE
        before:     state before mutation (for UPDATE/DELETE operations)
        after:      state after mutation (for CREATE/UPDATE operations)
    """
    payload = details or {}
    if before is not None:
        payload["before_state"] = before
    if after is not None:
        payload["after_state"] = after

    entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "actor_id":   actor_id,
        "actor_role": actor_role,
        "action":     action,
        "resource":   resource,
        "status":     status,
        "details":    payload,
    }
    audit_log.info(f"[AUDIT] {json.dumps(entry)}")
