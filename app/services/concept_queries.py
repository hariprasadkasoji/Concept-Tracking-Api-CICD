from typing import Optional, List, Dict, Any
from app.core.config import settings

# =====================================================================
# DASHBOARD
# =====================================================================

def fetch_dashboard_concepts(cursor) -> List[Dict[str, Any]]:
    """Concepts joined with their current display id and requestor/programmer names."""
    cursor.execute(f"""
        SELECT
            c.ConceptName AS [Concept Name],
            ck.CurrentConceptId AS [Concept_Id],
            c.DevelopmentStatus AS [Development Status],
            u1.Name AS [Ideation Requestor],
            u2.Name AS [Data Science Programmer],
            c.CreatedDate AS [Created Date]
        FROM {settings.CONCEPTS} c
        LEFT JOIN {settings.USERS} u1
            ON c.IdeationRequestorId = u1.Id
        LEFT JOIN {settings.USERS} u2
            ON c.DataScienceProgrammerId = u2.Id
        LEFT JOIN {settings.CONCEPT_KEYS} ck
            ON ck.ConceptId = c.ConceptId
        ORDER BY c.CreatedDate DESC;
    """)
    rows = cursor.fetchall()
    col_names = [col[0] for col in cursor.description]
    return [dict(zip(col_names, row)) for row in rows]


# =====================================================================
# MASTER DATA
# =====================================================================

def fetch_development_status(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT id, value
        FROM {settings.DEVELOPMENT_STATUS}
        ORDER BY created_date
    """)
    return [{"id": row.id, "value": row.value} for row in cursor.fetchall()]


def fetch_priority_status(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT id, value
        FROM {settings.PRIORITY_STATUS}
        ORDER BY created_date
    """)
    return [{"id": row.id, "value": row.value} for row in cursor.fetchall()]


def fetch_clients(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT client_id, client_name
        FROM {settings.CLIENTS}
        WHERE active = 1
        ORDER BY client_name
    """)
    return [{"client_id": row.client_id, "client_name": row.client_name} for row in cursor.fetchall()]


def fetch_master_concepts(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT master_id, concept_name
        FROM {settings.MASTER_CONCEPTS}
        WHERE active = 1
        ORDER BY createddate
    """)
    return [{"master_id": row.master_id, "concept_name": row.concept_name} for row in cursor.fetchall()]


def fetch_review_types(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT review_type, description
        FROM {settings.REVIEW_TYPE}
        WHERE active = 1
        ORDER BY review_type
    """)
    return [{"review_type": row.review_type, "description": row.description} for row in cursor.fetchall()]


def fetch_claim_types(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT claim_type, description
        FROM {settings.CLAIM_TYPE}
        WHERE active = 1
        ORDER BY claim_type
    """)
    return [{"claim_type": row.claim_type, "description": row.description} for row in cursor.fetchall()]


def fetch_ideation_requestors(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT DISTINCT
            u.id,
            u.username,
            u.name,
            ur.role_name
        FROM {settings.USERS} u
        INNER JOIN {settings.USER_ACCESS} ua
            ON u.id = ua.user_id
        INNER JOIN {settings.USER_ROLE} ur
            ON ua.role_id = ur.role_id
        WHERE u.is_active = 1
        AND ur.role_name = 'Ideation Requestor'
        ORDER BY u.name
    """)
    return [{"id": row.id, "name": row.name, "role_name": row.role_name} for row in cursor.fetchall()]


def fetch_datascience_programmers(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT DISTINCT
            u.id,
            u.username,
            u.name,
            ur.role_name
        FROM {settings.USERS} u
        INNER JOIN {settings.USER_ACCESS} ua
            ON u.id = ua.user_id
        INNER JOIN {settings.USER_ROLE} ur
            ON ua.role_id = ur.role_id
        WHERE u.is_active = 1
        AND ur.role_name = 'Data Science Programmer'
        ORDER BY u.name
    """)
    return [{"id": row.id, "name": row.name, "role_name": row.role_name} for row in cursor.fetchall()]


