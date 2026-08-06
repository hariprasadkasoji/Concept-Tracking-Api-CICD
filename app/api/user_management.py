import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
import numpy as np
import pandas as pd

from app.core.sql_connection import db_client
from app.core.authenticate import get_password_hash, require_admin_user
from app.services import concept_queries as q
from app.services import user_management_queries as um
from app.services.pydantic_schemas import (
    AssignRoleRequest,
    CreateRoleRequest,
    CreateUserRequest,
    DashboardRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    User,
)
from app.services.dataframe_utils import (
    apply_filters_on_df,
    apply_quick_search,
    apply_sort_on_df,
    coerce_date_columns,
    infer_column_metadata,
    FILTER_OPERATIONS,
)

logger = logging.getLogger(__name__)

user_management_route = APIRouter(prefix="/api/user-management")


# =====================================================================
# ACCESS CONTROL
#
# require_admin_user (app.core.authenticate) checks current_user.role_id
# against user_role.role_name == 'Admin'. That role must exist first -
# create it once via POST /api/user-management/roles, then assign it to
# whichever user(s) should manage this module via
# POST /api/user-management/users/{id}/roles.
# =====================================================================

require_admin = require_admin_user


# =====================================================================
# USERS
# =====================================================================

@user_management_route.post("/users/list")
def list_users(request: DashboardRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] POST /api/user-management/users/list")
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            users = um.fetch_all_users(cursor)
            for u in users:
                roles = q.get_user_roles(cursor, u["id"])
                u["roles"] = ", ".join(r["role_name"] for r in roles) if roles else ""

        if not users:
            logger.info("[FETCH SUCCESS] POST /api/user-management/users/list returned 0 record(s)")
            return {
                "columns": [], "columnMetadata": [], "data": [],
                "totalCount": 0, "page": request.page,
                "page_size": request.page_size, "error": "",
            }

        df = pd.DataFrame(users)
        df = coerce_date_columns(df, date_column_names={"created_at", "modified_at"})

        # apply_filters_on_df has no "set"/values-list branch, so status
        # (a plain "Active"/"Inactive" string column) is handled separately.
        filter_model = dict(request.filterModel or {})
        status_rule = filter_model.pop("status", None)
        if status_rule and status_rule.get("values"):
            allowed = [v for v in status_rule["values"] if v in ("Active", "Inactive")]
            if allowed:
                df = df[df["status"].isin(allowed)].reset_index(drop=True)

        df = apply_filters_on_df(df, filter_model)
        df = apply_quick_search(df, request.quickSearch)
        df = apply_sort_on_df(df, request.sortModel)

        total_count = len(df)

        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        page_df = df.iloc[start:end].copy()
        page_df = page_df.replace([np.nan, np.inf, -np.inf], None)

        columns = [
            {"field": col, "headerName": col.replace("_", " ").title()}
            for col in df.columns
        ]
        column_metadata = infer_column_metadata(df, FILTER_OPERATIONS)
        for field, meta in column_metadata.items():
            if field == "status":
                meta["type"] = "set"
                meta["filterOperations"] = ["equals", "notEqual"]
                meta["values"] = ["Active", "Inactive"]

        logger.info(
            "[FETCH SUCCESS] POST /api/user-management/users/list returned %s of %s record(s) (page=%s)",
            len(page_df), total_count, request.page
        )

        return {
            "columns": columns,
            "columnMetadata": column_metadata,
            "data": jsonable_encoder(page_df.to_dict(orient="records")),
            "page": request.page,
            "page_size": request.page_size,
            "totalCount": total_count,
            "error": "",
        }

    except Exception as e:
        logger.error(
            "API FAILED: POST /api/user-management/users/list error=%s",
            str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@user_management_route.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] POST /api/user-management/users username=%s", payload.username)
    username = payload.username.strip()
    if not username:
        logger.warning("Create user failed: empty username")
        raise HTTPException(status_code=400, detail="Username is required.")

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            existing = um.find_duplicate_username(cursor, username)
            if existing:
                logger.warning("Create user failed: username '%s' already exists", username)
                raise HTTPException(
                    status_code=409,
                    detail=f"Username '{existing}' already exists.",
                )

            # hashed = get_password_hash(payload.password)
            hashed = payload.password
            new_user_id = um.insert_user(
                cursor, username, hashed, payload.name, int(payload.is_active)
            )

            for role_id in payload.role_ids:
                if not q.user_has_role(cursor, new_user_id, role_id):
                    um.assign_user_role(cursor, new_user_id, role_id)

            conn.commit()
            logger.info(
                "[SUCCESS] POST /api/user-management/users created id=%s username=%s",
                new_user_id, username
            )

            return {"success": True, "id": new_user_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: POST /api/user-management/users error=%s",
            str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@user_management_route.put("/users/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] PUT /api/user-management/users/%s", user_id)
    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not um.fetch_user_by_id(cursor, user_id):
                logger.warning("Update user failed: user_id=%s not found", user_id)
                raise HTTPException(status_code=404, detail="User not found.")

            um.update_user(cursor, user_id, payload.name, int(payload.is_active))
            conn.commit()
            logger.info(
                "[SUCCESS] PUT /api/user-management/users/%s name=%s active=%s",
                user_id, payload.name, payload.is_active
            )
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: PUT /api/user-management/users/%s error=%s",
            user_id, str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@user_management_route.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: ResetPasswordRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] POST /api/user-management/users/%s/reset-password", user_id)
    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not um.fetch_user_by_id(cursor, user_id):
                logger.warning("Reset password failed: user_id=%s not found", user_id)
                raise HTTPException(status_code=404, detail="User not found.")

            hashed = get_password_hash(payload.password)
            um.update_user_password(cursor, user_id, hashed)
            conn.commit()
            logger.info("[SUCCESS] Password reset for user_id=%s", user_id)

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: POST /api/user-management/users/%s/reset-password error=%s",
            user_id, str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# ROLES
