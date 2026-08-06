"""
master_data_queries.py

All direct SQL access for the master-data / dropdown-config module
(Client Name, Master Concept Name, Review Type, Claim Type — coded;
Development Status, Priority, Client Approval Status — plain).
Same convention as user_management_queries.py: every function takes an
open `cursor`, only SELECT/INSERT/UPDATE/DELETE, no HTTPException, no
commit/rollback (that stays with the router).
"""

from typing import List, Dict, Any, Optional
from app.core.config import settings


# =====================================================================
# CODED CATEGORIES
#
# code_length matches what generate_concept_id/parse_concept_id expect
# for that segment of the concept ID — 3/4/1/1 confirmed against real
# client_id values like 'CSP'/'HCP' (3 chars); double-check the other
# two against the actual ID-generation logic if unsure.
#
# extra_cols: columns beyond the pk/name pair that this category's table
# carries. clients has description + claim_other; master_concepts has
# description + example; review_type/claim_type have neither (their
# "name" IS the description column, there's nothing left over).
# =====================================================================

CODED_CONFIG = {
    "client-name": {
        "table": settings.CLIENTS,
        "pk_col": "client_id",
        "name_col": "client_name",
        "code_length": 3,
        "extra_cols": ["description", "claim_other"],
        "name_max_length": 255,
        "extra_col_lengths": {"description": 255, "claim_other": 255},
    },
    "master-concept-name": {
        "table": settings.MASTER_CONCEPTS,
        "pk_col": "master_id",
        "name_col": "concept_name",
        "code_length": 4,
        "extra_cols": ["description", "example"],
        "name_max_length": 255,
        "extra_col_lengths": {"description": 255, "example": 255},
    },
    "review-type": {
        "table": settings.REVIEW_TYPE,
        "pk_col": "review_type",
        "name_col": "description",
        "code_length": 1,
        "extra_cols": [],
        "name_max_length": 255,
        "extra_col_lengths": {},
    },
    "claim-type": {
        "table": settings.CLAIM_TYPE,
        "pk_col": "claim_type",
        "name_col": "description",
        "code_length": 1,
        "extra_cols": [],
        "name_max_length": 255,
        "extra_col_lengths": {},
    },
}

def resolve_coded(category: str) -> Dict[str, Any]:
    cfg = CODED_CONFIG.get(category)
    if not cfg:
        raise ValueError(f"Unknown coded category '{category}'.")
    return cfg


def fetch_all_coded(cursor, category: str) -> List[Dict[str, Any]]:
    cfg = resolve_coded(category)
    extra_cols = cfg["extra_cols"]

    select_parts = [f"{cfg['pk_col']} AS code", f"{cfg['name_col']} AS name"] + extra_cols + ["active"]
    cursor.execute(f"""
        SELECT {', '.join(select_parts)}
        FROM {cfg['table']}
        WHERE active = 1
        ORDER BY createddate
    """)

    results = []
    for row in cursor.fetchall():
        item = {"code": row.code, "name": row.name, "is_active": int(bool(row.active))}
        for col in extra_cols:
            item[col] = getattr(row, col)
        results.append(item)
    return results


def code_exists(cursor, category: str, code: str) -> bool:
    cfg = resolve_coded(category)
    cursor.execute(f"""
        SELECT 1 FROM {cfg['table']} WHERE {cfg['pk_col']} = ?
    """, (code,))
    return cursor.fetchone() is not None


def insert_coded(
    cursor,
    category: str,
    code: str,
    name: str,
    is_active: int,
    created_by: str,
    extra_values: Optional[Dict[str, Any]] = None,
) -> None:
    cfg = resolve_coded(category)
    extra_cols = cfg["extra_cols"]
    extra_values = extra_values or {}

    cols = [cfg["pk_col"], cfg["name_col"]] + extra_cols + ["createdby", "createddate", "active"]
    placeholders = ["?"] * (2 + len(extra_cols)) + ["?", "GETDATE()", "?"]
    values = [code, name] + [extra_values.get(c) for c in extra_cols] + [created_by, is_active]

    cursor.execute(f"""
        INSERT INTO {cfg['table']} ({', '.join(cols)})
        VALUES ({', '.join(placeholders)})
    """, tuple(values))


