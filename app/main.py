import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi_proxiedheadersmiddleware import ProxiedHeadersMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.sql_connection import init_pool, close_pool
from app.core.logger_config import setup_logging
from app.api import *
from version import APP_VERSION, BUILD_SHA, BUILD_DATE, BUILD_BRANCH




def handle_exception(loop, context):
    exc = context.get('exception')
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_hander(context)


# ---------------- Logging Configuration ----------------
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # ---- DB ----
        loop=asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)
        init_pool()
        logger.info("[Startup] app id: %s", id(app))
        logger.info("[Start]")

    except Exception as e:
        logger.critical(f"[Startup] Failed: {e}")

    yield

    close_pool()
    logger.info("[Shutdown] Cleanup complete.")


app = FastAPI(lifespan=lifespan)

# origins = ["http://localhost:4200"]
origins = ["*"]

app.add_middleware(ProxiedHeadersMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET, same_site="lax", https_only=True)
app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,            # Allows specific origins
    allow_credentials=True,          # Allows cookies/auth headers
    allow_methods=["*"],              # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],              # Allows all headers
    allow_origins=origins,  # allows all origins
)

@app.get("/version")
def version():
    return {
        "version": APP_VERSION,
        "sha": BUILD_SHA,
        "date": BUILD_DATE,
        "branch": BUILD_BRANCH,
    }



#  Auth
app.include_router(login_router, tags=["LOGIN"])
app.include_router(auth_callback_router, tags=["Auth"])
app.include_router(role_router, tags=["Role"])


#  Dashboard
app.include_router(dashboard_router, tags=["Dashboard"])

#  Concepts
app.include_router(create_concept_router, tags=["Create Concept"])
app.include_router(concepts_router, tags=["Concepts"])
app.include_router(concepts_by_user_router, tags=["Concepts by User"])
app.include_router(master_data_router, tags=["Master Data"])
app.include_router(latest_updates_router, tags=["Latest Updates"])

#  Client Approval
app.include_router(clients_approval_router, tags=["Client Approval"])

#  Attachments
app.include_router(upload_supporting_docs_router, tags=["Attachments"])
app.include_router(download_attachment_router, tags=["Download Attachment"])
app.include_router(delete_attachment_router, tags=["Delete Attachment"])

#  Users
app.include_router(users_router, tags=["Users"])
app.include_router(user_management_route, tags=["User Management"])
app.include_router(master_data_management_route, tags=["Master Data Management"])


#  Status
app.include_router(status_router, tags=["Status"])