def fetch_client_approval_status(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT id, value
        FROM {settings.CLIENT_APPROVAL_STATUS}
        ORDER BY created_date
    """)
    return [{"id": row.id, "value": row.value} for row in cursor.fetchall()]


def fetch_master_data(cursor) -> Dict[str, Any]:
    """Bundles every master-data lookup into a single dict, in original response order."""
    return {
        "development_status": fetch_development_status(cursor),
        "priority_status": fetch_priority_status(cursor),
        "clients": fetch_clients(cursor),
        "master_concepts": fetch_master_concepts(cursor),
        "review_types": fetch_review_types(cursor),
        "claim_types": fetch_claim_types(cursor),
        "ideation_requestors": fetch_ideation_requestors(cursor),
        "datascience_programmers": fetch_datascience_programmers(cursor),
        "ClientApproval_status": fetch_client_approval_status(cursor),
    }


# =====================================================================
# CONCEPTS BY USER
# =====================================================================

def fetch_concepts_by_user(cursor, user_id: int) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT
            c.ConceptId,
            ck.CurrentConceptId,
            c.ConceptName,
            c.DevelopmentStatus,
            c.CreatedDate,
            c.Createdby,
            'CONCEPT' AS RecordType
        FROM {settings.CONCEPTS} c
        LEFT JOIN {settings.CONCEPT_KEYS} ck ON ck.ConceptId = c.ConceptId
        WHERE c.Createdby = ?

        UNION ALL

        SELECT
            d.ConceptId,
            ck.CurrentConceptId,
            d.ConceptName,
            d.DevelopmentStatus,
            d.CreatedDate,
            d.Createdby,
            'DRAFT' AS RecordType
        FROM {settings.CONCEPT_DRAFTS} d
        LEFT JOIN {settings.CONCEPT_KEYS} ck ON ck.ConceptId = d.ConceptId
        WHERE d.Createdby = ? AND d.IsActive = 1

        ORDER BY CreatedDate DESC
    """, (user_id, user_id))

    rows = cursor.fetchall()
    return [
        {
            "ConceptId": row[0],
            "CurrentConceptId": row[1],
            "ConceptName": row[2],
            "DevelopmentStatus": row[3],
            "CreatedDate": row[4],
            "Createdby": row[5],
            "RecordType": row[6],
        }
        for row in rows
    ]


# =====================================================================
# SINGLE CONCEPT DETAIL (Concept + Draft, unioned by anchor/current id)
# =====================================================================

def fetch_concept_main_row(cursor, concept_id: str) -> Optional[Dict[str, Any]]:
    """Looks up a Concept or active ConceptDraft by either the anchor ConceptId
    or the display CurrentConceptId. Returns None if nothing matches."""
    cursor.execute(f"""
        SELECT
            c.ConceptId,
            ck.CurrentConceptId,
            c.ConceptName,
            c.DevelopmentStatus,
            c.Priority,
            c.HaloNumber,
            c.InternalConceptDescription,
            c.EstimatedVolume,
            c.EstimatedDollars,
            c.ConfidenceScore,
            c.IdeationRequestorId,
            u1.Name AS IdeationRequestorName,
            c.DataScienceProgrammerId,
            u2.Name AS DataScienceProgrammerName,
            c.PreviousReportId,
            c.QASchedule,
            c.ProductionSchedule,
            c.CreatedBy,
            FORMAT(c.CreatedDate, 'MM/dd/yyyy') AS CreatedDate,
            FORMAT(c.UpdatedDate, 'MM/dd/yyyy') AS UpdatedDate,
            c.DevelopmentCompleted,
            c.ClientApprovalCompleted,
            c.SupportingDocumentsCompleted,
            NULL AS DraftId,
            CAST(1 AS BIT) AS IsActive,
            'CONCEPT' AS RecordType
        FROM {settings.CONCEPTS} c
        LEFT JOIN {settings.CONCEPT_KEYS} ck
            ON ck.ConceptId = c.ConceptId
        LEFT JOIN {settings.USERS} u1
            ON u1.Id = c.IdeationRequestorId
        LEFT JOIN {settings.USERS} u2
            ON u2.Id = c.DataScienceProgrammerId
        WHERE c.ConceptId = ? OR ck.CurrentConceptId = ?

        UNION ALL

        SELECT
            d.ConceptId,
            ck.CurrentConceptId,
            d.ConceptName,
            d.DevelopmentStatus,
            d.Priority,
            d.HaloNumber,
            d.InternalConceptDescription,
            d.EstimatedVolume,
            d.EstimatedDollars,
            d.ConfidenceScore,
            d.IdeationRequestorId,
            u1.Name AS IdeationRequestorName,
            d.DataScienceProgrammerId,
            u2.Name AS DataScienceProgrammerName,
            d.PreviousReportId,
            d.QASchedule,
            d.ProductionSchedule,
            d.CreatedBy,
            FORMAT(d.CreatedDate, 'MM/dd/yyyy') AS CreatedDate,
            FORMAT(d.UpdatedDate, 'MM/dd/yyyy') AS UpdatedDate,
            d.DevelopmentCompleted,
            d.ClientApprovalCompleted,
            d.SupportingDocumentsCompleted,
            d.DraftId,
            d.IsActive,
            'DRAFT' AS RecordType
        FROM {settings.CONCEPT_DRAFTS} d
        LEFT JOIN {settings.CONCEPT_KEYS} ck
            ON ck.ConceptId = d.ConceptId
        LEFT JOIN {settings.USERS} u1
            ON u1.Id = d.IdeationRequestorId
        LEFT JOIN {settings.USERS} u2
            ON u2.Id = d.DataScienceProgrammerId
        WHERE (d.ConceptId = ? OR ck.CurrentConceptId = ?)
          AND d.IsActive = 1;
    """, (concept_id, concept_id, concept_id, concept_id))

    row = cursor.fetchone()
    if not row:
        return None
    return {col[0]: val for col, val in zip(cursor.description, row)}


