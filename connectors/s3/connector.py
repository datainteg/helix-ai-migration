"""S3 connector — list buckets/prefixes, infer schema from CSV/Parquet files."""

from __future__ import annotations

import logging
from typing import Any

from connectors.base.connector import (
    BaseConnector, ColumnInfo, ConnectorCapabilities, ConnectorTestResult,
    ConnectorType, RowCountResult, SchemaInfo, TableInfo,
)
from connectors.base.exceptions import DiscoveryError

logger = logging.getLogger(__name__)


class S3Connector(BaseConnector):
    connector_type = ConnectorType.S3
    display_name = "Amazon S3"
    capabilities = ConnectorCapabilities(
        test_connection=True,
        schema_discovery=True,
        table_discovery=True,
        column_discovery=True,
        row_count=False,
        table_profile=False,
        file_listing=True,
        file_schema_inference=True,
        supports_recon=False,
    )

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # H-013: cache the boto3 S3 client on the instance so high-frequency
        # discovery (list_schemas → list_tables → list_columns) reuses one
        # SigV4-signed HTTPS connection pool instead of building a fresh
        # client + connection pool per call. Set lazily in _get_client.
        self._client: Any = None

    def _get_client(self):
        # H-013: cached client short-circuit. assume_role-issued tokens are
        # held inside the cached client; refresh requires re-instantiating
        # the connector. Caller lifecycle (one S3Connector per discovery
        # request) already bounds the token lifetime to that request.
        if self._client is not None:
            return self._client

        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
        except ImportError as exc:
            raise DiscoveryError("boto3 not installed. Add boto3 to requirements.txt.", "s3") from exc

        cfg = self.config
        kwargs: dict[str, Any] = {"region_name": cfg.get("region", "us-east-1")}
        if cfg.get("access_key_id"):
            kwargs["aws_access_key_id"] = cfg["access_key_id"]
            kwargs["aws_secret_access_key"] = cfg.get("secret_access_key", "")
        if cfg.get("role_arn"):
            sts = boto3.client("sts", **kwargs)
            try:
                assumed = sts.assume_role(
                    RoleArn=cfg["role_arn"],
                    RoleSessionName="helix-s3",
                )
            except NoCredentialsError as exc:
                # H-013: replace the opaque NoCredentialsError with an
                # actionable message that points at the two valid setups.
                raise ConnectionError(
                    "S3 connector requires either ambient IAM credentials "
                    "in the worker container, or explicit access_key_id + "
                    "secret_access_key in the connector config."
                ) from exc
            creds = assumed["Credentials"]
            kwargs = {
                "aws_access_key_id": creds["AccessKeyId"],
                "aws_secret_access_key": creds["SecretAccessKey"],
                "aws_session_token": creds["SessionToken"],
                "region_name": cfg.get("region", "us-east-1"),
            }
        self._client = boto3.client("s3", **kwargs)
        return self._client

    async def test_connection(self) -> ConnectorTestResult:
        try:
            client = self._get_client()
            bucket = self.config.get("bucket", "")
            if bucket:
                client.head_bucket(Bucket=bucket)
                return ConnectorTestResult(success=True, message=f"Connected to S3 bucket: {bucket}")
            client.list_buckets()
            return ConnectorTestResult(success=True, message="Connected to S3")
        except Exception as exc:
            logger.warning("S3 connection test failed: %s", exc)
            return ConnectorTestResult(success=False, message=f"Connection failed: {exc}")

    async def list_schemas(self) -> list[SchemaInfo]:
        """Returns the configured bucket as a schema."""
        bucket = self.config.get("bucket", "")
        if bucket:
            return [SchemaInfo(schema_name=bucket, connector_type="s3")]
        try:
            client = self._get_client()
            response = client.list_buckets()
            return [SchemaInfo(schema_name=b["Name"], connector_type="s3") for b in response.get("Buckets", [])]
        except Exception as exc:
            raise DiscoveryError(f"Bucket listing failed: {exc}", "s3") from exc

    async def list_tables(self, schema_name: str) -> list[TableInfo]:
        """Returns top-level prefixes in the bucket as tables."""
        try:
            client = self._get_client()
            prefix = self.config.get("prefix", "")
            response = client.list_objects_v2(Bucket=schema_name, Prefix=prefix, Delimiter="/")
            tables = []
            for cp in response.get("CommonPrefixes", []):
                name = cp["Prefix"].rstrip("/").split("/")[-1]
                tables.append(TableInfo(schema_name=schema_name, table_name=name, table_type="PREFIX"))
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith((".csv", ".parquet", ".json", ".jsonl")):
                    tables.append(TableInfo(schema_name=schema_name, table_name=key, table_type="FILE"))
            return tables
        except Exception as exc:
            raise DiscoveryError(f"Object listing failed: {exc}", "s3") from exc

    async def list_columns(self, schema_name: str, table_name: str) -> list[ColumnInfo]:
        """Infer columns from first file in prefix or file itself."""
        try:
            client = self._get_client()
            key = table_name if table_name.endswith((".csv", ".parquet", ".json", ".jsonl")) else f"{table_name}/"
            if key.endswith("/"):
                resp = client.list_objects_v2(Bucket=schema_name, Prefix=key, MaxKeys=1)
                objects = resp.get("Contents", [])
                if not objects:
                    return []
                key = objects[0]["Key"]

            if key.endswith(".csv"):
                # M-008: a 4 KB range can truncate a wide CSV header mid-column
                # (250+ columns, or long names). Read in growing windows until
                # the first newline is seen so the full header line is captured,
                # capping the total read so a single-line/no-newline file can't
                # force an unbounded download.
                header_line = self._read_first_line(client, schema_name, key)
                cols = [c.strip().strip('"') for c in header_line.split(",")]
                return [
                    ColumnInfo(schema_name=schema_name, table_name=table_name,
                               column_name=c, data_type="string", is_nullable=True, ordinal_position=i + 1)
                    for i, c in enumerate(cols) if c
                ]
            if key.endswith(".parquet"):
                # M-008: read ONLY the parquet schema (footer + metadata), not
                # the column data. pyarrow.parquet.read_schema seeks the footer
                # via the file-like's range reads, so this stays a small,
                # bounded download even for multi-GB files.
                return self._infer_parquet_columns(client, schema_name, table_name, key)
            return [ColumnInfo(schema_name=schema_name, table_name=table_name,
                               column_name="data", data_type="string", is_nullable=True, ordinal_position=1)]
        except DiscoveryError:
            raise
        except Exception as exc:
            raise DiscoveryError(f"Column inference failed: {exc}", "s3") from exc

    def _infer_parquet_columns(
        self, client, bucket: str, key: str, table_name: str
    ) -> list[ColumnInfo]:
        """List columns of a parquet object by reading JUST its schema.

        M-008: replaces the placeholder ``"data"`` column with the real
        parquet field names + types. ``pyarrow.parquet.read_schema`` is given a
        seekable, S3-backed file-like (`_S3RangeFile`) so it fetches only the
        footer/metadata via ranged GETs — never the whole object, which can be
        many GB. ``pyarrow`` is lazy-imported so the rest of the connector
        still imports (and CSV/JSON inference still works) when pyarrow is
        absent — a clear DiscoveryError is raised instead.
        """
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise DiscoveryError(
                "pyarrow not installed — parquet column inference is unavailable. "
                "Add pyarrow to backend/requirements.txt to enable it.",
                "s3",
            ) from exc

        fileobj = _S3RangeFile(client, bucket, key)
        schema = pq.read_schema(fileobj)
        return [
            ColumnInfo(
                schema_name=bucket,
                table_name=table_name,
                column_name=field.name,
                data_type=str(field.type),
                is_nullable=bool(field.nullable),
                ordinal_position=i + 1,
            )
            for i, field in enumerate(schema)
        ]

    # M-008: cap a single header read at 1 MiB so a CSV whose first line is the
    # whole file (no trailing newline) cannot force an unbounded GET.
    _MAX_HEADER_BYTES = 1 << 20  # 1 MiB
    _HEADER_CHUNK = 65536        # 64 KiB per ranged GET

    def _read_first_line(self, client, bucket: str, key: str) -> str:
        """Read bytes from `key` in growing ranges until the first newline.

        Returns the decoded first line WITHOUT the trailing newline. Falls back
        to whatever was read (up to _MAX_HEADER_BYTES) if no newline is present —
        better a long single-column header than a silently truncated one.
        """
        buf = b""
        start = 0
        while len(buf) < self._MAX_HEADER_BYTES:
            end = start + self._HEADER_CHUNK - 1
            try:
                obj = client.get_object(Bucket=bucket, Key=key, Range=f"bytes={start}-{end}")
                chunk = obj["Body"].read()
            except Exception:
                # Range past EOF (or a backend that rejects the range) — stop
                # with whatever we have.
                break
            if not chunk:
                break
            buf += chunk
            nl = buf.find(b"\n")
            if nl != -1:
                buf = buf[:nl]
                break
            if len(chunk) < self._HEADER_CHUNK:
                # Short read → reached EOF without a newline.
                break
            start += self._HEADER_CHUNK
        return buf[: self._MAX_HEADER_BYTES].decode("utf-8", errors="replace").rstrip("\r")

    async def get_row_count(self, schema_name: str, table_name: str) -> RowCountResult:
        return RowCountResult(schema_name=schema_name, table_name=table_name, row_count=0)


