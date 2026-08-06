import logging
from fastapi import APIRouter, HTTPException
from app.core.sql_connection import db_client
from app.utils.status_permissions import get_user_role, get_allowed_next_statuses
from app.services import concept_queries as q

logger = logging.getLogger(__name__)

status_route = APIRouter()


@status_route.get("/api/allowed-statuses")
def get_allowed_statuses(user_id: int, role_name: str, current_status: str = "New"):
    logger.info(
        "[API HIT] GET /api/allowed-statuses user_id=%s current_status=%s current_role_name=%s",
        user_id, current_status,role_name
    )
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            # role = get_user_role(cursor, user_id)
            role = role_name
            allowed = get_allowed_next_statuses(role, current_status)
            logger.info(
                "[FETCH SUCCESS] GET /api/allowed-statuses user_id=%s role=%s allowed=%s",
                user_id, role, allowed
            )
            return {
                "success": True,
                "role": role,
                "current_status": current_status,
                "allowed_next_statuses": allowed
            }
    except HTTPException as e:
        logger.error(
            "API FAILED: GET /api/allowed-statuses status=%s detail=%s user_id=%s",
            e.status_code, e.detail, user_id
        )
        raise
    except Exception as e:
        logger.error(
            "API FAILED: GET /api/allowed-statuses user_id=%s error=%s",
            user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))