def fetch_client_approvals(cursor, concept_id: str) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT *
        FROM {settings.CLIENT_APPROVAL}
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))
    rows = cursor.fetchall()
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def fetch_development_notes(cursor, concept_id: str) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT
            c.NoteId,
            c.ConceptId,
            c.NoteText,
            c.CreatedDate,
            c.Createdby,
            u.name AS CreatedByName,
            ur.role_name AS RoleName
        FROM {settings.CONCEPT_DEVELOPMENT_NOTES} c
        JOIN {settings.USERS} u
            ON u.id = c.Createdby
        LEFT JOIN {settings.USER_ROLE} ur
            ON ur.role_id = c.RoleId
        WHERE c.ConceptId = ?
        ORDER BY c.CreatedDate DESC
    """, (concept_id,))
    rows = cursor.fetchall()
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def fetch_active_attachments(cursor, concept_id: str) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT *
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE ConceptId = ?
        AND IsActive = 1
    """, (concept_id,))
    rows = cursor.fetchall()
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def fetch_attachment_history(cursor, concept_id: str) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT *
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE ConceptId = ?
        ORDER BY AttachmentType, Version DESC
    """, (concept_id,))
    rows = cursor.fetchall()
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# =====================================================================
# LATEST UPDATES (Concepts UNION active ConceptDrafts)
# =====================================================================

def fetch_latest_updates(cursor) -> List[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT
            c.ConceptName,
            c.ConceptId,
            ck.CurrentConceptId,
            c.DevelopmentStatus,
            u1.name AS IdeationRequestor,
            u2.name AS DataScienceProgrammer,
            c.CreatedDate,
            c.UpdatedDate,
            CAST(0 AS BIT) AS IsDraft,
            COALESCE(c.UpdatedDate, c.CreatedDate) AS SortDate
        FROM {settings.CONCEPTS} c
        LEFT JOIN {settings.USERS} u1 ON c.IdeationRequestorId = u1.id
        LEFT JOIN {settings.USERS} u2 ON c.DataScienceProgrammerId = u2.id
        LEFT JOIN {settings.CONCEPT_KEYS} ck ON ck.ConceptId = c.ConceptId
        UNION ALL
        SELECT
            d.ConceptName,
            d.ConceptId,
            ck.CurrentConceptId,
            d.DevelopmentStatus,
            u1.name AS IdeationRequestor,
            u2.name AS DataScienceProgrammer,
            d.CreatedDate,
            d.UpdatedDate,
            CAST(1 AS BIT) AS IsDraft,
            COALESCE(d.UpdatedDate, d.CreatedDate) AS SortDate
        FROM {settings.CONCEPT_DRAFTS} d
        LEFT JOIN {settings.USERS} u1 ON d.IdeationRequestorId = u1.id
        LEFT JOIN {settings.USERS} u2 ON d.DataScienceProgrammerId = u2.id
        LEFT JOIN {settings.CONCEPT_KEYS} ck ON ck.ConceptId = d.ConceptId
        WHERE d.IsActive = 1
        ORDER BY SortDate DESC
    """)
    rows = cursor.fetchall()
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in rows]


# =====================================================================
# CONCEPT ID RESOLUTION / CONCEPTKEYS
# =====================================================================

