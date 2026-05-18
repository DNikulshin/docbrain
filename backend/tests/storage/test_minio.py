"""Integration tests for MinioStorage against a live MinIO instance.

Skipped automatically when MINIO_ACCESS_KEY is not set in the environment.
Run with: pytest -v -m integration
"""

import os
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def minio_settings():
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    if not access_key:
        pytest.skip("MINIO_ACCESS_KEY not set — skipping MinIO integration tests")
    return {
        "endpoint": os.environ.get("MINIO_ENDPOINT", "http://home-codespaces-minio-1:9000"),
        "access_key": access_key,
        "secret_key": os.environ.get("MINIO_SECRET_KEY", ""),
    }


@pytest_asyncio.fixture(scope="module")
async def minio_client_and_bucket(minio_settings):
    import aiobotocore.session as aio_session

    bucket = f"docbrain-test-{uuid.uuid4().hex[:8]}"
    kwargs = dict(
        aws_access_key_id=minio_settings["access_key"],
        aws_secret_access_key=minio_settings["secret_key"],
        region_name="us-east-1",
    )
    s = aio_session.get_session()
    async with s.create_client("s3", endpoint_url=minio_settings["endpoint"], **kwargs) as client:
        await client.create_bucket(Bucket=bucket)
        try:
            yield client, bucket
        finally:
            # cleanup: delete all objects then bucket
            try:
                paginator = client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=bucket):
                    for obj in page.get("Contents", []):
                        await client.delete_object(Bucket=bucket, Key=obj["Key"])
                await client.delete_bucket(Bucket=bucket)
            except Exception:
                pass


@pytest_asyncio.fixture
async def storage(minio_client_and_bucket, minio_settings):
    from app.storage.minio import MinioStorage

    client, bucket = minio_client_and_bucket
    return MinioStorage(client, client, bucket=bucket, presign_ttl=300)


async def test_put_and_head_object(storage) -> None:
    key = f"test/{uuid.uuid4().hex}.txt"
    data = b"hello minio"

    await storage.put_object(key, data, "text/plain")
    assert await storage.head_object(key) is True


async def test_head_object_missing(storage) -> None:
    assert await storage.head_object(f"missing/{uuid.uuid4().hex}") is False


async def test_presigned_url_contains_key(storage) -> None:
    key = f"test/{uuid.uuid4().hex}.txt"
    await storage.put_object(key, b"data", "text/plain")

    url = storage.generate_presigned_url(key)
    assert key in url


async def test_delete_object(storage) -> None:
    key = f"test/{uuid.uuid4().hex}.txt"
    await storage.put_object(key, b"bye", "text/plain")
    assert await storage.head_object(key) is True

    await storage.delete_object(key)
    assert await storage.head_object(key) is False


async def test_health(storage) -> None:
    assert await storage.health() is True
