# Concept File Storage Configuration

from pathlib import Path

from fastapi import UploadFile, HTTPException

from app.core.config import settings


BASE_DIR = Path(__file__).resolve().parent

# Navigate to project root
PROJECT_ROOT = BASE_DIR.parent.parent


def get_concept_files_directory() -> Path:
    """
    Determine the concept files directory.

    Priority:
    1. settings.CONCEPT_FILES_DIR as application root
       -> creates <CONCEPT_FILES_DIR>/concept_files
    2. <project_root>/concept_files (default)
    """

    default_dir = PROJECT_ROOT / "concept_files"

    custom_base_dir = settings.CONCEPT_FILES_DIR

    if custom_base_dir:
        try:
            concept_dir = (
                Path(custom_base_dir)
                .expanduser()
                .resolve()
                / "concept_files"
            )

            concept_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            # Verify write access
            test_file = concept_dir / ".write_test"
            test_file.touch(exist_ok=True)
            test_file.unlink()

            return concept_dir

        except Exception:
            # Fall back to default location
            pass

    default_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return default_dir


# -------------------------------------------------
# Create concept file directories
# -------------------------------------------------

CONCEPT_FILES_DIR = get_concept_files_directory()

TEMP_UPLOAD_DIR = CONCEPT_FILES_DIR / "uploads"

FINAL_UPLOAD_DIR = CONCEPT_FILES_DIR / "final_uploads"


TEMP_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

FINAL_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# -------------------------------------------------
# Save Uploaded Chunk
# -------------------------------------------------

async def save_chunk(
    concept_id: str,
    category: str,
    chunk: UploadFile,
    chunk_index: int,
    file_name: str,
):
    try:
        chunk_path = (
            TEMP_UPLOAD_DIR
            / f"{concept_id}_{category}_{file_name}.part{chunk_index}"
        )

        with open(chunk_path, "wb") as f:
            content = await chunk.read()
            f.write(content)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving chunk: {str(e)}",
        )


# -------------------------------------------------
# Merge Chunks Into Final File
# -------------------------------------------------

def merge_chunks(
    concept_id: str,
    attachment_type: str,
    file_name: str,
    total_chunks: int,
):
    try:

        final_folder = (
            FINAL_UPLOAD_DIR
            / concept_id.strip()
            / attachment_type.strip()
        )

        final_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        final_file_path = final_folder / file_name


        with open(final_file_path, "wb") as final_file:

            for i in range(total_chunks):

                chunk_path = (
                    TEMP_UPLOAD_DIR
                    / f"{concept_id}_{attachment_type}_{file_name}.part{i}"
                )

                with open(chunk_path, "rb") as chunk_file:
                    final_file.write(
                        chunk_file.read()
                    )

                chunk_path.unlink()


        return {
            "file_name": file_name,
            "file_path": str(final_file_path),
            "file_size": final_file_path.stat().st_size,
        }


    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error merging chunks: {str(e)}",
        )


# -------------------------------------------------
# Save Complete File
# -------------------------------------------------

def save_file(
    concept_id: str,
    attachment_type: str,
    file_name: str,
    content: bytes,
):
    try:

        final_folder = (
            FINAL_UPLOAD_DIR
            / concept_id.strip()
            / attachment_type.strip()
        )

        final_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        final_file_path = final_folder / file_name


        with open(final_file_path, "wb") as f:
            f.write(content)


        return {
            "file_name": file_name,
            "file_path": str(final_file_path),
            "file_size": final_file_path.stat().st_size,
        }


    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving file: {str(e)}",
        )


# Final Structure:
#
# C:\Users\hkasoji\Desktop\concept-tracking-git-pull
#
# └── concept_files
#     │
#     ├── uploads
#     │
#     └── final_uploads
#         │
#         └── CON001
#             │
#             ├── Specs
#             │   ├── requirements.pdf
#             │   └── design.docx
#             │
#             └── Other
#                 └── notes.txt