def resolve_concept_id(cursor, concept_id: str) -> str | None: 
    cursor.execute(f"""
        SELECT ConceptId FROM {settings.CONCEPT_KEYS} WHERE ConceptId = ? OR CurrentConceptId = ?
    """, (concept_id, concept_id)) 
    row = cursor.fetchone() 
    if not row: 
        return None 
    anchor_id = row[0] 
    cursor.execute(f"""
        SELECT 1 FROM {settings.CONCEPTS} WHERE ConceptId = ? 
        UNION SELECT 1 FROM {settings.CONCEPT_DRAFTS} WHERE ConceptId = ?
    """, (anchor_id, anchor_id)) 
    if not cursor.fetchone(): 
        return None 
    return anchor_id 


def fetch_concept_key_by_anchor(cursor, concept_id: str):
    """Returns (ConceptId, CurrentConceptId) for an exact anchor match, or None."""
    cursor.execute(f"""
        SELECT ConceptId, CurrentConceptId FROM {settings.CONCEPT_KEYS} WHERE ConceptId = ?
    """, (concept_id,))
    return cursor.fetchone()


def fetch_concept_key_by_current(cursor, concept_id: str):
    """Returns (ConceptId, CurrentConceptId) for an exact CurrentConceptId match, or None."""
    cursor.execute(f"""
        SELECT ConceptId, CurrentConceptId FROM {settings.CONCEPT_KEYS} WHERE CurrentConceptId = ?
    """, (concept_id,))
    return cursor.fetchone()


def fetch_current_concept_id(cursor, concept_id: str) -> Optional[str]:
    cursor.execute(f"""
        SELECT CurrentConceptId FROM {settings.CONCEPT_KEYS} WHERE ConceptId = ?
    """, (concept_id,))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def concept_key_exists(cursor, concept_id: str) -> bool:
    cursor.execute(f"""
        SELECT COUNT(*) FROM {settings.CONCEPT_KEYS} WHERE ConceptId = ?
    """, (concept_id,))
    return cursor.fetchone()[0] > 0


def ensure_concept_key(
    cursor,
    concept_id: str,
    current_concept_id: str,
    client_code,
    master_concept_id,
    review_type,
    claim_type,
    edition,
    version,
    is_development,
    run_number,
):
    """No-op if a ConceptKeys row already exists for this anchor; otherwise inserts one.
    On update-flows, all the descriptive columns (client_code..run_number) are None,
    which is fine because the INSERT branch never fires for an existing anchor."""
    cursor.execute(f"""
        IF NOT EXISTS (SELECT 1 FROM {settings.CONCEPT_KEYS} WHERE ConceptId = ?)
        INSERT INTO {settings.CONCEPT_KEYS}
            (ConceptId, CurrentConceptId, ClientCode, MasterConceptId,
             ReviewType, ClaimType, Edition, Version, IsDevelopment, RunNumber)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        concept_id,
        concept_id, current_concept_id,
        client_code, master_concept_id,
        review_type, claim_type,
        edition, version, is_development, run_number
    ))


def update_concept_key_version(
    cursor, concept_id: str, current_concept_id: str,
    version: int, is_development: int, run_number: int = None
):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_KEYS}
        SET CurrentConceptId=?, Version=?, IsDevelopment=?, RunNumber=?, UpdatedDate=GETDATE()
        WHERE ConceptId=?
    """, (current_concept_id, version, is_development, run_number, concept_id))


