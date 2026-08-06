import logging
from fastapi import APIRouter, HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q

logger = logging.getLogger(__name__)

concepts_by_user_id_route = APIRouter()

@concepts_by_user_id_route.get("/api/Concept/{user_id}")
def get_concepts_by_user_id(user_id: int):
    logger.info("[API HIT] GET /api/Concept/%s", user_id)
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            result = q.fetch_concepts_by_user(cursor, user_id)
            logger.info(
                "[FETCH SUCCESS] GET /api/Concept/%s returned %s record(s)",
                user_id, len(result) if result is not None else 0
            )
            return result
    except Exception as e:
        logger.error(
            "API FAILED: GET /api/Concept/%s error=%s",
            user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))