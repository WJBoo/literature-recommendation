from __future__ import annotations

from dataclasses import dataclass
import base64
from hashlib import sha256
import mimetypes
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import quote
from uuid import uuid4

from app.core.config import settings


DATA_URL_RE = re.compile(r"^data:(?P<content_type>[^;,]+);base64,(?P<payload>.+)$", re.DOTALL)
REMOTE_MEDIA_PREFIXES = ("http://", "https://", "/media/")


class StorageConfigurationError(RuntimeError):
    pass


class StorageUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    url: str
    backend: str
    content_type: str
    byte_size: int
    sha256: str
    local_path: str | None = None


class ObjectStorageService:
    """Small storage adapter for user media and corpus artifacts.

    Backends:
    - inline: keep browser data URLs in the JSON prototype store.
    - local: write files under MEDIA_UPLOAD_DIR and serve them from /media.
    - s3: upload to S3-compatible object storage such as AWS S3, R2, or MinIO.
    """

    def __init__(self, backend: str | None = None) -> None:
        self.backend = normalize_backend(backend or settings.media_storage_backend)

    @property
    def stores_externally(self) -> bool:
        return self.backend in {"local", "s3"}

    def should_store_reference(self, value: str) -> bool:
        return self.stores_externally and is_data_url(value)

    def store_data_url(
        self,
        data_url: str,
        *,
        key_prefix: str,
        filename_hint: str,
        allowed_content_prefixes: Iterable[str],
    ) -> StoredObject:
        if not is_data_url(data_url):
            return StoredObject(
                key=data_url,
                url=data_url,
                backend="external",
                content_type=infer_reference_content_type(data_url),
                byte_size=0,
                sha256="",
            )

        content_type, payload = parse_data_url(data_url)
        if not any(content_type.startswith(prefix) for prefix in allowed_content_prefixes):
            raise StorageUploadError(f"Unsupported media type: {content_type}")

        if self.backend == "inline":
            digest = sha256(payload).hexdigest()
            return StoredObject(
                key=digest,
                url=data_url,
                backend="inline",
                content_type=content_type,
                byte_size=len(payload),
                sha256=digest,
            )

        extension = extension_for_content_type(content_type)
        key = make_storage_key(key_prefix, filename_hint, extension)
        return self.upload_bytes(payload, key=key, content_type=content_type)

    def store_file(
        self,
        path: Path,
        *,
        key_prefix: str,
        content_type: str | None = None,
    ) -> StoredObject:
        if self.backend == "inline":
            raise StorageConfigurationError("File artifact storage requires MEDIA_STORAGE_BACKEND=local or s3.")
        content = path.read_bytes()
        guessed_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        key = make_storage_key(key_prefix, path.name, "")
        return self.upload_bytes(content, key=key, content_type=guessed_type)

    def upload_bytes(self, content: bytes, *, key: str, content_type: str) -> StoredObject:
        digest = sha256(content).hexdigest()
        clean_key = normalize_key(key)
        if self.backend == "local":
            return self._upload_local(content, key=clean_key, content_type=content_type, digest=digest)
        if self.backend == "s3":
            return self._upload_s3(content, key=clean_key, content_type=content_type, digest=digest)
        raise StorageConfigurationError(f"Unsupported storage backend: {self.backend}")

    def _upload_local(
        self,
        content: bytes,
        *,
        key: str,
        content_type: str,
        digest: str,
    ) -> StoredObject:
        destination = settings.media_upload_dir / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredObject(
            key=key,
            url=public_url_for_key(key),
            backend="local",
            content_type=content_type,
            byte_size=len(content),
            sha256=digest,
            local_path=str(destination),
        )

    def _upload_s3(
        self,
        content: bytes,
        *,
        key: str,
        content_type: str,
        digest: str,
    ) -> StoredObject:
        bucket = settings.object_storage_bucket
        if not bucket:
            raise StorageConfigurationError("OBJECT_STORAGE_BUCKET is required for MEDIA_STORAGE_BACKEND=s3.")
        public_base_url = settings.object_storage_public_base_url
        if not public_base_url:
            raise StorageConfigurationError(
                "OBJECT_STORAGE_PUBLIC_BASE_URL is required so uploaded media can be rendered."
            )

        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on deployment extra.
            raise StorageConfigurationError("Install boto3 to use S3-compatible media storage.") from exc

        client_kwargs: dict[str, str] = {}
        if settings.object_storage_region:
            client_kwargs["region_name"] = settings.object_storage_region
        if settings.object_storage_endpoint_url:
            client_kwargs["endpoint_url"] = settings.object_storage_endpoint_url
        if settings.object_storage_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.object_storage_access_key_id
        if settings.object_storage_secret_access_key:
            client_kwargs["aws_secret_access_key"] = settings.object_storage_secret_access_key

        client = boto3.client("s3", **client_kwargs)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(
            key=key,
            url=f"{public_base_url.rstrip('/')}/{quote(key)}",
            backend="s3",
            content_type=content_type,
            byte_size=len(content),
            sha256=digest,
        )


def normalize_backend(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in {"filesystem", "file", "local"}:
        return "local"
    if cleaned in {"s3", "r2", "minio", "object"}:
        return "s3"
    return "inline"


def is_data_url(value: str) -> bool:
    return value.startswith("data:")


def is_renderable_media_reference(value: str, *, media_type: str) -> bool:
    if is_data_url(value):
        return value.startswith(f"data:{media_type}/")
    return value.startswith(REMOTE_MEDIA_PREFIXES)


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    match = DATA_URL_RE.match(data_url)
    if match is None:
        raise StorageUploadError("Media must be a base64 data URL.")
    content_type = match.group("content_type").strip().lower()
    try:
        payload = base64.b64decode(match.group("payload"), validate=True)
    except ValueError as exc:
        raise StorageUploadError("Media data URL is not valid base64.") from exc
    return content_type, payload


def infer_reference_content_type(value: str) -> str:
    if value.startswith("data:"):
        try:
            return parse_data_url(value)[0]
        except StorageUploadError:
            return "application/octet-stream"
    return mimetypes.guess_type(value)[0] or "application/octet-stream"


def extension_for_content_type(content_type: str) -> str:
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0])
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ""


def make_storage_key(key_prefix: str, filename_hint: str, extension: str) -> str:
    prefix = normalize_key(key_prefix)
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename_hint.strip()).strip("-._")
    if not stem:
        stem = "media"
    if extension and not stem.lower().endswith(extension.lower()):
        stem = f"{stem}{extension}"
    return normalize_key(f"{prefix}/{uuid4().hex}-{stem}")


def normalize_key(value: str) -> str:
    parts = [part for part in value.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    return "/".join(parts)


def public_url_for_key(key: str) -> str:
    base_url = settings.media_public_base_url.rstrip("/") or "/media"
    return f"{base_url}/{quote(key)}"
