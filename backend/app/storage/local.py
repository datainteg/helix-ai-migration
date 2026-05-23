import re
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


ALLOWED_TYPES = {"py", "sql"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    """Return a display-safe filename without path components."""
    raw_filename = filename or "artifact"
    name = Path(raw_filename).name
    name = Path(name.replace("\\", "/")).name
    sanitized = SAFE_FILENAME_PATTERN.sub("_", name)
    sanitized = sanitized.strip("_") or "artifact"
    if sanitized in {".", ".."}:
        return "artifact"
    return sanitized[:255]


def _storage_root() -> Path:
    return Path(settings.ARTIFACT_STORAGE_PATH or "./data/artifacts").resolve()


def _assert_inside_storage_root(path: Path) -> None:
    storage_root = _storage_root()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("Resolved artifact path is outside the configured storage root") from exc


def build_safe_artifact_path(project_id: str, filename: str) -> Path:
    safe_project_id = sanitize_filename(project_id)
    safe_filename = sanitize_filename(filename)
    extension = Path(safe_filename).suffix.lower()
    storage_name = f"{uuid4().hex}{extension}"
    path = (_storage_root() / safe_project_id / storage_name).resolve()
    _assert_inside_storage_root(path)
    return path


def get_storage_path(project_id: str, filename: str) -> str:
    return str(build_safe_artifact_path(project_id, filename))


def save_file(path: str | Path, content: bytes):
    artifact_path = Path(path).resolve()
    _assert_inside_storage_root(artifact_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("wb") as f:
        f.write(content)


def save_artifact_file(project_id: str, filename: str, content: bytes) -> Path:
    path = build_safe_artifact_path(project_id, filename)
    save_file(path, content)
    return path


def validate_upload(filename: str, content: bytes) -> None:
    """Validate file type and size. Raises HTTPException on failure."""
    from fastapi import HTTPException

    safe_filename = sanitize_filename(filename)
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_TYPES)}")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.MAX_UPLOAD_MB}MB")
