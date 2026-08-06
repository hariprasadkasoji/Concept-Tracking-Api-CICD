import logging
import os
from fastapi import APIRouter, HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q
from app.services.users import get_user_files

logger = logging.getLogger(__name__)

users_route = APIRouter()

# # =====================================================================
# # CONFIGURABLE BASE PATH
# # Change this to point at the shared network root.
# # Examples seen in your snippet:
# #   r"\\172.19.20.15\Networkshare"
# #   r"\\172.19.31.8\Network\sharedfolder"
# # =====================================================================
# # USER_FILES_BASE_PATH = r"\\172.19.20.15\Networkshare"
# USER_FILES_BASE_PATH = r"\\172.19.20.15"


# def get_user_files(user_id: int, base_path: str = USER_FILES_BASE_PATH):
#     """
#     Fetch the list of files (name, full path, size) for a given user_id.

#     Looks up the user's name from the `users` table, builds their folder
#     path as `base_path/<user_name>`, and lists files in that folder.

#     Args:
#         user_id: The user's ID, looked up in the users table.
#         base_path: Root folder under which each user has a subfolder
#                     named after them. Configurable per call, defaults
#                     to USER_FILES_BASE_PATH.

#     Returns:
#         dict: {
#             "user_id": int,
#             "user_name": str,
#             "folder_path": str,
#             "files": [
#                 {"file_name": str, "file_path": str, "file_size": int},
#                 ...
#             ]
#         }

#     Raises:
#         ValueError: if the user_id is not found in the users table.
#         FileNotFoundError: if the resolved folder path does not exist.
#     """
#     with db_client() as conn:
#         cursor = conn.cursor()
#         user_name = q.fetch_user_name(cursor, user_id)

#         if not user_name:
#             raise ValueError(f"No user found with id={user_id}")

#     folder_path = os.path.normpath(os.path.join(base_path, user_name))

#     if not os.path.isdir(folder_path):
#         raise FileNotFoundError(f"Folder not found: {folder_path}")

#     files = []

#     for entry in os.listdir(folder_path):
#         full_path = os.path.join(folder_path, entry)

#         if os.path.isfile(full_path):
#             files.append({
#                 "file_name": entry,
#                 "file_path": full_path,
#                 "file_size": os.path.getsize(full_path)
#             })

#     return {
#         "user_id": user_id,
#         "user_name": user_name,
#         "folder_path": folder_path,
#         "files": files
#     }


@users_route.get("/api/user-files/{user_id}")
def list_user_files(user_id: int):
    try:
        result = get_user_files(user_id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("[USER FILES ERROR]")
        raise HTTPException(status_code=500, detail=str(e))
