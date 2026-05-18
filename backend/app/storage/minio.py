from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

logger = structlog.get_logger(__name__)


@runtime_checkable
class StorageProtocol(Protocol):
    async def put_object(self, key: str, data: bytes, content_type: str) -> None: ...
    async def head_object(self, key: str) -> bool: ...
    async def delete_object(self, key: str) -> None: ...
    def generate_presigned_url(self, key: str, ttl: int = 3600) -> str: ...
    async def health(self) -> bool: ...


class MinioStorage:
    """aiobotocore-based async S3/MinIO storage.

    _client        — internal endpoint (put, head, delete, health)
    _public_client — public endpoint (presigned URL host visible externally)
    """

    def __init__(
        self,
        client: S3Client,
        public_client: S3Client,
        *,
        bucket: str,
        presign_ttl: int = 3600,
    ) -> None:
        self._client = client
        self._public_client = public_client
        self._bucket = bucket
        self._presign_ttl = presign_ttl

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("storage_put", key=key, size=len(data))

    async def head_object(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            await self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    async def delete_object(self, key: str) -> None:
        await self._client.delete_object(Bucket=self._bucket, Key=key)
        logger.info("storage_delete", key=key)

    def generate_presigned_url(self, key: str, ttl: int | None = None) -> str:
        # generate_presigned_url is synchronous in aiobotocore (no network call)
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl if ttl is not None else self._presign_ttl,
        )

    async def health(self) -> bool:
        from botocore.exceptions import ClientError

        try:
            await self._client.head_bucket(Bucket=self._bucket)
            return True
        except ClientError:
            return False


class StubStorage:
    """In-memory storage for unit/API tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data

    async def head_object(self, key: str) -> bool:
        return key in self._store

    async def delete_object(self, key: str) -> None:
        self._store.pop(key, None)

    def generate_presigned_url(self, key: str, ttl: int | None = None) -> str:
        return f"http://stub/{key}"

    async def health(self) -> bool:
        return True