def is_data_science_programmer_role(cursor, role_id) -> bool:
    """True if the given role_id corresponds to the 'Data Science Programmer' role."""
    if role_id is None:
        return False
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM {settings.USER_ROLE}
        WHERE role_id = ? AND role_name = 'Data Science Programmer'
    """, (role_id,))
    return cursor.fetchone()[0] > 0


def get_next_edition_number(cursor, base_prefix: str) -> int:
    cursor.execute(f"""
        SELECT ISNULL(MAX(TRY_CAST(
            SUBSTRING(ConceptId, LEN(?) + 2, 3) AS INT
        )), 0) + 1
        FROM {settings.CONCEPT_KEYS}
        WHERE ConceptId LIKE ?
    """, (base_prefix, f"{base_prefix}_%"))
    return cursor.fetchone()[0]


# =====================================================================
# DUPLICATE-NAME CHECKS
# =====================================================================

def find_duplicate_concept_name(cursor, name_lower: str) -> Optional[str]:
    """Used on create — checks both Concepts and active ConceptDrafts."""
    cursor.execute(f"""
        SELECT TOP 1 ConceptId FROM {settings.CONCEPTS}
        WHERE LOWER(LTRIM(RTRIM(ConceptName))) = ?
        UNION
        SELECT TOP 1 ConceptId FROM {settings.CONCEPT_DRAFTS}
        WHERE LOWER(LTRIM(RTRIM(ConceptName))) = ? AND IsActive = 1
    """, (name_lower, name_lower))
    row = cursor.fetchone()
    return row[0] if row else None


def find_duplicate_concept_name_excluding(cursor, name_lower: str, exclude_concept_id: str) -> Optional[str]:
    """Used on update — same check but excludes the concept being updated."""
    cursor.execute(f"""
        SELECT TOP 1 ConceptId FROM {settings.CONCEPTS}
        WHERE LOWER(LTRIM(RTRIM(ConceptName))) = ?
          AND ConceptId <> ?
        UNION
        SELECT TOP 1 ConceptId FROM {settings.CONCEPT_DRAFTS}
        WHERE LOWER(LTRIM(RTRIM(ConceptName))) = ?
          AND ConceptId <> ?
          AND IsActive = 1
    """, (name_lower, exclude_concept_id, name_lower, exclude_concept_id))
    row = cursor.fetchone()
    return row[0] if row else None


# =====================================================================
# ESTIMATED VOLUME / DOLLARS LOOKUP (for version-bump comparison)
# =====================================================================

def fetch_old_volume_dollars(cursor, concept_id: str):
    """Checks Concepts first, then falls back to the active ConceptDrafts row.
    Returns (old_volume, old_dollars), either may be None."""
    cursor.execute(f"""
        SELECT EstimatedVolume, EstimatedDollars
        From {settings.CONCEPTS} WHERE ConceptId = ?
    """, (concept_id,))
    old_row = cursor.fetchone()

    if not old_row:
        cursor.execute(f"""
            SELECT EstimatedVolume, EstimatedDollars
            From {settings.CONCEPT_DRAFTS} WHERE ConceptId = ? AND IsActive = 1
        """, (concept_id,))
        old_row = cursor.fetchone()

    old_volume = old_row[0] if old_row else None
    old_dollars = old_row[1] if old_row else None
    return old_volume, old_dollars


# =====================================================================
# DRAFTS
# =====================================================================

def draft_exists(cursor, concept_id: str) -> bool:
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM {settings.CONCEPT_DRAFTS}
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))
    return cursor.fetchone()[0] > 0


def insert_draft(cursor, concept_id: str, meta: dict, estimated_dollars, user_id: str, normalize_datetime):
    cursor.execute(f"""
        INSERT INTO {settings.CONCEPT_DRAFTS}
        (
            ConceptId, ConceptName, DevelopmentStatus, Priority,
            HaloNumber, InternalConceptDescription, EstimatedVolume,
            EstimatedDollars, ConfidenceScore, IdeationRequestorId,
            DataScienceProgrammerId, PreviousReportId, QASchedule,
            ProductionSchedule, DevelopmentCompleted,
            ClientApprovalCompleted, SupportingDocumentsCompleted,
            IsActive, Createdby
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        concept_id,
        meta.get("conceptName"),
        meta.get("developmentStatus"),
        meta.get("priority"),
        meta.get("haloNumber"),
        meta.get("InternalConceptDescription"),
        meta.get("estimatedVolume"),
        estimated_dollars,
        meta.get("confidenceScore"),
        meta.get("ideationRequestor"),
        meta.get("dataScienceProgrammer"),
        meta.get("previousReportId"),
        normalize_datetime(meta.get("qaSchedule")),
        normalize_datetime(meta.get("productionSchedule")),
        meta.get("DevelopmentCompleted", 0),
        meta.get("ClientApprovalCompleted", 0),
        meta.get("SupportingDocumentsCompleted", 0),
        user_id
    ))


