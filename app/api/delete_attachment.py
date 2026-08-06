import logging
from fastapi import APIRouter, Form, HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q
from app.utils.concept_helpers import resolve_concept_id

logger = logging.getLogger(__name__)

delete_route = APIRouter()

@delete_route.post("/api/delete-attachment")
async def delete_attachment(
    concept_id: str = Form(...),
    attachment_id: int = Form(...),
    category: str = Form(...),
    user_id: int = Form(...)
):
    logger.info(
        "[API HIT] POST /api/delete-attachment concept_id=%s attachment_id=%s user_id=%s",
        concept_id, attachment_id, user_id
    )

    try:
        with db_client() as conn:
            cursor = conn.cursor()

            concept_id = resolve_concept_id(cursor, concept_id)

            row = q.fetch_attachment_for_delete(cursor, attachment_id, concept_id, category)

            if not row:
                logger.warning(
                    "API FAILED: delete-attachment not found concept_id=%s attachment_id=%s "
                    "category=%s user_id=%s",
                    concept_id, attachment_id, category, user_id
                )
                raise HTTPException(
                    status_code=404,
                    detail="Attachment not found."
                )

            q.soft_delete_attachment(cursor, attachment_id, user_id)

            conn.commit()

        logger.info(
            "UPDATE: attachment soft-deleted concept_id=%s attachment_id=%s category=%s user_id=%s",
            concept_id, attachment_id, category, user_id
        )

        return {
            "success": True,
            "message": "Attachment deleted successfully."
        }

    except HTTPException as e:
        if e.status_code != 404:
            logger.error(
                "API FAILED: delete-attachment status=%s detail=%s concept_id=%s "
                "attachment_id=%s user_id=%s",
                e.status_code, e.detail, concept_id, attachment_id, user_id
            )
        raise

    except Exception as e:
        logger.error(
            "API FAILED: delete-attachment concept_id=%s attachment_id=%s user_id=%s error=%s",
            concept_id, attachment_id, user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))