def update_coded(
    cursor,
    category: str,
    code: str,
    name: str,
    is_active: int,
    extra_values: Optional[Dict[str, Any]] = None,
) -> int:
    cfg = resolve_coded(category)
    extra_cols = cfg["extra_cols"]
    extra_values = extra_values or {}

    set_parts = [f"{cfg['name_col']} = ?"] + [f"{c} = ?" for c in extra_cols] + ["active = ?", "modifieddate = GETDATE()"]
    values = [name] + [extra_values.get(c) for c in extra_cols] + [is_active, code]

    cursor.execute(f"""
        UPDATE {cfg['table']}
        SET {', '.join(set_parts)}
        WHERE {cfg['pk_col']} = ?
    """, tuple(values))
    return cursor.rowcount


def soft_delete_coded(cursor, category: str, code: str) -> int:
    cfg = resolve_coded(category)
    cursor.execute(f"""
        UPDATE {cfg['table']}
        SET active = 0, modifieddate = GETDATE()
        WHERE {cfg['pk_col']} = ? AND active = 1
    """, (code,))
    return cursor.rowcount


def delete_coded(cursor, category: str, code: str) -> int:
    cfg = resolve_coded(category)
    cursor.execute(f"""
        DELETE FROM {cfg['table']}
        WHERE {cfg['pk_col']} = ?
    """, (code,))
    return cursor.rowcount


# =====================================================================
# PLAIN CATEGORIES
# No active column, no extra columns — id + value only.
# =====================================================================

PLAIN_CONFIG = {
    "development-status": {"table": settings.DEVELOPMENT_STATUS, "value_max_length": 50},
    "priority": {"table": settings.PRIORITY_STATUS, "value_max_length": 50},
    "client-approval-status": {"table": settings.CLIENT_APPROVAL_STATUS, "value_max_length": 50},
}


def resolve_plain(category: str) -> Dict[str, Any]:
    cfg = PLAIN_CONFIG.get(category)
    if not cfg:
        raise ValueError(f"Unknown plain category '{category}'.")
    return cfg


def fetch_all_plain(cursor, category: str) -> List[Dict[str, Any]]:
    cfg = resolve_plain(category)
    cursor.execute(f"""
        SELECT id, value
        FROM {cfg['table']}
        ORDER BY created_date
    """)
    return [{"id": row.id, "name": row.value} for row in cursor.fetchall()]

def find_duplicate_value(cursor, category: str, value: str, exclude_id: Optional[int] = None) -> Optional[str]:
    cfg = resolve_plain(category)
    query = f"""
        SELECT TOP 1 value FROM {cfg['table']}
        WHERE LOWER(value) = LOWER(?)
    """
    params = [value]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    return row[0] if row else None


def insert_plain(cursor, category: str, value: str) -> int:
    cfg = resolve_plain(category)
    cursor.execute(f"""
        INSERT INTO {cfg['table']} (value)
        OUTPUT INSERTED.id
        VALUES (?)
    """, (value,))
    return cursor.fetchone()[0]


def update_plain(cursor, category: str, item_id: int, value: str) -> int:
    cfg = resolve_plain(category)
    cursor.execute(f"""
        UPDATE {cfg['table']}
        SET value = ?
        WHERE id = ?
    """, (value, item_id))
    return cursor.rowcount


def delete_plain(cursor, category: str, item_id: int) -> int:
    cfg = resolve_plain(category)
    cursor.execute(f"""
        DELETE FROM {cfg['table']}
        WHERE id = ?
    """, (item_id,))
    return cursor.rowcount