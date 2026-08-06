import logging
import mimetypes
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.sql_connection import db_client
from app.services import concept_queries as q

download_route = APIRouter()

logger = logging.getLogger(__name__)

@download_route.post("/api/download-attachment/{attachment_id}")
async def download_attachment(attachment_id: int):
    logger.info("[API HIT] POST /api/download-attachment/%s", attachment_id)

    try:
        with db_client() as conn:
            cursor = conn.cursor()
            row = q.fetch_attachment_file(cursor, attachment_id)

            if not row:
                logger.warning(
                    "API FAILED: download-attachment not found attachment_id=%s",
                    attachment_id
                )
                raise HTTPException(status_code=404, detail="Attachment not found")

            file_name, file_path = row[0], row[1]

        normalized_path = os.path.normpath(file_path)

        if not os.path.isfile(normalized_path):
            logger.warning(
                "API FAILED: download-attachment file missing on disk attachment_id=%s path=%s",
                attachment_id, normalized_path
            )
            raise HTTPException(status_code=404, detail="File not found on disk")

        mime_type, _ = mimetypes.guess_type(normalized_path)
        mime_type = mime_type or "application/octet-stream"

        def file_iterator():
            with open(normalized_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        logger.info(
            "[DOWNLOAD SUCCESS] attachment_id=%s file_name=%s",
            attachment_id, file_name
        )

        return StreamingResponse(
            file_iterator(),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Accept-Ranges": "bytes"
            }
        )

    except HTTPException as e:
        if e.status_code != 404:
            logger.error(
                "API FAILED: download-attachment status=%s detail=%s attachment_id=%s",
                e.status_code, e.detail, attachment_id
            )
        raise
    except Exception as e:
        logger.error(
            "API FAILED: download-attachment attachment_id=%s error=%s",
            attachment_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")