# =====================================================================

@user_management_route.get("/roles")
def list_roles(_: User = Depends(require_admin)):
    logger.info("[API HIT] GET /api/user-management/roles")
    with db_client() as conn:
        cursor = conn.cursor()
        roles = um.fetch_all_roles(cursor)
        logger.info("[FETCH SUCCESS] GET /api/user-management/roles returned %s record(s)", len(roles))
        return {"roles": roles}


@user_management_route.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: CreateRoleRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] POST /api/user-management/roles role_name=%s", payload.role_name)
    role_name = payload.role_name.strip()
    if not role_name:
        logger.warning("Create role failed: empty role name")
        raise HTTPException(status_code=400, detail="Role name is required.")

    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            existing = um.find_duplicate_role_name(cursor, role_name)
            if existing:
                logger.warning("Create role failed: role '%s' already exists", role_name)
                raise HTTPException(
                    status_code=409,
                    detail=f"Role '{existing}' already exists.",
                )

            new_role_id = um.insert_role(cursor, role_name)
            conn.commit()
            logger.info(
                "[SUCCESS] POST /api/user-management/roles created id=%s role_name=%s",
                new_role_id, role_name
            )

            return {"success": True, "role_id": new_role_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: POST /api/user-management/roles error=%s",
            str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@user_management_route.delete("/roles/{role_id}")
def delete_role(role_id: int, _: User = Depends(require_admin)):
    logger.info("[API HIT] DELETE /api/user-management/roles/%s", role_id)
    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not um.role_exists(cursor, role_id):
                logger.warning("Delete role failed: role_id=%s not found", role_id)
                raise HTTPException(status_code=404, detail="Role not found.")

            um.delete_role(cursor, role_id)
            conn.commit()
            logger.info("[SUCCESS] DELETE /api/user-management/roles/%s", role_id)
            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: DELETE /api/user-management/roles/%s error=%s",
            role_id, str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# ROLE ACCESS (user_access - which roles a user holds)
# =====================================================================

@user_management_route.get("/users/{user_id}/roles")
def get_user_roles(user_id: int, _: User = Depends(require_admin)):
    logger.info("[API HIT] GET /api/user-management/users/%s/roles", user_id)
    with db_client() as conn:
        cursor = conn.cursor()

        if not um.fetch_user_by_id(cursor, user_id):
            logger.warning("Get user roles failed: user_id=%s not found", user_id)
            raise HTTPException(status_code=404, detail="User not found.")

        roles = q.get_user_roles(cursor, user_id)
        logger.info(
            "[FETCH SUCCESS] GET /api/user-management/users/%s/roles returned %s record(s)",
            user_id, len(roles)
        )
        return {"roles": roles}


@user_management_route.post("/users/{user_id}/roles")
def assign_role(user_id: int, payload: AssignRoleRequest, _: User = Depends(require_admin)):
    logger.info("[API HIT] POST /api/user-management/users/%s/roles role_id=%s", user_id, payload.role_id)
    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not um.fetch_user_by_id(cursor, user_id):
                logger.warning("Assign role failed: user_id=%s not found", user_id)

                raise HTTPException(status_code=404, detail="User not found.")

            if q.user_has_role(cursor, user_id, payload.role_id):
                logger.warning("Assign role failed: user_id=%s already has role_id=%s",user_id,payload.role_id)
                raise HTTPException(
                    status_code=409, detail="User already has that role."
                )

            um.assign_user_role(cursor, user_id, payload.role_id)
            conn.commit()
            logger.info("[SUCCESS] Role assigned: user_id=%s role_id=%s",user_id,payload.role_id)

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: POST /api/user-management/users/%s/roles error=%s",
            user_id, str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@user_management_route.delete("/users/{user_id}/roles/{role_id}")
def unassign_role(user_id: int, role_id: int, _: User = Depends(require_admin)):
    logger.info("[API HIT] DELETE /api/user-management/users/%s/roles/%s", user_id, role_id)
    conn = None
    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not q.user_has_role(cursor, user_id, role_id):
                logger.warning("Remove role failed: user_id=%s does not have role_id=%s",user_id,role_id)
                raise HTTPException(
                    status_code=404, detail="User does not have that role."
                )

            um.remove_user_role(cursor, user_id, role_id)
            conn.commit()
            logger.info("[SUCCESS] Role removed: user_id=%s role_id=%s",user_id,role_id)

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API FAILED: DELETE /api/user-management/users/%s/roles/%s error=%s",
            user_id, role_id, str(e), exc_info=True
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))