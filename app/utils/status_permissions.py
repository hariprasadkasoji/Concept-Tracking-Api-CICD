"""
status_permissions.py

Backend-enforced role -> status transition rules.

This is the single source of truth for "who can move a concept from
status A to status B". The frontend should call GET /api/allowed-statuses
(see bottom of this file for the FastAPI route to add) to build its
dropdown, but the REAL enforcement happens in create_or_update_concept,
which must call is_transition_allowed() before writing DevelopmentStatus.

Never trust developmentStatus from the request body alone.
"""

from fastapi import HTTPException

# =====================================================================
# 1. PERMISSION MATRIX
# =====================================================================
# Structure:
#   ROLE_NAME -> {
#       "from": {current_status: [allowed_next_statuses...]},
#       "override": bool   # True = can set ANY status regardless of "from"
#   }
#
# Edit this dict to change who can do what. Nothing else in the app
# needs to change when you update these rules.
# =====================================================================

STATUS_PERMISSIONS = {
    "Ideation Requestor": {
        "from": {
            "New":              ["Programming Queue", "Programming", "Researching", "Hold","Closed"],
            "Programming":      ["Programming Queue", "Programming", "Researching", "Hold","Closed"],
            "Researching":      ["Programming Queue", "Programming", "New", "Hold","Closed"],
            "Hold":             ["Programming Queue", "Programming", "New", "Hold","Closed"],
            "QA Revise":        ["Programming Queue", "Researching", "Hold","Closed"],
            "Approved":         ["Client Review","Client Approved", "Client Denied","Client Revise", "Client Resubmit", "Hold","Closed"],
            "Client Review":    ["Client Approved", "Client Denied","Client Revise", "Client Resubmit", "Hold","Closed"],
        },
        "override": False,
    },

    "QA": {
        "from": {
            "Result Set QA": ["QA Revise", "Approved"],
            "QA Revise": ["Result Set QA", "Approved"],
        },
        "override": False,
    },

    "Data Science Programmer": {
        "from": {
            "Programming Queue": ["Programming","Result Set QA"],
            "Programming":       ["Result Set QA","Programming Queue"],
        },
        "override": False,
    },

    "Manager": {
        "from": {
            "Approved":        ["Pre-Production"],
            "Pre-Production":  ["Production"],
            # Manager can also close/hold/revisit from virtually any status
            "Production":      ["Closed", "Hold", "Revisit"],
            "New":             ["Closed", "Hold", "Revisit"],
            "Researching":     ["Closed", "Hold", "Revisit"],
            "Programming":     ["Closed", "Hold", "Revisit"],
            "Result Set QA":   ["Closed", "Hold", "Revisit"],
        },
        # Manager can override and force ANY transition, e.g. for exceptions.
        "override": True,
    },

    "Operations": {
        "from": {},        # read-only — no transitions allowed
        "override": False,
    },

    "Viewer": {
        "from": {},        # read-only — no transitions allowed
        "override": False,
    },
}

# Statuses no human should ever set manually via this endpoint —
# these are system-controlled.
SYSTEM_ONLY_STATUSES = {"Superseded"}


# =====================================================================
# 2. LOOKUP HELPERS
# =====================================================================

def get_user_role(cursor, user_id) -> str:
    """
    Resolve a user_id to their role_name via user_access -> user_role.
    Raises 403 if the user has no active role assignment.

    NOTE: assumes one active role per user. If a user can hold multiple
    roles, change this to return a list and adjust is_transition_allowed
    to check across all of them.
    """
    cursor.execute("""
        SELECT ur.role_name
        FROM users u
        INNER JOIN user_access ua ON u.id = ua.user_id
        INNER JOIN user_role ur ON ua.role_id = ur.role_id
        WHERE u.id = ? AND u.is_active = 1
    """, (user_id,))

    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=403,
            detail=f"No active role found for user_id={user_id}. Cannot authorize status change."
        )
    return row[0]


