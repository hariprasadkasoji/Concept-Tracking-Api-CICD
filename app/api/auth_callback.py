import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.core.oauth import oauth
from app.core import authenticate
from app.core.config import *

logger = logging.getLogger(__name__)


auth_callback_route = APIRouter(prefix="/auth")


@auth_callback_route.get("/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.microsoft.authorize_access_token(request)

        username = token['userinfo']['email']
        name = token['userinfo']['name']

        # Validate user and fetch every role assigned to them - a user can
        # hold more than one now, so this is never a single role_id anymore.
        user_data = authenticate.user_exists(username)

        if not user_data:
            frontend_url = (
                f"{settings.UI_FRONTEND_URL}/#/auth/callback"
                f"?error=unauthorized&username={username}"
            )
            return RedirectResponse(url=frontend_url)

        roles = user_data["roles"]

        if len(roles) == 0:
            frontend_url = (
                f"{settings.UI_FRONTEND_URL}/#/auth/callback"
                f"?error=no_role_assigned&username={username}"
            )
            return RedirectResponse(url=frontend_url)

        if len(roles) > 1:
            # Multiple roles - don't issue a real session token yet. Send a
            # short-lived pending token + the role list to a dedicated
            # frontend "choose your role" screen; that screen then calls
            # POST /select-role with the chosen role_id to get the real JWT.
            pending_token = authenticate.create_pending_token(user_data["id"], username)
            roles_json = quote(json.dumps(roles))
            frontend_url = (
                f"{settings.UI_FRONTEND_URL}/#/auth/select-role"
                f"?pending_token={pending_token}"
                f"&username={username}"
                f"&name={name}"
                f"&roles={roles_json}"
            )
            logger.info(f"FRONTEND_URL (role selection required): {frontend_url}")
            return RedirectResponse(url=frontend_url)

        # Exactly one role - proceed exactly as before, no change in
        # behavior or URL shape for existing single-role users.
        role_id = roles[0]["role_id"]
        role_name = roles[0]["role_name"]

        jwt_token = authenticate.create_jwt_token({
            "sub": username,
            "user_id": user_data["id"],
            "role_id": role_id
        })

        frontend_url = (
            f"{settings.UI_FRONTEND_URL}/#/auth/callback"
            f"?token={jwt_token}"
            f"&username={username}"
            f"&name={name}"
            f"&role_id={role_id}"
            f"&uid={user_data['id']}"
            f"&roleName={role_name}"
        )
        logger.info(f"FRONTEND_URL: {frontend_url}")

        return RedirectResponse(url=frontend_url)

    except Exception as e:
        return RedirectResponse(
            url=f"{settings.UI_FRONTEND_URL}/#/auth/callback?error={str(e)}"
        )