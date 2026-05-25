"""S3 / S3-compatible artifact storage driver.

Activated when `ARTIFACT_STORAGE_PROVIDER=s3`. Reads:

  S3_BUCKET            (required)
  S3_REGION            (default: us-east-1)
  S3_PREFIX            (default: helix-artifacts)
  S3_ENDPOINT_URL      (optional — MinIO, R2, B2 etc.)
  AWS_ACCESS_KEY_ID    (optional — boto3 default chain otherwise)
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN

Persisted `storage_path` rows for S3 artifacts have the form
`s3://<bucket>/<key>` so call sites can distinguish them from local paths
trivially (`startswith("s3://")`). Reads route through `read_artifact_bytes`
which dispatches based on that prefix.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.storage.local import sanitize_filename, validate_upload  # noqa: F401 (re-export)

logger = logging.getLogger(__name__)


_S3_PATH_RE = re.compile(r"^s3://([^/]+)/(.+)$")


def is_s3_enabled() -> bool:
    return (settings.ARTIFACT_STORAGE_PROVIDER or "").lower() == "s3"


def _s3_client():
    """Lazy boto3 import so the local-only deployment doesn't pull in boto3."""
    import boto3  # type: ignore[import-not-found]
    endpoint = os.getenv("S3_ENDPOINT_URL") or None
    region = os.getenv("S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region, endpoint_url=endpoint)


def _bucket() -> str:
    bucket = os.getenv("S3_BUCKET", "")
    if not bucket:
        raise RuntimeError("S3_BUCKET env var required when ARTIFACT_STORAGE_PROVIDER=s3")
    return bucket


def _prefix() -> str:
    return (os.getenv("S3_PREFIX") or "helix-artifacts").strip("/")


def _build_key(project_id: str, filename: str) -> str:
    safe_project = sanitize_filename(project_id)
    safe_filename = sanitize_filename(filename)
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    storage_name = f"{uuid4().hex}{('.' + ext) if ext else ''}"
    return f"{_prefix()}/{safe_project}/{storage_name}"


def save_artifact_s3(project_id: str, filename: str, content: bytes) -> str:
    """Upload + return `s3://bucket/key`."""
    client = _s3_client()
    key = _build_key(project_id, filename)
    client.put_object(Bucket=_bucket(), Key=key, Body=content, ContentType="text/plain")
    return f"s3://{_bucket()}/{key}"


def parse_s3_path(path: str) -> Optional[Tuple[str, str]]:
    m = _S3_PATH_RE.match(path or "")
    if not m:
        return None
    return m.group(1), m.group(2)


def read_s3_bytes(path: str) -> bytes:
    parsed = parse_s3_path(path)
    if not parsed:
        raise ValueError(f"Not an s3 path: {path!r}")
    bucket, key = parsed
    client = _s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def read_artifact_bytes(storage_path: str) -> bytes:
    """Dispatch between local-disk and s3:// paths."""
    if storage_path.startswith("s3://"):
        return read_s3_bytes(storage_path)
    from pathlib import Path
    return Path(storage_path).read_bytes()


def save_artifact(project_id: str, filename: str, content: bytes) -> str:
    """Top-level write — picks the right driver based on settings.

    Returns a string suitable for storing in code_artifacts.storage_path:
      local: absolute filesystem path
      s3:    `s3://<bucket>/<key>`
    """
    if is_s3_enabled():
        return save_artifact_s3(project_id, filename, content)
    from app.storage.local import save_artifact_file
    return str(save_artifact_file(project_id, filename, content))
