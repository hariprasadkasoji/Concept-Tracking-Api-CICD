import json
import logging
from typing import List
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.core.sql_connection import db_client
from app.services.file_handler import save_file
from app.services import concept_queries as q
from app.utils.concept_helpers import resolve_concept_id

logger = logging.getLogger(__name__)

upload_router = APIRouter()

@upload_router.post("/api/upload_supporting_docs")
async def upload_supporting_docs(
    concept_id: str = Form(...),
    metadata: str = Form(...),
    category: str = Form(...),
    user_id: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    doc_indices: List[str] = Form(default=[]),
    doc_names: List[str] = Form(default=[]),
    source_urls: List[str] = Form(default=[]),
    file_names: List[str] = Form(default=[]),
    file_sizes: List[int] = Form(default=[]),
):
    logger.info(
        "[API HIT] POST /api/upload_supporting_docs concept_id=%s category=%s user_id=%s",
        concept_id, category, user_id
    )

    try:
        meta = json.loads(metadata)
        supporting_completed = meta.get("SupportingDocumentsCompleted", 0)
        supporting_docs = meta.get("supportingDocs", [])

        # doc_indices (Form field, one per uploaded file) already carries the
        # STABLE docIndex from the frontend - matches doc.docIndex, not the
        # file's position among `files`.
        file_pos_by_doc_index = {
            int(doc_idx): i for i, doc_idx in enumerate(doc_indices)
        }

        with db_client() as conn:
            cursor = conn.cursor()

            # resolve whatever ID came in (anchor OR CurrentConceptId)
            # to the anchor ConceptId, and use it for every query below.
            concept_id = resolve_concept_id(cursor, concept_id)

            results = []

            # Iterate the docs as given, using EACH DOC'S OWN docIndex
            # field (sent explicitly by the frontend) instead of array
            # position, which is unstable once a doc is deleted.
            for doc in supporting_docs:
                doc_index = doc.get("docIndex")

                if doc_index is None:
                    logger.warning(
                        "upload_supporting_docs: doc missing docIndex, skipping: %s",
                        doc
                    )
                    continue

                doc_index = int(doc_index)

                doc_name = doc.get("name")
                source_url = doc.get("sourceurl")

                file_pos = file_pos_by_doc_index.get(doc_index)

                if file_pos is None:
                    if not source_url:
                        continue

                    # file_pos is None only means "no *new* file was
                    # attached in THIS request" for this doc_index - it
                    # does NOT mean the doc has no file. Carry forward the
                    # existing active file's FileName/FilePath/FileSize so
                    # we only create a genuinely new "URL-only" version
                    # when the doc never had a file to begin with.
                    existing = q.fetch_active_supporting_attachment(cursor, concept_id, category, doc_index)
                    existing_file_name = existing[0] if existing else None
                    existing_file_path = existing[1] if existing else None
                    existing_file_size = existing[2] if existing else None

                    q.deactivate_attachment_by_doc_index(cursor, concept_id, category, doc_index)
                    version = q.get_next_attachment_version_by_doc_index(cursor, concept_id, category, doc_index)
                    q.insert_supporting_attachment(
                        cursor, concept_id, category, doc_index, doc_name,
                        existing_file_name, existing_file_path, existing_file_size,
                        source_url, user_id, version
                    )

                    if existing_file_name:
                        logger.info(
                            "UPDATE: supporting document metadata updated concept_id=%s "
                            "category=%s doc_index=%s version=%s user_id=%s",
                            concept_id, category, doc_index, version, user_id
                        )
                    else:
                        logger.info(
                            "CREATE: supporting document recorded (URL only) concept_id=%s "
                            "category=%s doc_index=%s version=%s user_id=%s",
                            concept_id, category, doc_index, version, user_id
                        )

                    results.append({
                        "doc_index": doc_index,
                        "message": (
                            "Supporting document metadata updated"
                            if existing_file_name else
                            "Supporting document recorded (URL only)"
                        )
                    })
                    continue

                upload = files[file_pos]
                disp_name = file_names[file_pos] if file_pos < len(file_names) else upload.filename
                content = await upload.read()
                disp_size = file_sizes[file_pos] if file_pos < len(file_sizes) else len(content)

                saved_file = save_file(
                    concept_id=concept_id,
                    attachment_type=category,
                    file_name=disp_name,
                    content=content,
                )

                q.deactivate_attachment_by_doc_index(cursor, concept_id, category, doc_index)
                version = q.get_next_attachment_version_by_doc_index(cursor, concept_id, category, doc_index)
                q.insert_supporting_attachment(
                    cursor, concept_id, category, doc_index, doc_name,
                    saved_file["file_name"], saved_file["file_path"],
                    disp_size, source_url, user_id, version
                )

                action = "CREATE" if version == 1 else "UPDATE"
                logger.info(
                    "%s: supporting document uploaded concept_id=%s category=%s doc_index=%s "
                    "file_name=%s version=%s user_id=%s",
                    action, concept_id, category, doc_index,
                    saved_file["file_name"], version, user_id
                )

                results.append({
                    "doc_index": doc_index,
                    "message": "Supporting document uploaded",
                    "file": saved_file,
                    "version": version
                })

            q.update_concept_supporting_docs_flag(cursor, concept_id, supporting_completed)
            current_concept_id = q.fetch_current_concept_id(cursor, concept_id) or concept_id

            conn.commit()

            logger.info(
                "[UPLOAD SUPPORTING DOCS SUCCESS] concept_id=%s category=%s docs_processed=%s user_id=%s",
                concept_id, category, len(results), user_id
            )

            return {
                "success": True,
                "concept_id": concept_id,
                "current_concept_id": current_concept_id,
                "results": results
            }

    except HTTPException as e:
        logger.error(
            "API FAILED: upload_supporting_docs status=%s detail=%s concept_id=%s "
            "category=%s user_id=%s",
            e.status_code, e.detail, concept_id, category, user_id
        )
        raise
    except Exception as e:
        logger.error(
            "API FAILED: upload_supporting_docs concept_id=%s category=%s user_id=%s error=%s",
            concept_id, category, user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))