def update_draft(cursor, concept_id: str, meta: dict, estimated_dollars, user_id: str, normalize_datetime):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_DRAFTS}
        SET
            ConceptName=?, DevelopmentStatus=?, Priority=?,
            HaloNumber=?, InternalConceptDescription=?,
            EstimatedVolume=?, EstimatedDollars=?, ConfidenceScore=?,
            IdeationRequestorId=?, DataScienceProgrammerId=?,
            PreviousReportId=?, QASchedule=?, ProductionSchedule=?,
            Createdby=?, UpdatedDate=GETDATE()
        WHERE ConceptId=? AND IsActive=1
    """, (
        meta.get("conceptName"),
        meta.get("developmentStatus"),
        meta.get("priority"),
        meta.get("haloNumber"),
        meta.get("InternalConceptDescription"),
        meta.get("estimatedVolume"),
        estimated_dollars,
        meta.get("confidenceScore"),
        meta.get("ideationRequestor"),
        meta.get("dataScienceProgrammer"),
        meta.get("previousReportId"),
        normalize_datetime(meta.get("qaSchedule")),
        normalize_datetime(meta.get("productionSchedule")),
        user_id,
        concept_id
    ))


def fetch_draft_for_promotion(cursor, concept_id: str) -> Optional[Dict[str, Any]]:
    cursor.execute(f"""
        SELECT
            ConceptName, DevelopmentStatus, Priority, HaloNumber,
            InternalConceptDescription, EstimatedVolume, EstimatedDollars,
            ConfidenceScore, IdeationRequestorId, DataScienceProgrammerId,
            PreviousReportId, QASchedule, ProductionSchedule,
            DevelopmentCompleted, ClientApprovalCompleted,
            SupportingDocumentsCompleted
        FROM {settings.CONCEPT_DRAFTS}
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))
    row = cursor.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))


def deactivate_draft(cursor, concept_id: str):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_DRAFTS}
        SET IsActive = 0
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))


# =====================================================================
# CONCEPTS (final)
# =====================================================================

def concept_exists(cursor, concept_id: str) -> bool:
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM {settings.CONCEPTS}
        WHERE ConceptId = ?
    """, (concept_id,))
    return cursor.fetchone()[0] > 0


def insert_concept(
    cursor, concept_id: str, concept_name, development_status, priority,
    halo_number, internal_description, estimated_volume, estimated_dollars,
    confidence_score, ideation_requestor, ds_programmer, previous_report_id,
    qa_schedule, production_schedule, user_id: str,
    development_completed, client_approval_completed, supporting_documents_completed,
):
    cursor.execute(f"""
        INSERT INTO {settings.CONCEPTS}
        (
            ConceptId, ConceptName, DevelopmentStatus, Priority,
            HaloNumber, InternalConceptDescription, EstimatedVolume,
            EstimatedDollars, ConfidenceScore, IdeationRequestorId,
            DataScienceProgrammerId, PreviousReportId, QASchedule,
            ProductionSchedule, Createdby, DevelopmentCompleted,
            ClientApprovalCompleted, SupportingDocumentsCompleted
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        concept_id, concept_name, development_status, priority,
        halo_number, internal_description, estimated_volume,
        estimated_dollars, confidence_score, ideation_requestor,
        ds_programmer, previous_report_id, qa_schedule,
        production_schedule, user_id, development_completed,
        client_approval_completed, supporting_documents_completed
    ))


def update_concept(cursor, concept_id: str, meta: dict, estimated_dollars, user_id: str, normalize_datetime):
    cursor.execute(f"""
        UPDATE {settings.CONCEPTS}
        SET
            ConceptName=?, DevelopmentStatus=?, Priority=?,
            HaloNumber=?, InternalConceptDescription=?,
            EstimatedVolume=?, EstimatedDollars=?, ConfidenceScore=?,
            IdeationRequestorId=?, DataScienceProgrammerId=?,
            PreviousReportId=?, QASchedule=?, ProductionSchedule=?,
            Createdby=?, UpdatedDate=GETDATE()
        WHERE ConceptId=?
    """, (
        meta.get("conceptName"),
        meta.get("developmentStatus"),
        meta.get("priority"),
        meta.get("haloNumber"),
        meta.get("InternalConceptDescription"),
        meta.get("estimatedVolume"),
        estimated_dollars,
        meta.get("confidenceScore"),
        meta.get("ideationRequestor"),
        meta.get("dataScienceProgrammer"),
        meta.get("previousReportId"),
        normalize_datetime(meta.get("qaSchedule")),
        normalize_datetime(meta.get("productionSchedule")),
        user_id,
        concept_id
    ))


def insert_development_notes(cursor, concept_id: str, notes: List[str], user_id: str, role_id: int):
    for note in notes:
        note_text = note.get("text") if isinstance(note, dict) else note
        if note_text and note_text.strip():
            cursor.execute(f"""
                INSERT INTO {settings.CONCEPT_DEVELOPMENT_NOTES}
                (ConceptId, NoteText, Createdby, RoleId)
                VALUES (?, ?, ?, ?)
            """, (concept_id, note_text.strip(), user_id, role_id))


