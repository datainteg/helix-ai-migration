import os

from app.core.config import settings


ALLOWED_TYPES = {"py", "sql"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


def get_storage_path(project_id: str, filename: str) -> str:
    base = settings.ARTIFACT_STORAGE_PATH or "./data/artifacts"
    project_dir = os.path.join(base, project_id)
    os.makedirs(project_dir, exist_ok=True)
    return os.path.join(project_dir, filename)


def save_file(path: str, content: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def validate_upload(filename: str, content: bytes) -> None:
    """Validate file type and size. Raises HTTPException on failure."""
    from fastapi import HTTPException

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_TYPES)}")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.MAX_UPLOAD_MB}MB")
