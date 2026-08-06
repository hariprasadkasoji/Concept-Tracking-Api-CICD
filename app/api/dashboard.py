import logging
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from app.core.sql_connection import db_client
from app.services import concept_queries as q
from app.services.pydantic_schemas import DashboardRequest
from app.services.dataframe_utils import apply_filters_on_df, apply_quick_search, apply_sort_on_df, coerce_date_columns, infer_column_metadata
from app.services.dataframe_utils import FILTER_OPERATIONS  # reuse the same op map

logger = logging.getLogger(__name__)

dashboard_route = APIRouter()


@dashboard_route.post("/api/dashboard-concepts")
def get_all_concepts(request: DashboardRequest):
    try:
        with db_client() as conn:
            cursor = conn.cursor()
            data = q.fetch_dashboard_concepts(cursor)

        total_raw = len(data)
        stats = {
            "totalConcepts": total_raw,
            "newConcepts": sum(1 for r in data if r.get("Development Status") == "Programming Queue"), #new
            "conceptsInProgress": sum(1 for r in data if r.get("Development Status") in
                                       ["Programming", "Researching", "QA Revise", "Client Revise"]), # 
            "pendingApprovals": sum(1 for r in data if r.get("Development Status") in
                                     ["Approved", "Client Review", "Client Resubmit"]),
            "qaScheduled": sum(1 for r in data if r.get("Development Status") in ["Result Set QA"]),
            "productionReady": sum(1 for r in data if r.get("Development Status") in
                                    ["Client Approved", "Pre-Production", "Production"]),
        }

        if not data:
            return {"stats": stats, "columns": [], "data": [], "totalCount": 0,
                     "page": request.page, "page_size": request.page_size, "error": ""}

        df = pd.DataFrame(data)
        df = coerce_date_columns(df, date_column_names={"Created Date", "Updated Date"})
        # Apply AG Grid filter/sort model
        df = apply_filters_on_df(df, request.filterModel or {})
        df = apply_quick_search(df, request.quickSearch)
        df = apply_sort_on_df(df, request.sortmodel if hasattr(request, "sortmodel") else request.sortModel)

        total_count = len(df)

        # Paginate after filter/sort
        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        page_df = df.iloc[start:end].copy()
        page_df = page_df.replace([np.nan, np.inf, -np.inf], None)

        columns = [
            {"field": col, "headerName": col.replace("_", " ")}
            for col in df.columns
        ]
        column_metadata = infer_column_metadata(df, FILTER_OPERATIONS)

        return {
            "stats": stats,
            "columns": columns,
            "columnMetadata": column_metadata,
            "data": jsonable_encoder(page_df.to_dict(orient="records")),
            "page": request.page,
            "page_size": request.page_size,
            "totalCount": total_count,
            "error": ""
        }

    except Exception as e:
        logger.error("Error in get_all_concepts: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))