def get_allowed_next_statuses(role: str, current_status: str) -> list:
    """
    Returns the list of statuses `role` is allowed to move a concept
    to, given its current status. Empty list = no permission to change
    status at all from here.
    """
    role_rules = STATUS_PERMISSIONS.get(role)
    if not role_rules:
        return []

    if role_rules.get("override"):
        # Manager (or any future override role) can go anywhere except
        # system-only statuses.
        all_statuses = {
            s
            for rules in STATUS_PERMISSIONS.values()
            for lst in rules["from"].values()
            for s in lst
        } | set(role_rules["from"].keys())
        return sorted(all_statuses - SYSTEM_ONLY_STATUSES)

    return role_rules["from"].get(current_status, [])


def is_transition_allowed(role: str, current_status: str, new_status: str) -> bool:
    """
    The core check. Call this before ANY write to DevelopmentStatus.
    """
    if new_status == current_status:
        return True  # no-op, not a transition

    if new_status in SYSTEM_ONLY_STATUSES:
        return False  # humans can never manually set system-only statuses

    return new_status in get_allowed_next_statuses(role, current_status)


def log_status_change(cursor, concept_id: str, user_id, role: str,
                       old_status: str, new_status: str, reason: str = None):
    """
    Writes one row to ConceptStatusHistory for audit/traceability.

    Requires this table (create once via migration):

        CREATE TABLE ConceptStatusHistory (
            HistoryId    INT IDENTITY PRIMARY KEY,
            ConceptId    VARCHAR(100) NOT NULL,
            OldStatus    VARCHAR(50)  NULL,
            NewStatus    VARCHAR(50)  NOT NULL,
            ChangedBy    INT          NOT NULL,
            ChangedRole  VARCHAR(50)  NOT NULL,
            Reason       VARCHAR(500) NULL,
            ChangedDate  DATETIME     DEFAULT GETDATE()
        );

    Called automatically by enforce_status_transition on every successful
    (allowed) change. Never call this for a rejected change — a 403 should
    leave no trace of a change that didn't happen, only the attempt could
    optionally be logged separately if you want intrusion-style auditing.
    """
    cursor.execute("""
        INSERT INTO ConceptStatusHistory
            (ConceptId, OldStatus, NewStatus, ChangedBy, ChangedRole, Reason, ChangedDate)
        VALUES (?, ?, ?, ?, ?, ?, GETDATE())
    """, (concept_id, old_status, new_status, user_id, role, reason))


def enforce_status_transition(cursor, concept_id: str, user_id, current_status: str,
                               new_status: str, reason: str = None) -> str:
    """
    Convenience wrapper: resolves the user's role, checks the transition,
    raises HTTPException(403) if not allowed, and — on success — writes
    an audit log row. Returns the role.

    Usage in an endpoint:
        role = enforce_status_transition(cursor, concept_id, user_id, current_status, new_status)

    `reason` is optional free text (e.g. "QA feedback: threshold logic revised")
    — pass it through from the request body if you want the "reason for
    version/status change" prompt the original spec calls for.
    """
    role = get_user_role(cursor, user_id)

    original_current_status = current_status
    if not current_status:
        # Brand-new concept being created — treat as "New" for permission purposes
        current_status = "New"

    if not is_transition_allowed(role, current_status, new_status):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{role}' is not permitted to change status "
                f"from '{current_status}' to '{new_status}'."
            )
        )

    # Only log an actual transition, not a no-op save where status is unchanged.
    if new_status != original_current_status:
        log_status_change(cursor, concept_id, user_id, role,
                           original_current_status, new_status, reason)

    return role


# =====================================================================
# 3. OPTIONAL: FRONTEND-FACING ROUTE
# =====================================================================
# Add this route in main.py (import get_user_role, get_allowed_next_statuses
# from this file) so the frontend can build its status dropdown from the
# SAME rules the backend enforces — no duplicated/out-of-sync logic.
#
# from app.status_permissions import get_user_role, get_allowed_next_statuses
#
# @app.get("/api/allowed-statuses")
# def get_allowed_statuses(user_id: int, current_status: str = "New"):
#     with db_client() as conn:
#         cursor = conn.cursor()
#         role = get_user_role(cursor, user_id)
#         return {
#             "role": role,
#             "current_status": current_status,
#             "allowed_next_statuses": get_allowed_next_statuses(role, current_status)
#         }

