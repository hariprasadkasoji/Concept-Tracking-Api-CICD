import logging
from fastapi import APIRouter, HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q

logger = logging.getLogger(__name__)

updates_route = APIRouter()

# fetch all concept and also draft -- load latest update section
@updates_route.get("/api/latest-updates")
def get_latest_updates():
    """
    Feeds the 'Latest Updates' panel on the Concept Development page.
    Unlike /api/dashboard-concepts (which only reads the Concepts table),
    this UNIONs in active ConceptDrafts too, so concepts saved as a
    draft actually show up here instead of silently disappearing until
    they're finally submitted.
    """
    logger.info("[API HIT] GET /api/latest-updates")
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            data = q.fetch_latest_updates(cursor)
            logger.info(
                "[FETCH SUCCESS] GET /api/latest-updates returned %s record(s)",
                len(data)
            )
            return {
                "success": True,
                "count": len(data),
                "data": data
            }
    except Exception as e:
        logger.error(
            "API FAILED: GET /api/latest-updates error=%s",
            str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))