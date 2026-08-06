import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.sql_connection import db_client
from app.core.authenticate import require_admin_user
from app.services import master_data_queries as md
from app.services.pydantic_schemas import (
    CreateCodedMasterDataRequest,
    UpdateCodedMasterDataRequest,
    CreatePlainMasterDataRequest,
    UpdatePlainMasterDataRequest,
    User,
)

logger = logging.getLogger(__name__)

master_data_management_route = APIRouter(prefix="/api/user-management/master-data")


def _extract_extra_values(payload, category: str) -> dict:
    """Pulls whichever extra fields this category's table actually has
    (e.g. description/claim_other for clients) off the payload, trimming
    strings. Categories with no extra_cols (review-type, claim-type) get
    an empty dict, which insert_coded/update_coded treat as a no-op."""
    cfg = md.resolve_coded(category)
    values = {}
    for col in cfg["extra_cols"]:
        val = getattr(payload, col, None)
        values[col] = val.strip() if isinstance(val, str) else val
    return values


# =====================================================================
# CODED (Client Name, Master Concept Name, Review Type, Claim Type)
# code is the primary key in these tables - immutable once created.
# Enforces the exact code length generate_concept_id/parse_concept_id
# require - a bad-length code here breaks concept-id parsing app-wide.
# =====================================================================