class _S3RangeFile:
    """A minimal seekable, read-only file-like backed by S3 ranged GETs.

    M-008: lets ``pyarrow.parquet.read_schema`` read a remote parquet object's
    footer/metadata without downloading the whole file. pyarrow seeks to the
    end for the 4-byte magic + footer length, then back to read the footer, so
    only a few small ranges are ever fetched. The object size is resolved once
    via a HEAD (``content_length``) and ranged GETs (``Range: bytes=start-end``)
    satisfy each read.
    """

    def __init__(self, client, bucket: str, key: str):
        self._client = client
        self._bucket = bucket
        self._key = key
        self._pos = 0
        self._size: int | None = None

    # ── sizing ───────────────────────────────────────────────────────
    @property
    def size(self) -> int:
        if self._size is None:
            head = self._client.head_object(Bucket=self._bucket, Key=self._key)
            self._size = int(head["ContentLength"])
        return self._size

    # ── file-like protocol pyarrow relies on ─────────────────────────
    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:      # SEEK_SET
            self._pos = offset
        elif whence == 1:    # SEEK_CUR
            self._pos += offset
        elif whence == 2:    # SEEK_END
            self._pos = self.size + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        if self._pos < 0:
            self._pos = 0
        return self._pos

    def read(self, length: int = -1) -> bytes:
        size = self.size
        if self._pos >= size:
            return b""
        if length is None or length < 0:
            end = size - 1
        else:
            end = min(self._pos + length, size) - 1
        if end < self._pos:
            return b""
        obj = self._client.get_object(
            Bucket=self._bucket,
            Key=self._key,
            Range=f"bytes={self._pos}-{end}",
        )
        data = obj["Body"].read()
        self._pos += len(data)
        return data

    def close(self) -> None:  # pyarrow may call close() on wrap-up
        pass

    @property
    def closed(self) -> bool:
        return False
