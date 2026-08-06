import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.core.sql_connection import db_client
from app.services.file_handler import save_file
from app.services import concept_queries as q
from app.utils.concept_helpers import (
    normalize_datetime,
    generate_concept_id,
    parse_concept_id,
    get_next_concept_id,
)
from app.core.authenticate import get_current_user
from app.services.pydantic_schemas import User

logger = logging.getLogger(__name__)

create_concept_route = APIRouter()

@create_concept_route.post("/api/create-concept")
async def create_or_update_concept(
    metadata: str = Form(...),
    concept_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    categories: List[str] = Form(default=[]),
    file_names: List[str] = Form(default=[]),
    file_sizes: List[int] = Form(default=[]),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id
    action = "Concept updated"

    # Values used to populate/refresh ConceptKeys - set on the create OR
    # update branch below, then consumed once in the "ensure key exists" block.
    current_concept_id = None
    key_client_code = None
    key_master_concept_id = None
    key_review_type = None
    key_claim_type = None
    key_edition = None
    key_version = None
    key_is_development = None
    key_run_number = None
    version_bumped = None
    previous_concept_id = None

    try:
        logger.info("API HIT: /api/create-concept user_id=%s", user_id)

        meta = json.loads(metadata)
        is_draft = int(meta.get("isDraft", meta.get("is_Draft", 0)))

        # concept_id can arrive as its own form field or nested in metadata -
        # the frontend sends both now; the standalone field wins if present,
        # otherwise fall back to metadata (covers older/alt payload shapes).
        concept_id = concept_id or meta.get("concept_id")

        with db_client() as conn:
            cursor = conn.cursor()

            # =====================================================
            # GENERATE CONCEPT ID - only when this is a genuine create.
            # clientName/masterConceptName/reviewType/claimType are ONLY
            # required here, not on every request - an update already
            # has concept_id and never sends these.
            # =====================================================
            if not concept_id:
                try:
                    clientName = meta["clientName"]
                    masterConceptName = meta["masterConceptName"]
                    reviewType = meta["reviewType"]
                    claimType = meta["claimType"]
                except KeyError as e:
                    logger.error(
                        "API FAILED: /api/create-concept missing required field=%s user_id=%s",
                        str(e), user_id
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing required field for a new concept: {e}"
                    )

                # -- DUPLICATE NAME CHECK --------------------------------
                incoming_name = (meta.get("conceptName") or "").strip().lower()
                if not incoming_name:
                    logger.error(
                        "API FAILED: /api/create-concept missing concept name user_id=%s",
                        user_id
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="Concept name is required."
                    )

                existing_name = q.find_duplicate_concept_name(cursor, incoming_name)
                if existing_name:
                    logger.error(
                        "API FAILED: /api/create-concept duplicate concept name=%s "
                        "existing=%s user_id=%s",
                        meta.get("conceptName"), existing_name, user_id
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"A concept named '{meta.get('conceptName')}' already exists "
                            f"({existing_name}). Please use a different name."
                        )
                    )

                # -- GENERATE CONCEPT ID (Edition) -----------------------
                base_prefix = f"{clientName}{masterConceptName}{reviewType}{claimType}"

                edition = q.get_next_edition_number(cursor, base_prefix)

                # Always create with the Development version D001, and a
                # starting run number of 001, appended.
                concept_id = generate_concept_id(
                    clientName, masterConceptName, reviewType, claimType,
                    edition, version=1, run=1, is_development=True
                )

                # -- DUPLICATE CONCEPT ID CHECK (race-condition guard) ---
                if q.concept_key_exists(cursor, concept_id):
                    logger.error(
                        "API FAILED: /api/create-concept concept_id race collision "
                        "concept_id=%s user_id=%s",
                        concept_id, user_id
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Concept ID {concept_id} was just created by another request. "
                            f"Please try submitting again."
                        )
                    )

                # CurrentConceptId starts equal to the anchor ConceptId at creation.
                current_concept_id = concept_id

                key_client_code = clientName
                key_master_concept_id = masterConceptName
                key_review_type = reviewType
                key_claim_type = claimType
                key_edition = edition
                key_version = 1
                key_is_development = 1
                key_run_number = 1

            else:
                # =====================================================
                # EXISTING CONCEPT - read the CURRENT display version from
                # ConceptKeys, compute the next one, and update ONLY
                # CurrentConceptId/Version/IsDevelopment. The anchor
                # `concept_id` is never touched - no FK risk.
                #
                # DEFENSIVE RESOLUTION: the frontend is supposed to always
                # send the stable anchor ConceptId, never the changing
                # CurrentConceptId. If a caller ever sends the display id
                # instead, resolve to the real anchor first so every
                # downstream query is guaranteed correct.
                # =====================================================
                row = q.fetch_concept_key_by_anchor(cursor, concept_id)

                if not row:
                    row = q.fetch_concept_key_by_current(cursor, concept_id)
                    if row:
                        logger.warning(
                            "create-concept: received display id %s instead of anchor - "
                            "resolved to anchor %s", concept_id, row[0]
                        )
                        concept_id = row[0]

                existing_current = row[1] if row and row[1] else concept_id
                previous_concept_id = existing_current

                if is_draft == 1:
                    # Every draft save AFTER the first one lands here too -
                    # the first "Save as Draft" click is what assigns
                    # concept_id in the first place, so every subsequent
                    # draft save for the SAME concept already has one and
                    # falls into this EXISTING CONCEPT branch. A draft is
                    # explicitly allowed to be re-saved any number of times
                    # while incomplete, and none of those re-saves are a
                    # real development milestone - only a genuine non-draft
                    # submit should ever advance the display version
                    # (…_D001 -> …_D002). Skip the bump logic entirely here.
                    current_concept_id = existing_current
                    version_bumped = False
                    parsed = parse_concept_id(current_concept_id)
                    key_version = parsed["version"]
                    key_is_development = 1 if parsed["is_development"] else 0

                else:
                    # PROMOTING A DRAFT -> FINAL CONCEPT is this concept_id's
                    # FIRST real (non-draft) submit: it already has a
                    # ConceptKeys row (assigned the moment the draft was
                    # first saved, which is why concept_id is already set
                    # here), but it has no row yet in the final Concepts
                    # table. That transition is not an edit of an
                    # already-finalized concept - there is no meaningful
                    # "previous final state" to diff specs/volume/dollars
                    # against - so it must never trigger a bump either.
                    is_promoting_draft = not q.concept_exists(cursor, concept_id)

                    if is_promoting_draft:
                        current_concept_id = existing_current
                        version_bumped = False
                        parsed = parse_concept_id(current_concept_id)
                        key_version = parsed["version"]
                        key_is_development = 1 if parsed["is_development"] else 0

                    else:
                        # old_volume, old_dollars = q.fetch_old_volume_dollars(cursor, concept_id)

                        # new_volume_raw = meta.get("estimatedVolume")
                        # new_dollars_raw = meta.get("estimatedDollars")
                        # new_dollars_parsed = (
                        #     float(str(new_dollars_raw).replace(",", ""))
                        #     if new_dollars_raw not in (None, "") else None
                        # )

                        spec_changed = "specs" in categories
                        # volume_changed = num_changed(old_volume, new_volume_raw)
                        # dollars_changed = num_changed(old_dollars, new_dollars_parsed)

                        # bump_dev_version = spec_changed or volume_changed or dollars_changed
                        bump_dev_version = spec_changed 

                        # -- RUN NUMBER: increments independently of the
                        # version bump above, any time a user with the Data
                        # Science Programmer role saves an update to an
                        # already-final concept. Never applies to drafts or
                        # to the draft->final promotion save.
                        is_ds_programmer = q.is_data_science_programmer_role(
                            cursor, current_user.role_id
                        )
                        bump_run_number = is_ds_programmer

                        current_concept_id = get_next_concept_id(
                            existing_current, meta.get("developmentStatus"),
                            bump_dev_version, bump_run_number
                        )
                        version_bumped = current_concept_id != existing_current

                        parsed = parse_concept_id(current_concept_id)
                        key_version = parsed["version"]
                        key_is_development = 1 if parsed["is_development"] else 0
                        key_run_number = parsed["run"]

                        if current_concept_id != existing_current:
                            q.update_concept_key_version(
                                cursor, concept_id, current_concept_id,
                                key_version, key_is_development, key_run_number
                            )
                            logger.info(
                                "UPDATE: concept version bumped concept_id=%s "
                                "previous=%s new=%s user_id=%s",
                                concept_id, existing_current, current_concept_id, user_id
                            )

            # =====================================================
            # ENSURE CONCEPT KEY EXISTS (anchor for all FKs)
            # =====================================================
            q.ensure_concept_key(
                cursor,
                concept_id, current_concept_id,
                key_client_code, key_master_concept_id,
                key_review_type, key_claim_type,
                key_edition, key_version, key_is_development, key_run_number
            )

            estimated_dollars = meta.get("estimatedDollars")
            if estimated_dollars:
                estimated_dollars = float(str(estimated_dollars).replace(",", ""))

            # =====================================================
            # DB WRITE - runs exactly once per request. Every submit
            # (with or without files) is a single call, so the metadata
            # write always happens exactly once, period.
            # =====================================================
            if is_draft == 1:
                if not q.draft_exists(cursor, concept_id):
                    q.insert_draft(cursor, concept_id, meta, estimated_dollars, user_id, normalize_datetime)
                    action = "Draft created"
                    logger.info(
                        "CREATE: draft created concept_id=%s user_id=%s",
                        concept_id, user_id
                    )
                else:
                    incoming_name = (meta.get("conceptName") or "").strip().lower()
                    if incoming_name:
                        existing_name = q.find_duplicate_concept_name_excluding(
                            cursor, incoming_name, concept_id
                        )
                        if existing_name:
                            logger.error(
                                "API FAILED: /api/create-concept duplicate concept name=%s "
                                "existing=%s concept_id=%s user_id=%s",
                                meta.get("conceptName"), existing_name, concept_id, user_id
                            )
                            raise HTTPException(
                                status_code=409,
                                detail=(
                                    f"A concept named '{meta.get('conceptName')}' already exists "
                                    f"({existing_name}). Please use a different name."
                                )
                            )
                    q.update_draft(cursor, concept_id, meta, estimated_dollars, user_id, normalize_datetime)
                    action = "Draft updated"
                    logger.info(
                        "UPDATE: draft updated concept_id=%s user_id=%s",
                        concept_id, user_id
                    )

            else:
                if not q.concept_exists(cursor, concept_id):
                    # PROMOTING A DRAFT -> FINAL CONCEPT (or a true
                    # brand-new submit that skipped the draft stage).
                    draft = q.fetch_draft_for_promotion(cursor, concept_id) or {}
                    draft_row = bool(draft)

                    def pick(meta_key: str, draft_key: str):
                        val = meta.get(meta_key)
                        if val is not None and str(val).strip() != "":
                            return val
                        return draft.get(draft_key)

                    concept_name = pick("conceptName", "ConceptName")

                    # -- DUPLICATE NAME CHECK ON PROMOTE/CREATE ------------------  # NEW
                    incoming_name = (concept_name or "").strip().lower()             # NEW
                    if incoming_name:                                                # NEW
                        existing_name = q.find_duplicate_concept_name_excluding(     # NEW
                            cursor, incoming_name, concept_id                        # NEW
                        )                                                             # NEW
                        if existing_name:                                            # NEW
                            logger.error(
                                "API FAILED: /api/create-concept duplicate concept name=%s "
                                "existing=%s concept_id=%s user_id=%s",
                                concept_name, existing_name, concept_id, user_id
                            )
                            raise HTTPException(                                     # NEW
                                status_code=409,                                      # NEW
                                detail=(                                              # NEW
                                    f"A concept named '{concept_name}' already exists "  # NEW
                                    f"({existing_name}). Please use a different name."   # NEW
                                )                                                      # NEW
                            )                                                          # NEW

                    development_status = pick("developmentStatus", "DevelopmentStatus")
                    priority = pick("priority", "Priority")
                    halo_number = pick("haloNumber", "HaloNumber")
                    internal_description = pick("InternalConceptDescription", "InternalConceptDescription")
                    estimated_volume = pick("estimatedVolume", "EstimatedVolume")
                    confidence_score = pick("confidenceScore", "ConfidenceScore")
                    ideation_requestor = pick("ideationRequestor", "IdeationRequestorId")
                    ds_programmer = pick("dataScienceProgrammer", "DataScienceProgrammerId")
                    previous_report_id = pick("previousReportId", "PreviousReportId")
                    qa_schedule = normalize_datetime(pick("qaSchedule", "QASchedule"))
                    production_schedule = normalize_datetime(pick("productionSchedule", "ProductionSchedule"))

                    if estimated_dollars is None:
                        estimated_dollars = draft.get("EstimatedDollars")

                    development_completed = meta.get(
                        "DevelopmentCompleted", draft.get("DevelopmentCompleted", 0)
                    )
                    client_approval_completed = meta.get(
                        "ClientApprovalCompleted", draft.get("ClientApprovalCompleted", 0)
                    )
                    supporting_documents_completed = meta.get(
                        "SupportingDocumentsCompleted", draft.get("SupportingDocumentsCompleted", 0)
                    )

                    q.insert_concept(
                        cursor, concept_id, concept_name, development_status, priority,
                        halo_number, internal_description, estimated_volume, estimated_dollars,
                        confidence_score, ideation_requestor, ds_programmer, previous_report_id,
                        qa_schedule, production_schedule, user_id,
                        development_completed, client_approval_completed, supporting_documents_completed,
                    )
                    action = "Concept submitted"
                    logger.info(
                        "CREATE: concept submitted concept_id=%s user_id=%s promoted_from_draft=%s",
                        concept_id, user_id, draft_row
                    )

                    if draft_row:
                        q.deactivate_draft(cursor, concept_id)

                else:
                    # -- DUPLICATE NAME CHECK ON UPDATE ------------------
                    incoming_name = (meta.get("conceptName") or "").strip().lower()
                    if incoming_name:
                        existing_name = q.find_duplicate_concept_name_excluding(
                            cursor, incoming_name, concept_id
                        )
                        if existing_name:
                            logger.error(
                                "API FAILED: /api/create-concept duplicate concept name=%s "
                                "existing=%s concept_id=%s user_id=%s",
                                meta.get("conceptName"), existing_name, concept_id, user_id
                            )
                            raise HTTPException(
                                status_code=409,
                                detail=(
                                    f"A concept named '{meta.get('conceptName')}' already exists "
                                    f"({existing_name}). Please use a different name."
                                )
                            )

                    q.update_concept(cursor, concept_id, meta, estimated_dollars, user_id, normalize_datetime)
                    action = "Concept updated"
                    logger.info(
                        "UPDATE: concept updated concept_id=%s user_id=%s",
                        concept_id, user_id
                    )

            # =====================================================
            # DEVELOPMENT NOTES
            # =====================================================
            development_notes = meta.get("developmentNotes", [])
            if development_notes:
                q.insert_development_notes(cursor, concept_id, development_notes, user_id, current_user.role_id)

            # =====================================================
            # SAVE ATTACHMENTS
            # =====================================================
            saved_files = []

            for i, upload in enumerate(files):
                category = categories[i] if i < len(categories) else "other"
                disp_name = file_names[i] if i < len(file_names) else upload.filename
                content = await upload.read()
                disp_size = file_sizes[i] if i < len(file_sizes) else len(content)

                saved_file = save_file(
                    concept_id=concept_id,
                    attachment_type=category,
                    file_name=disp_name,
                    content=content,
                )

                q.deactivate_attachment_by_filename(cursor, concept_id, category, saved_file["file_name"])
                version = q.get_next_attachment_version_by_filename(cursor, concept_id, category, saved_file["file_name"])
                q.insert_attachment(
                    cursor, concept_id, category, saved_file["file_name"],
                    saved_file["file_path"], disp_size, user_id, version
                )

                saved_files.append({**saved_file, "category": category, "version": version})

                logger.info(
                    "CREATE: attachment saved concept_id=%s category=%s file_name=%s "
                    "version=%s user_id=%s",
                    concept_id, category, saved_file["file_name"], version, user_id
                )

            conn.commit()
            logger.info(
                "INSERT SUCCESS: action=%s concept_id=%s current_concept_id=%s user_id=%s",
                action, concept_id, current_concept_id, user_id
            )

            return {
                "success": True,
                "message": action,
                "concept_id": concept_id,
                "current_concept_id": current_concept_id,
                "previous_concept_id": previous_concept_id,
                "version_updated": version_bumped,
                "files": saved_files,
            }

    except HTTPException as e:
        logger.error(
            "API FAILED: /api/create-concept status=%s detail=%s concept_id=%s user_id=%s",
            e.status_code, e.detail, concept_id, user_id
        )
        raise
    except Exception as e:
        # NOTE: no conn.rollback() here anymore - db_client() now rolls back
        # (and, if that fails, discards + replaces the connection) internally
        # before the connection is ever returned to the pool. Rolling back a
        # second time here, on a connection that may have already been
        # recycled or closed by db_client(), is what caused connections to
        # leak into the pool mid-transaction and get shared across concurrent
        # requests - the root cause of the intermittent "Fail to Refresh" /
        # phantom duplicate-name errors and the eventual pool hang.
        logger.error(
            "API FAILED: /api/create-concept concept_id=%s user_id=%s error=%s",
            concept_id, user_id, str(e), exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))