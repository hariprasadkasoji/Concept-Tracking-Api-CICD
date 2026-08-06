"""
user_management_queries.py

All direct SQL access for the User Management module (Users, Roles,
User-Role assignment). Same convention as concept_queries.py: every
function takes an open `cursor`, only SELECT/INSERT/UPDATE, no
HTTPException, no commit/rollback (that stays with the router, next to
the `with db_client() as conn:` block that owns the connection).
"""

from typing import List, Dict, Any, Optional
from app.core.config import settings


# =====================================================================
# USERS
# =====================================================================

def fetch_all_users(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT ROW_NUMBER() OVER (ORDER BY id) AS id, username, name, is_active, created_at, modified_at
        FROM {settings.USERS}
        ORDER BY id
    """)

    return [
        {
            "id": row.id,
            "username": row.username,
            "name": row.name,
            "status": "Active" if row.is_active else "Inactive",
            "created_at": row.created_at,
            # "modified_at": (row.modified_at or row.created_at),
        }
        for row in cursor.fetchall()
    ]


def fetch_user_by_id(cursor, user_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT id, username, name, is_active
        FROM {settings.USERS}
        WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {"id": row.id, "username": row.username, "name": row.name, "is_active": bool(row.is_active)}


def find_duplicate_username(cursor, username: str, exclude_user_id: Optional[int] = None) -> Optional[str]:
    """Case-insensitive check. Returns the existing username if a clash exists, else None."""
    query = f"""
        SELECT TOP 1 username
        FROM {settings.USERS}
        WHERE LOWER(username) = LOWER(?)
    """
    params = [username]
    if exclude_user_id is not None:
        query += " AND id != ?"
        params.append(exclude_user_id)

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    return row[0] if row else None


def insert_user(cursor, username: str, hashed_password: str, name: str, is_active: int) -> None:
    cursor.execute(f"""
        INSERT INTO {settings.USERS}
            (username, hashed_password, name, is_active, created_at, modified_at)
        OUTPUT INSERTED.id    
        VALUES
            (?, ?, ?, ?, GETDATE(), GETDATE())
    """, (username, hashed_password, name, is_active))
    return cursor.fetchone()[0]


def update_user(cursor, user_id: int, name: str, is_active: int) -> None:
    cursor.execute(f"""
        UPDATE {settings.USERS}
        SET
            name = ?,
            is_active = ?,
            modified_at = GETDATE()
        WHERE id = ?
    """, (name, is_active, user_id))


def update_user_password(cursor, user_id: int, hashed_password: str) -> None:
    cursor.execute(f"""
        UPDATE {settings.USERS}
        SET hashed_password = ?
        WHERE id = ?
    """, (hashed_password, user_id))


# =====================================================================
# ROLES
# =====================================================================

def fetch_all_roles(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT role_id, role_name
        FROM {settings.USER_ROLE}
        WHERE is_active = 1
        ORDER BY role_name
    """)
    return [{"role_id": row.role_id, "role_name": row.role_name} for row in cursor.fetchall()]


def find_duplicate_role_name(cursor, role_name: str, exclude_role_id: Optional[int] = None) -> Optional[str]:
    query = f"""
        SELECT TOP 1 role_name
        FROM {settings.USER_ROLE}
        WHERE LOWER(role_name) = LOWER(?)
    """
    params = [role_name]
    if exclude_role_id is not None:
        query += " AND role_id != ?"
        params.append(exclude_role_id)

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    return row[0] if row else None


def insert_role(cursor, role_name: str) -> int:
    cursor.execute(f"""
        INSERT INTO {settings.USER_ROLE} (role_name)
        OUTPUT INSERTED.role_id
        VALUES (?)
    """, (role_name,))
    return cursor.fetchone()[0]


def role_exists(cursor, role_id: int) -> bool:
    cursor.execute(f"""
        SELECT 1 FROM {settings.USER_ROLE}
        WHERE role_id = ? AND is_active = 1
    """, (role_id,))
    return cursor.fetchone() is not None


def soft_delete_role(cursor, role_id: int) -> None:
    """Soft-deletes the role itself, and cascades to soft-delete every
    user_access row currently pointing at it — so a deleted role
    disappears from every user's role list too, not just the roles panel."""
    cursor.execute(f"""
        UPDATE {settings.USER_ROLE}
        SET is_active = 0, modified_date = GETDATE()
        WHERE role_id = ? AND is_active = 1
    """, (role_id,))

    cursor.execute(f"""
        UPDATE {settings.USER_ACCESS}
        SET is_active = 0, modified_date = GETDATE()
        WHERE role_id = ? AND is_active = 1
    """, (role_id,))


def delete_role(cursor, role_id: int) -> None:
    """deletes the role itself"""
    cursor.execute(f"""
        DELETE FROM {settings.USER_ROLE}
        WHERE role_id = ?
    """, (role_id,))

    cursor.execute(f"""
        UPDATE {settings.USER_ACCESS}
        SET is_active = 0, modified_date = GETDATE()
        WHERE role_id = ? AND is_active = 1
    """, (role_id,))

# =====================================================================
# USER <-> ROLE ASSIGNMENT (user_access)
# =====================================================================

def assign_user_role(cursor, user_id: int, role_id: int) -> None:
    """Upsert: reactivates a soft-deleted assignment if one exists,
    otherwise inserts a fresh row. Needed because (user_id, role_id) is
    the primary key, so a soft-deleted row still blocks a plain INSERT."""
    cursor.execute(f"""
        UPDATE {settings.USER_ACCESS}
        SET is_active = 1, modified_date = GETDATE()
        WHERE user_id = ? AND role_id = ? AND is_active = 0
    """, (user_id, role_id))

    if cursor.rowcount == 0:
        cursor.execute(f"""
            INSERT INTO {settings.USER_ACCESS} (user_id, role_id, is_active)
            VALUES (?, ?, 1)
        """, (user_id, role_id))


def remove_user_role(cursor, user_id: int, role_id: int) -> None:
    """Soft-deletes a role assignment (marks it inactive) instead of
    physically removing the row, so assignment history is preserved."""
    cursor.execute(f"""
        DELETE FROM {settings.USER_ACCESS}
        WHERE user_id = ? AND role_id = ?
    """, (user_id, role_id))