@master_data_management_route.get("/coded/{category}")
def list_coded(category: str, _: User = Depends(require_admin_user)):
    logger.info("[API HIT] GET /api/user-management/master-data/coded/%s", category)
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            items = md.fetch_all_coded(cursor, category)
            cfg = md.resolve_coded(category)
            logger.info(
                "[FETCH SUCCESS] GET /api/user-management/master-data/coded/%s returned %s record(s)",
                category, len(items)
            )
            return {
                "items": items,
                "codeLength": cfg["code_length"],
                "nameMaxLength": cfg["name_max_length"],
                "extraColLengths": cfg["extra_col_lengths"],
            }
    except ValueError as e:
        logger.warning("list_coded(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))


@master_data_management_route.post("/coded/{category}", status_code=status.HTTP_201_CREATED)
def create_coded(
    category: str, payload: CreateCodedMasterDataRequest,
    current_user: User = Depends(require_admin_user),
):
    logger.info("[API HIT] POST /api/user-management/master-data/coded/%s code=%s", category, payload.code)
    conn = None
    try:
        cfg = md.resolve_coded(category)
    except ValueError as e:
        logger.warning("create_coded(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    code = payload.code.strip()
    name = payload.name.strip()

    if len(code) != cfg["code_length"]:
        logger.warning(
            "create_coded(%s) failed: code '%s' has invalid length (expected %s)",
            category, code, cfg["code_length"]
        )
        raise HTTPException(
            status_code=400,
            detail=f"{category} code must be exactly {cfg['code_length']} characters.",
        )
    if not name:
        logger.warning("create_coded(%s) failed: empty name", category)
        raise HTTPException(status_code=400, detail="Name is required.")
    if len(name) > cfg["name_max_length"]:
        logger.warning(
            "create_coded(%s) failed: name exceeds max length %s (got %s chars)",
            category, cfg["name_max_length"], len(name)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Name must be {cfg['name_max_length']} characters or fewer.",
        )

    extra_values = _extract_extra_values(payload, category)
    for col, val in extra_values.items():
        max_len = cfg["extra_col_lengths"].get(col)
        if max_len and isinstance(val, str) and len(val) > max_len:
            logger.warning(
                "create_coded(%s) failed: field '%s' exceeds max length %s (got %s chars)",
                category, col, max_len, len(val)
            )
            raise HTTPException(
                status_code=400,
                detail=f"'{col}' must be {max_len} characters or fewer.",
            )

    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if md.code_exists(cursor, category, code):
                logger.warning("create_coded(%s) failed: code '%s' already exists", category, code)
                raise HTTPException(status_code=409, detail=f"Code '{code}' already exists.")

            md.insert_coded(
                cursor, category, code, name, int(payload.is_active),
                current_user.username, extra_values,
            )
            conn.commit()
            logger.info(
                "[SUCCESS] POST /api/user-management/master-data/coded/%s created code=%s by=%s",
                category, code, current_user.username
            )
            return {"success": True, "code": code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: create_coded(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@master_data_management_route.put("/coded/{category}/{code}")
def update_coded(
    category: str, code: str, payload: UpdateCodedMasterDataRequest,
    _: User = Depends(require_admin_user),
):
    logger.info("[API HIT] PUT /api/user-management/master-data/coded/%s/%s", category, code)
    try:
        cfg = md.resolve_coded(category)
    except ValueError as e:
        logger.warning("update_coded(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    name = payload.name.strip()
    if not name:
        logger.warning("update_coded(%s) failed: empty name for code=%s", category, code)
        raise HTTPException(status_code=400, detail="Name is required.")
    if len(name) > cfg["name_max_length"]:
        logger.warning(
            "update_coded(%s) failed: name exceeds max length %s (got %s chars) code=%s",
            category, cfg["name_max_length"], len(name), code
        )
        raise HTTPException(
            status_code=400,
            detail=f"Name must be {cfg['name_max_length']} characters or fewer.",
        )

    extra_values = _extract_extra_values(payload, category)
    for col, val in extra_values.items():
        max_len = cfg["extra_col_lengths"].get(col)
        if max_len and isinstance(val, str) and len(val) > max_len:
            logger.warning(
                "update_coded(%s) failed: field '%s' exceeds max length %s (got %s chars) code=%s",
                category, col, max_len, len(val), code
            )
            raise HTTPException(
                status_code=400,
                detail=f"'{col}' must be {max_len} characters or fewer.",
            )

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            affected = md.update_coded(cursor, category, code, name, int(payload.is_active), extra_values)
            if affected == 0:
                logger.warning("update_coded(%s) failed: code '%s' not found", category, code)
                raise HTTPException(status_code=404, detail=f"Code '{code}' not found.")

            conn.commit()
            logger.info("[SUCCESS] PUT /api/user-management/master-data/coded/%s/%s", category, code)
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: update_coded(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@master_data_management_route.delete("/coded/{category}/{code}")
def delete_coded(category: str, code: str, _: User = Depends(require_admin_user)):
    logger.info("[API HIT] DELETE /api/user-management/master-data/coded/%s/%s", category, code)
    try:
        md.resolve_coded(category)
    except ValueError as e:
        logger.warning("delete_coded(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            affected = md.delete_coded(cursor, category, code)
            if affected == 0:
                logger.warning("delete_coded(%s) failed: code '%s' not found", category, code)
                raise HTTPException(status_code=404, detail=f"Code '{code}' not found.")

            conn.commit()
            logger.info("[SUCCESS] DELETE /api/user-management/master-data/coded/%s/%s", category, code)
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: delete_coded(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# PLAIN (Development Status, Priority, Client Approval Status)
# =====================================================================

@master_data_management_route.get("/plain/{category}")
def list_plain(category: str, _: User = Depends(require_admin_user)):
    logger.info("[API HIT] GET /api/user-management/master-data/plain/%s", category)
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            items = md.fetch_all_plain(cursor, category)
            cfg = md.resolve_plain(category)
            logger.info(
                "[FETCH SUCCESS] GET /api/user-management/master-data/plain/%s returned %s record(s)",
                category, len(items)
            )
            return {"items": items, "valueMaxLength": cfg["value_max_length"]}
    except ValueError as e:
        logger.warning("list_plain(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))


@master_data_management_route.post("/plain/{category}", status_code=status.HTTP_201_CREATED)
def create_plain(category: str, payload: CreatePlainMasterDataRequest, _: User = Depends(require_admin_user)):
    logger.info("[API HIT] POST /api/user-management/master-data/plain/%s name=%s", category, payload.name)
    conn = None
    try:
        cfg = md.resolve_plain(category)
    except ValueError as e:
        logger.warning("create_plain(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    name = payload.name.strip()
    if not name:
        logger.warning("create_plain(%s) failed: empty value", category)
        raise HTTPException(status_code=400, detail="Value is required.")
    if len(name) > cfg["value_max_length"]:
        logger.warning(
            "create_plain(%s) failed: value exceeds max length %s (got %s chars)",
            category, cfg["value_max_length"], len(name)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Value must be {cfg['value_max_length']} characters or fewer.",
        )

    try:
        with db_client() as conn:
            cursor = conn.cursor()

            existing = md.find_duplicate_value(cursor, category, name)
            if existing:
                logger.warning("create_plain(%s) failed: '%s' already exists", category, existing)
                raise HTTPException(status_code=409, detail=f"'{existing}' already exists.")

            new_id = md.insert_plain(cursor, category, name)
            conn.commit()
            logger.info(
                "[SUCCESS] POST /api/user-management/master-data/plain/%s created id=%s name=%s",
                category, new_id, name
            )
            return {"success": True, "id": new_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: create_plain(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@master_data_management_route.put("/plain/{category}/{item_id}")
def update_plain(
    category: str, item_id: int, payload: UpdatePlainMasterDataRequest,
    _: User = Depends(require_admin_user),
):
    logger.info("[API HIT] PUT /api/user-management/master-data/plain/%s/%s", category, item_id)
    try:
        cfg = md.resolve_plain(category)
    except ValueError as e:
        logger.warning("update_plain(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    name = payload.name.strip()
    if not name:
        logger.warning("update_plain(%s) failed: empty value for id=%s", category, item_id)
        raise HTTPException(status_code=400, detail="Value is required.")
    if len(name) > cfg["value_max_length"]:
        logger.warning(
            "update_plain(%s) failed: value exceeds max length %s (got %s chars) id=%s",
            category, cfg["value_max_length"], len(name), item_id
        )
        raise HTTPException(
            status_code=400,
            detail=f"Value must be {cfg['value_max_length']} characters or fewer.",
        )

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            existing = md.find_duplicate_value(cursor, category, name, exclude_id=item_id)
            if existing:
                logger.warning("update_plain(%s) failed: '%s' already exists", category, existing)
                raise HTTPException(status_code=409, detail=f"'{existing}' already exists.")

            affected = md.update_plain(cursor, category, item_id, name)
            if affected == 0:
                logger.warning("update_plain(%s) failed: id=%s not found", category, item_id)
                raise HTTPException(status_code=404, detail="Item not found.")

            conn.commit()
            logger.info("[SUCCESS] PUT /api/user-management/master-data/plain/%s/%s name=%s", category, item_id, name)
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: update_plain(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@master_data_management_route.delete("/plain/{category}/{item_id}")
def delete_plain(category: str, item_id: int, _: User = Depends(require_admin_user)):
    logger.info("[API HIT] DELETE /api/user-management/master-data/plain/%s/%s", category, item_id)
    try:
        md.resolve_plain(category)
    except ValueError as e:
        logger.warning("delete_plain(%s) failed: %s", category, str(e))
        raise HTTPException(status_code=404, detail=str(e))

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            affected = md.delete_plain(cursor, category, item_id)
            if affected == 0:
                logger.warning("delete_plain(%s) failed: id=%s not found", category, item_id)
                raise HTTPException(status_code=404, detail="Item not found.")

            conn.commit()
            logger.info("[SUCCESS] DELETE /api/user-management/master-data/plain/%s/%s", category, item_id)
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("API FAILED: delete_plain(%s) error=%s", category, str(e), exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))