# =====================================================================
# ATTACHMENTS (generic upload flow shared by create/update + client approval)
# =====================================================================

def deactivate_attachment_by_filename(cursor, concept_id: str, category: str, file_name: str):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_ATTACHMENTS}
        SET IsActive = 0
        WHERE ConceptId = ? AND AttachmentType = ? AND FileName = ? AND IsActive = 1
    """, (concept_id, category, file_name))


def get_next_attachment_version_by_filename(cursor, concept_id: str, category: str, file_name: str) -> int:
    cursor.execute(f"""
        SELECT ISNULL(MAX(Version),0)+1
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE ConceptId = ? AND AttachmentType = ? AND FileName = ?
    """, (concept_id, category, file_name))
    return cursor.fetchone()[0]


def insert_attachment(cursor, concept_id: str, category: str, file_name: str, file_path: str,
                       file_size, user_id: str, version: int):
    cursor.execute(f"""
        INSERT INTO {settings.CONCEPT_ATTACHMENTS}
        (ConceptId, AttachmentType, FileName, FilePath, FileSize,
         Createdby, Version, IsActive, UploadedOn)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
    """, (
        concept_id, category, file_name,
        file_path, file_size,
        user_id, version
    ))


# =====================================================================
# CLIENT APPROVAL
# =====================================================================

def fetch_active_client_approval_id(cursor, concept_id: str) -> Optional[int]:
    cursor.execute(f"""
        SELECT ApprovalId
        FROM {settings.CLIENT_APPROVAL}
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def deactivate_client_approval(cursor, concept_id: str):
    cursor.execute(f"""
        UPDATE {settings.CLIENT_APPROVAL}
        SET IsActive = 0,
            UpdatedDate = GETDATE()
        WHERE ConceptId = ? AND IsActive = 1
    """, (concept_id,))


def insert_client_approval(
    cursor, concept_id: str, concept_name, client_concept_name, client_concept_description,
    client_approval_status, submitted_to_client_on, client_approval_notes,
    estimated_volume, estimated_dollars, approved_by,
):
    cursor.execute(f"""
        INSERT INTO {settings.CLIENT_APPROVAL}
        (
            ConceptId,
            ConceptName,
            ClientConceptName,
            ClientConceptDescription,
            ClientApprovalStatus,
            SubmittedToClientOn,
            ClientApprovalNotes,
            EstimatedVolume,
            EstimatedDollars,
            Approvedby,
            IsActive
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        concept_id,
        concept_name,
        client_concept_name,
        client_concept_description,
        client_approval_status,
        submitted_to_client_on,
        client_approval_notes,
        estimated_volume,
        estimated_dollars,
        approved_by
    ))


def fetch_concept_volume_dollars(cursor, concept_id: str):
    cursor.execute(f"""
        SELECT EstimatedVolume, EstimatedDollars
        FROM {settings.CONCEPTS}
        WHERE ConceptId = ?
    """, (concept_id,))
    row = cursor.fetchone()
    return (row[0], row[1]) if row else (None, None)


def sync_concept_volume_dollars_and_approval_flag(
    cursor, concept_id: str, new_volume, new_dollars, client_approval_completed
):
    cursor.execute(f"""
        UPDATE {settings.CONCEPTS}
        SET
            EstimatedVolume  = COALESCE(?, EstimatedVolume),
            EstimatedDollars = COALESCE(?, EstimatedDollars),
            ClientApprovalCompleted = ?,
            UpdatedDate = GETDATE()
        WHERE ConceptId = ?
    """, (new_volume, new_dollars, client_approval_completed, concept_id))


def update_concept_client_approval_flag(cursor, concept_id: str, client_approval_completed):
    cursor.execute(f"""
        UPDATE {settings.CONCEPTS}
        SET ClientApprovalCompleted = ?
        WHERE ConceptId = ?
    """, (client_approval_completed, concept_id))


# =====================================================================
# SUPPORTING DOCUMENTS
# =====================================================================

def fetch_active_supporting_attachment(cursor, concept_id: str, category: str, doc_index: int):
    """Returns (FileName, FilePath, FileSize) for the currently active
    attachment at this doc_index, or None."""
    cursor.execute(f"""
        SELECT FileName, FilePath, FileSize
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE ConceptId = ?
        AND AttachmentType = ?
        AND DocIndex = ?
        AND IsActive = 1
    """, (concept_id, category, doc_index))
    return cursor.fetchone()


def deactivate_attachment_by_doc_index(cursor, concept_id: str, category: str, doc_index: int):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_ATTACHMENTS}
        SET IsActive = 0
        WHERE ConceptId = ?
        AND AttachmentType = ?
        AND DocIndex = ?
        AND IsActive = 1
    """, (concept_id, category, doc_index))


