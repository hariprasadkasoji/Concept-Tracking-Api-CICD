"""
concept_helpers.py

Pure, DB-free helper functions shared by the concept-related routers
(app/api/concepts.py, app/api/client_approval.py, app/api/attachments.py).
Nothing here touches a cursor or raises HTTPException directly - keeping
these separate from concept_queries.py (DB access) and the routers
(HTTP/request handling) so each layer has one job.
"""

import re
from datetime import datetime
from fastapi import HTTPException
from app.services import concept_queries as q


def normalize_datetime(value):
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def format_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y")
    return value


def num_changed(old_val, new_val):
    if new_val in (None, ""):
        return False
    try:
        return float(old_val or 0) != float(new_val)
    except (TypeError, ValueError):
        return str(old_val) != str(new_val)


def resolve_concept_id(cursor, concept_id: str) -> str:
    """
    Accepts either the anchor ConceptId or the current display
    CurrentConceptId, and returns the anchor ConceptId - which is what
    every other table (Concepts, ConceptDrafts, ConceptAttachments,
    ConceptDevelopmentNotes, ClientApproval) is actually keyed on.

    Raises HTTPException(404) if neither matches.
    """
    resolved = q.resolve_concept_id(cursor, concept_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Concept not found: {concept_id}")
    return resolved


# =====================================================================
# CONCEPT ID GENERATION / PARSING
# =====================================================================

def generate_concept_id(
    client_code: str,
    master_concept_id: str,
    review_type: str,
    claim_type: str,
    edition: int,
    version: int = None,
    run: int = None,
    is_development: bool = False
):
    """
    Generate Concept IDs based on the Concept ID structure.

    Examples:
        Base Concept ID:
            MRW0000AP

        Concept ID:
            MRW0000AP_001

        Production Version:
            MRW0000AP_001_001

        Development Version:
            MRW0000AP_001_D001

        Development Version + Run:
            MRW0000AP_001_D001_001

        Production Run:
            MRW0000AP_001_001_001
    """

    base_id = (
        f"{client_code}"
        f"{master_concept_id}"
        f"{review_type}"
        f"{claim_type}"
    )

    concept_id = f"{base_id}_{edition:03d}"

    if version is None:
        return concept_id

    if is_development:
        concept_version = f"{concept_id}_D{version:03d}"
    else:
        concept_version = f"{concept_id}_{version:03d}"

    if run is None:
        return concept_version

    return f"{concept_version}_{run:03d}"


CONCEPT_ID_PATTERN = re.compile(
    r'^(?P<base>[A-Za-z0-9]{3}\d{4}[A-Za-z]{2})_(?P<edition>\d{3})'
    r'(?:_(?P<dev>D)?(?P<version>\d{3}))?'
    r'(?:_(?P<run>\d{3}))?$'
)


def parse_concept_id(concept_id: str) -> dict:
    m = CONCEPT_ID_PATTERN.match(concept_id)
    if not m:
        raise ValueError(f"Unrecognized Concept ID format: {concept_id}")
    d = m.groupdict()
    return {
        "base": d["base"],
        "edition": int(d["edition"]),
        "version": int(d["version"]) if d["version"] else None,
        "is_development": bool(d["dev"]),
        "run": int(d["run"]) if d["run"] else None,
    }


def get_next_concept_id(
    current_concept_id: str,
    new_development_status,
    bump_dev_version: bool = True,
    bump_run_number: bool = False,
) -> str:
    parsed = parse_concept_id(current_concept_id)

    if parsed["version"] is None:
        return current_concept_id

    base = parsed["base"]
    edition = parsed["edition"]
    version = parsed["version"]
    is_development = parsed["is_development"]
    run = parsed["run"]

    # Run number is independent of the version/dev-status transition below -
    # it only reflects how many times a Data Science Programmer has saved
    # an update, regardless of whether that same save also bumps version.
    if bump_run_number:
        run = (run or 0) + 1

    if str(new_development_status) == "Production" and is_development:
        is_development = False
    elif is_development and bump_dev_version:
        version += 1

    core = f'{base}_{edition:03d}'
    core += f'_D{version:03d}' if is_development else f'_{version:03d}'

    # Only append a run segment if one already existed (or is being newly
    # assigned via bump_run_number) - never silently invent one for older
    # concept IDs that were created before run numbers existed.
    if run is not None:
        core += f'_{run:03d}'

    return core