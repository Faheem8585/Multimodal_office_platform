"""Object storage abstraction: S3-compatible with a local-filesystem fallback.

Production uses S3/MinIO (configured via S3_* env vars). If no S3 endpoint is
configured (e.g. a developer laptop without MinIO), it transparently falls back
to a local directory so the app still runs. The interface is intentionally tiny
(put/get/delete/presign) so swapping backends never touches callers.
"""

import contextlib
import os
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def presigned_url(self, key: str, expires: int = 3600) -> str | None: ...


class LocalStorage:
    """Filesystem-backed fallback. Not for production scale, but keeps the app
    fully functional without object storage."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal: resolve and ensure it stays under root.
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.remove(self._path(key))

    def presigned_url(self, key: str, expires: int = 3600) -> str | None:
        # Served via the API's authenticated download endpoint instead.
        return None


class S3Storage:
    """S3-compatible backend (AWS S3, MinIO, etc.) using boto3."""

    def __init__(self) -> None:
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self._bucket = settings.s3_bucket

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_url(self, key: str, expires: int = 3600) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )


def get_storage() -> StorageBackend:
    """Pick the backend: S3 when configured, else local fallback."""
    if settings.s3_endpoint_url or settings.environment != "dev":
        try:
            return S3Storage()
        except Exception as exc:  # pragma: no cover - misconfig path
            log.error("s3_init_failed_falling_back_local", error=str(exc))
    log.warning("using_local_storage_fallback", dir=settings.storage_local_fallback_dir)
    return LocalStorage(settings.storage_local_fallback_dir)