def get_next_attachment_version_by_doc_index(cursor, concept_id: str, category: str, doc_index: int) -> int:
    cursor.execute(f"""
        SELECT ISNULL(MAX(Version), 0) + 1
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE ConceptId = ?
        AND AttachmentType = ?
        AND DocIndex = ?
    """, (concept_id, category, doc_index))
    return cursor.fetchone()[0]


def insert_supporting_attachment(
    cursor, concept_id: str, category: str, doc_index: int, doc_name,
    file_name, file_path, file_size, source_url, user_id: str, version: int,
):
    cursor.execute(f"""
        INSERT INTO {settings.CONCEPT_ATTACHMENTS}
        (ConceptId, AttachmentType, DocIndex, DocName, FileName,
         FilePath, FileSize, sourceurl, Createdby, Version,
         IsActive, UploadedOn)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
    """, (
        concept_id, category, doc_index, doc_name,
        file_name, file_path, file_size,
        source_url, user_id, version
    ))


def update_concept_supporting_docs_flag(cursor, concept_id: str, supporting_completed):
    cursor.execute(f"""
        UPDATE {settings.CONCEPTS}
        SET SupportingDocumentsCompleted = ?
        WHERE ConceptId = ?
    """, (supporting_completed, concept_id))


# =====================================================================
# ATTACHMENT DOWNLOAD / DELETE
# =====================================================================

def fetch_attachment_file(cursor, attachment_id: int):
    """Returns (FileName, FilePath) for an active attachment, or None."""
    cursor.execute(f"""
        SELECT FileName, FilePath
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE AttachmentId = ? AND IsActive = 1
    """, (attachment_id,))
    return cursor.fetchone()


def fetch_attachment_for_delete(cursor, attachment_id: int, concept_id: str, category: str):
    """Returns (FilePath,) if a matching active attachment exists, or None."""
    cursor.execute(f"""
        SELECT FilePath
        FROM {settings.CONCEPT_ATTACHMENTS}
        WHERE AttachmentId = ?
          AND ConceptId = ?
          AND AttachmentType = ?
          AND IsActive = 1
    """, (attachment_id, concept_id, category))
    return cursor.fetchone()


def soft_delete_attachment(cursor, attachment_id: int, user_id: int):
    cursor.execute(f"""
        UPDATE {settings.CONCEPT_ATTACHMENTS}
        SET
            IsActive = 0,
            UpdatedBy = ?,
            UpdatedDate = GETDATE()
        WHERE AttachmentId = ?
          AND IsActive = 1
    """, (user_id, attachment_id))


# =====================================================================
# USERS
# =====================================================================

def fetch_user_name(cursor, user_id: int) -> Optional[str]:
    cursor.execute(f"""
        SELECT name
        FROM {settings.USERS}
        WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_user_roles(cursor, user_id: int) -> List[Dict[str, Any]]:
    """
    All roles currently assigned to a user. A user can have more than one
    row in user_access, so this must never assume/return just one - callers
    that need a single active role (e.g. at login) are responsible for
    letting the user pick when this returns more than one.
    """
    cursor.execute(f"""
        SELECT ur.role_id, ur.role_name
        FROM {settings.USER_ACCESS} ua
        INNER JOIN {settings.USER_ROLE} ur ON ua.role_id = ur.role_id
        WHERE ua.user_id = ?
        ORDER BY ur.role_name
    """, (user_id,))
    return [{"role_id": row.role_id, "role_name": row.role_name} for row in cursor.fetchall()]


def user_has_role(cursor, user_id: int, role_id: int) -> bool:
    """
    Server-side check that a role really is assigned to this user - never
    trust a client-supplied role_id (e.g. from a role-switch request)
    without verifying it against user_access first.
    """
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM {settings.USER_ACCESS}
        WHERE user_id = ? AND role_id = ?
    """, (user_id, role_id))
    return cursor.fetchone()[0] > 0