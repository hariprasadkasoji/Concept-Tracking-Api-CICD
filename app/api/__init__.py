from app.api.login import login_route as login_router
from app.api.auth_callback import auth_callback_route as auth_callback_router
from app.api.users import users_route as users_router
from app.api.create_concept import create_concept_route as create_concept_router
from app.api.concepts import concepts_route as concepts_router
from app.api.concept_by_user import concepts_by_user_id_route as concepts_by_user_router
from app.api.master_data import master_data_route as master_data_router
from app.api.latest_updates import updates_route as latest_updates_router
from app.api.upload_supporting_docs import upload_router as upload_supporting_docs_router
from app.api.clients_approval import create_client_approval_route as clients_approval_router
from app.api.status import status_route as status_router
from app.api.dashboard import dashboard_route as dashboard_router
from app.api.download_attachment import download_route as download_attachment_router
from app.api.delete_attachment import delete_route as delete_attachment_router
from app.api.role_router import role_router as role_router
from app.api.user_management import user_management_route
from app.api.master_data_management import master_data_management_route 




