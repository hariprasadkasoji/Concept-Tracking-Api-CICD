import json
import logging
from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.core.sql_connection import db_client
from app.services.file_handler import save_file
from app.services import concept_queries as q   
from app.utils.concept_helpers import num_changed, resolve_concept_id

logger = logging.getLogger(__name__)

create_client_approval_route = APIRouter()


@create_client_approval_route.post("/api/submit_client_approval")
async def create_client_approval(
    data: str = Form(...),
    user_id: str = Form(...),
    concept_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    categories: List[str] = Form(default=[]),
    file_names: List[str] = Form(default=[]),
    file_sizes: List[str] = Form(default=[]),
):
    logger.info("[API HIT] POST /api/submit_client_approval user_id=%s", user_id)

    conceptId = concept_id

    try:
        try:
            meta = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(
                "[CLIENT APPROVAL FAILED] invalid JSON payload user_id=%s error=%s",
                user_id, str(e)
            )
            raise HTTPException(status_code=400, detail="Invalid JSON payload for 'data'.")

        try:
            conceptId = meta['conceptId']
            conceptId = concept_id or conceptId

            conceptname = meta['conceptname']
            clientConceptName = meta['clientConceptName']
            clientConceptDescription = meta['clientConceptDescription']
            clientApprovalStatus = meta['clientApprovalStatus']
            submittedToClientOn = meta['submittedToClientOn']
            clientApprovalNotes = meta['clientApprovalNotes']
            estimatedVolume = meta['estimatedVolume']
            clientApprovalCompleted = meta['clientApprovalCompleted']
        except KeyError as e:
            logger.error(
                "[CLIENT APPROVAL FAILED] missing required field=%s user_id=%s",
                str(e), user_id
            )
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field for client approval: {e}"
            )

        estimated_dollars = meta.get('estimatedDollars')
        if estimated_dollars:
            estimated_dollars = float(str(estimated_dollars).replace(",", ""))

        # Approvedby is whoever is actually submitting this approval right
        # now - the authenticated user_id on the request - not a value
        # trusted from the JSON body.
        Approvedby = user_id

        logger.info("[CLIENT APPROVAL] Processing ConceptId=%s user_id=%s", conceptId, user_id)

        with db_client() as conn:
            cursor = conn.cursor()

            # Resolve whatever ID came in (anchor OR CurrentConceptId) down
            # to the anchor ConceptId - every table below is keyed on the
            # anchor, not the display version.
            conceptId = resolve_concept_id(cursor, conceptId)

            # STEP 1-2: CHECK/DEACTIVATE EXISTING ACTIVE RECORD
            existing_approval_id = q.fetch_active_client_approval_id(cursor, conceptId)
            is_update = existing_approval_id is not None

            if is_update:
                q.deactivate_client_approval(cursor, conceptId)

            # STEP 3: INSERT NEW ACTIVE RECORD
            q.insert_client_approval(
                cursor, conceptId, conceptname, clientConceptName, clientConceptDescription,
                clientApprovalStatus, submittedToClientOn, clientApprovalNotes,
                estimatedVolume, estimated_dollars, Approvedby
            )

            if is_update:
                logger.info(
                    "UPDATE: client approval updated concept_id=%s previous_approval_id=%s user_id=%s",
                    conceptId, existing_approval_id, user_id
                )
            else:
                logger.info(
                    "CREATE: client approval created concept_id=%s user_id=%s",
                    conceptId, user_id
                )

            # STEP 4: UPDATE CONCEPT TABLE - completion flag, and keep
            # EstimatedVolume / EstimatedDollars on the Concepts row in
            # sync whenever the client-approval submission changed them.
            old_volume, old_dollars = q.fetch_concept_volume_dollars(cursor, conceptId)

            volume_changed = num_changed(old_volume, estimatedVolume)
            dollars_changed = num_changed(old_dollars, estimated_dollars)

            if volume_changed or dollars_changed:
                q.sync_concept_volume_dollars_and_approval_flag(
                    cursor, conceptId,
                    estimatedVolume if volume_changed else None,
                    estimated_dollars if dollars_changed else None,
                    clientApprovalCompleted
                )
                logger.info(
                    "UPDATE: Synced Concepts.EstimatedVolume/EstimatedDollars "
                    "for ConceptId=%s (volume_changed=%s, dollars_changed=%s) user_id=%s",
                    conceptId, volume_changed, dollars_changed, user_id
                )
            else:
                q.update_concept_client_approval_flag(cursor, conceptId, clientApprovalCompleted)

            # STEP 5: SAVE CLIENT APPROVAL ATTACHMENTS
            saved_files = []

            for i, upload in enumerate(files):
                category = categories[i] if i < len(categories) else "approval"
                disp_name = file_names[i] if i < len(file_names) else upload.filename
                content = await upload.read()
                disp_size = file_sizes[i] if i < len(file_sizes) else len(content)

                saved_file = save_file(
                    concept_id=conceptId,
                    attachment_type=category,
                    file_name=disp_name,
                    content=content,
                )

                q.deactivate_attachment_by_filename(cursor, conceptId, category, saved_file["file_name"])
                version = q.get_next_attachment_version_by_filename(cursor, conceptId, category, saved_file["file_name"])
                q.insert_attachment(
                    cursor, conceptId, category, saved_file["file_name"],
                    saved_file["file_path"], disp_size, user_id, version
                )

                saved_files.append({**saved_file, "category": category, "version": version})

                logger.info(
                    "CREATE: client approval attachment saved concept_id=%s category=%s "
                    "file_name=%s version=%s user_id=%s",
                    conceptId, category, saved_file["file_name"], version, user_id
                )

            # STEP 6: FETCH CurrentConceptId FOR RESPONSE
            current_concept_id = q.fetch_current_concept_id(cursor, conceptId) or conceptId

            conn.commit()

        logger.info(
            "[CLIENT APPROVAL SUCCESS] action=%s ConceptId=%s, AttachmentsSaved=%s user_id=%s",
            "UPDATE" if is_update else "CREATE", conceptId, len(saved_files), user_id
        )

        return {
            "success": True,
            "message": "Client Approval submitted successfully",
            "concept_id": conceptId,
            "current_concept_id": current_concept_id,
            "files": saved_files
        }

    except HTTPException as e:
        logger.error(
            "[CLIENT APPROVAL FAILED] status=%s detail=%s concept_id=%s user_id=%s",
            e.status_code, e.detail, conceptId, user_id
        )
        raise
    except Exception as e:
        logger.error(
            "[CLIENT APPROVAL FAILED] concept_id=%s user_id=%s error=%s",
            conceptId, user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))