
from pathlib import Path
from uuid import uuid4


# backend/storage/uploads/
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "storage" / "uploads"


def save_pdf(contents: bytes) -> str:
    """
    Save PDF bytes using a unique filename.

    Returns the relative storage path from the backend directory.
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4()}.pdf"
    file_path = UPLOAD_DIR / filename

    file_path.write_bytes(contents)

    return f"storage/uploads/{filename}"


def get_pdf_path(storage_path: str) -> Path:
    """
    Resolve a stored relative path and ensure it stays
    inside the uploads directory.
    """
    upload_dir = UPLOAD_DIR.resolve()
    resolved_path = (UPLOAD_DIR.parent.parent / storage_path).resolve()

    if not resolved_path.is_relative_to(upload_dir):
        raise ValueError("Invalid storage path")

    if not resolved_path.is_file():
        raise FileNotFoundError("Stored PDF file not found")

    return resolved_path
