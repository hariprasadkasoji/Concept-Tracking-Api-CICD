import logging
from fastapi import APIRouter,HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q
from app.utils.concept_helpers import resolve_concept_id

logger = logging.getLogger(__name__)

concepts_route = APIRouter()


@concepts_route.get("/api/concepts/{concept_id}")
def get_concept(concept_id: str):
    logger.info("[API HIT] GET /api/concepts/%s", concept_id)
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            concept_id = resolve_concept_id(cursor, concept_id)

            concept = q.fetch_concept_main_row(cursor, concept_id)
            if not concept:
                logger.warning(
                    "API FAILED: GET /api/concepts/%s not found", concept_id
                )
                raise HTTPException(status_code=404, detail="Concept not found")

            # Use the resolved anchor ConceptId (not the path param) for
            # every subsequent lookup below - attachments, notes, and
            # approvals are all keyed on the anchor, never the display ID.
            resolved_concept_id = concept["ConceptId"]

            client_approvals = q.fetch_client_approvals(cursor, resolved_concept_id)
            development_notes = q.fetch_development_notes(cursor, resolved_concept_id)
            active_files = q.fetch_active_attachments(cursor, resolved_concept_id)
            file_history = q.fetch_attachment_history(cursor, resolved_concept_id)

            logger.info(
                "[FETCH SUCCESS] GET /api/concepts/%s resolved_concept_id=%s",
                concept_id, resolved_concept_id
            )

            return {
                "success": True,
                "concept": concept,
                "client_approvals": client_approvals,
                "development_notes": development_notes,
                "active_files": active_files,
                "file_history": file_history
            }

    except HTTPException as e:
        if e.status_code != 404:
            logger.error(
                "API FAILED: GET /api/concepts/%s status=%s detail=%s",
                concept_id, e.status_code, e.detail
            )
        raise
    except Exception as e:
        logger.error(
            "API FAILED: GET /api/concepts/%s error=%s",
            concept_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))