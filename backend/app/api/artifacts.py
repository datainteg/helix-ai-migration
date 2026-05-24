from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.services.artifact_version_service import create_artifact_metadata, list_artifacts, get_artifact, list_versions
from app.services.project_service import ensure_project_access
from app.storage.local import sanitize_filename, save_artifact_file, validate_upload
from app.services.auth_service import get_current_user
from app.api.audit import write_audit

router = APIRouter(tags=["artifacts"])


@router.post("/projects/{project_id}/artifacts/upload")
async def upload_artifact(request: Request, project_id: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = get_current_user(db, user_id)
    org_id = user.memberships[0].organization_id
    ensure_project_access(db, org_id, project_id)

    original_filename = file.filename or "unknown"
    content = await file.read()
    validate_upload(original_filename, content)

    path = save_artifact_file(project_id, original_filename, content)

    ext = sanitize_filename(original_filename).rsplit(".", 1)[-1].lower()
    result = create_artifact_metadata(db, org_id, project_id, original_filename, ext, str(path), content)
    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_uploaded", entity_type="artifact", entity_id=result.id, meta={"filename": original_filename}, request=request)
    return result


@router.get("/projects/{project_id}/artifacts")
def api_list_artifacts(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    user = get_current_user(db, user_id)
    if not user.memberships:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="User has no organization membership")
    org_id = user.memberships[0].organization_id
    ensure_project_access(db, org_id, project_id)
    rows = list_artifacts(db, org_id, project_id)
    return rows[offset : offset + limit]


@router.get("/artifacts/{artifact_id}")
def api_get_artifact(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = get_current_user(db, user_id)
    return get_artifact(db, user.memberships[0].organization_id, artifact_id)


@router.get("/artifacts/{artifact_id}/versions")
def api_list_versions(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = get_current_user(db, user_id)
    return list_versions(db, user.memberships[0].organization_id, artifact_id)
