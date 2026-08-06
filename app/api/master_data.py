import logging
from fastapi import APIRouter, HTTPException
from app.core.sql_connection import db_client
from app.services import concept_queries as q

logger = logging.getLogger(__name__)

master_data_route = APIRouter()


@master_data_route.get("/api/master-data")
def get_master_data():
    logger.info("[API HIT] GET /api/master-data")
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            data = q.fetch_master_data(cursor)
            logger.info("[FETCH SUCCESS] GET /api/master-data")
            return {
                "success": True,
                "data": data
            }
    except Exception as e:
        logger.error(
            "API FAILED: GET /api/master-data error=%s",
            str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))