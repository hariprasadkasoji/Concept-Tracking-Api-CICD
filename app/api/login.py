from app.core.oauth import oauth
from app.core.config import *
from fastapi import APIRouter, Request

login_route = APIRouter(prefix="/api")

@login_route.get("/login")
async def auth_login(request: Request):
    redirect_uri = f"{settings.API}/auth/callback"
    return await oauth.microsoft.authorize_redirect(
        request,
        redirect_uri,
    )