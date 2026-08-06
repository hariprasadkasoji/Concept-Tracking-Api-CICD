import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.sql_connection import db_client
from app.services import concept_queries as q
from app.core.authenticate import (
    create_access_token,
    decode_pending_token,
    get_current_user,
)
from app.services.pydantic_schemas import (
    MyRolesResponse,
    SelectRoleRequest,
    SwitchRoleRequest,
    Token,
    User,
)

logger = logging.getLogger(__name__)

role_router = APIRouter()


@role_router.post("/select-role", response_model=Token)
def select_role(payload: SelectRoleRequest):
    """
    Second step of login for a user with more than one role.
    """
    logger.info(
        "[API HIT] POST /select-role role_id=%s",
        payload.role_id,
    )

    try:
        identity = decode_pending_token(payload.pending_token)
        user_id = identity["user_id"]
        username = identity["username"]

        logger.info(
            "[TOKEN VERIFIED] user_id=%s username=%s",
            user_id,
            username,
        )

        with db_client() as conn:
            cursor = conn.cursor()

            if not q.user_has_role(cursor, user_id, payload.role_id):
                logger.warning(
                    "[ROLE VALIDATION FAILED] user_id=%s role_id=%s",
                    user_id,
                    payload.role_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="That role is not assigned to this user.",
                )

        access_token = create_access_token(
            data={
                "sub": username,
                "user_id": user_id,
                "role_id": payload.role_id,
            },
            expires_delta=timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            ),
        )

        logger.info(
            "[ROLE SELECT SUCCESS] user_id=%s role_id=%s",
            user_id,
            payload.role_id,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            id=user_id,
        )

    except HTTPException as e:
        logger.error(
            "API FAILED: POST /select-role status=%s detail=%s role_id=%s",
            e.status_code,
            e.detail,
            payload.role_id,
        )
        raise

    except Exception as e:
        logger.error(
            "API FAILED: POST /select-role role_id=%s error=%s",
            payload.role_id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@role_router.post("/switch-role", response_model=Token)
def switch_role(
    payload: SwitchRoleRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Mid-session role change.
    """
    logger.info(
        "[API HIT] POST /switch-role user_id=%s current_role=%s requested_role=%s",
        current_user.id,
        getattr(current_user, "role_id", None),
        payload.role_id,
    )

    try:
        with db_client() as conn:
            cursor = conn.cursor()

            if not q.user_has_role(cursor, current_user.id, payload.role_id):
                logger.warning(
                    "[ROLE VALIDATION FAILED] user_id=%s requested_role=%s",
                    current_user.id,
                    payload.role_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="That role is not assigned to this user.",
                )

        access_token = create_access_token(
            data={
                "sub": current_user.username,
                "user_id": current_user.id,
                "role_id": payload.role_id,
            },
            expires_delta=timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            ),
        )

        logger.info(
            "[ROLE SWITCH SUCCESS] user_id=%s new_role=%s",
            current_user.id,
            payload.role_id,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            id=current_user.id,
        )

    except HTTPException as e:
        logger.error(
            "API FAILED: POST /switch-role status=%s detail=%s user_id=%s requested_role=%s",
            e.status_code,
            e.detail,
            current_user.id,
            payload.role_id,
        )
        raise

    except Exception as e:
        logger.error(
            "API FAILED: POST /switch-role user_id=%s requested_role=%s error=%s",
            current_user.id,
            payload.role_id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    
@role_router.get("/my-roles", response_model=MyRolesResponse)
def my_roles(current_user: User = Depends(get_current_user)):
    """
    Returns the roles currently assigned to the logged-in user, read
    fresh from user_access/user_role on every call - lets the frontend's
    "Switch Role" dropdown pick up roles added/removed after the user's
    last login, instead of relying only on the availableRoles snapshot
    cached in sessionStorage at select-role time.
    """
    logger.info(
        "[API HIT] GET /my-roles user_id=%s",
        current_user.id,
    )

    try:
        with db_client() as conn:
            cursor = conn.cursor()
            roles = q.get_user_roles(cursor, current_user.id)

        logger.info(
            "[MY ROLES SUCCESS] user_id=%s role_count=%s",
            current_user.id,
            len(roles),
        )

        return MyRolesResponse(roles=roles)

    except Exception as e:
        logger.error(
            "API FAILED: GET /my-roles user_id=%s error=%s",
            current_user.id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
