from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.services.artifact_version_service import create_artifact_metadata, list_artifacts, get_artifact, list_versions
from app.storage.local import sanitize_filename, save_artifact_file, validate_upload
from app.services.auth_service import get_current_user

router = APIRouter(tags=["artifacts"])


@router.post("/projects/{project_id}/artifacts/upload")
async def upload_artifact(project_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = get_current_user(db, user_id)
    org_id = user.memberships[0].organization_id

    original_filename = file.filename or "unknown"
    content = await file.read()
    validate_upload(original_filename, content)

    path = save_artifact_file(project_id, original_filename, content)

    ext = sanitize_filename(original_filename).rsplit(".", 1)[-1].lower()
    return create_artifact_metadata(db, org_id, project_id, original_filename, ext, str(path), content)


@router.get("/projects/{project_id}/artifacts")
def api_list_artifacts(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_artifacts(db, project_id)


@router.get("/artifacts/{artifact_id}")
def api_get_artifact(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_artifact(db, artifact_id)


@router.get("/artifacts/{artifact_id}/versions")
def api_list_versions(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return list_versions(db, artifact_id)
