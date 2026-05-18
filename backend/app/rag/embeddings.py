from __future__ import annotations

import asyncio
import hashlib
import json
import math
import struct
from typing import Protocol, runtime_checkable

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingProviderError(RuntimeError):
    pass


class StubEmbeddingService:
    def __init__(self, dim: int | None = None) -> None:
        resolved = dim if dim is not None else settings.embedding_dim
        if resolved <= 0:
            raise ValueError(f"dim must be positive, got {resolved}")
        self._dim = resolved

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    def _vector_for(self, text: str) -> list[float]:
        raw = hashlib.shake_256(text.encode("utf-8")).digest(self._dim * 4)
        values = [
            struct.unpack_from(">I", raw, i * 4)[0] / 0xFFFFFFFF * 2.0 - 1.0
            for i in range(self._dim)
        ]
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0.0:
            return [1.0] + [0.0] * (self._dim - 1)
        return [v / norm for v in values]


class OpenRouterEmbeddingService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        retries: int,
        batch_size: int,
        dim: int,
        _transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._retries = retries
        self._batch_size = batch_size
        self._dim = dim
        self._transport = _transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            vectors = await self._embed_batch(batch)
            result.extend(vectors)
        return result

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://docbrain.nikulshin-dev.online",
            "Content-Type": "application/json",
        }
        body = json.dumps({"model": self._model, "input": batch}).encode()

        for attempt in range(self._retries + 1):
            logger.info("embedding_request", batch_size=len(batch), attempt=attempt)
            client_kwargs: dict = {"timeout": self._timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.post(url, content=body, headers=headers)

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self._retries:
                    logger.warning("embedding_retry", attempt=attempt, status=resp.status_code)
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
                raise EmbeddingProviderError(
                    f"embedding request failed after {attempt + 1} attempt(s): HTTP {resp.status_code}"
                )

            resp.raise_for_status()
            data = resp.json()
            vectors = [item["embedding"] for item in data["data"]]
            for vec in vectors:
                if len(vec) != self._dim:
                    raise EmbeddingProviderError(
                        f"expected embedding dim {self._dim}, got {len(vec)}"
                    )
            return vectors

        raise EmbeddingProviderError("embedding_batch unreachable")


def get_embedding_service() -> EmbeddingService:
    provider = settings.embedding_provider
    if provider == "stub":
        return StubEmbeddingService()
    if provider == "openrouter":
        if settings.openrouter_api_key is None:
            raise RuntimeError("OPENROUTER_API_KEY is required when EMBEDDING_PROVIDER=openrouter")
        return OpenRouterEmbeddingService(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_embedding_model,
            timeout=settings.openrouter_timeout,
            retries=settings.openrouter_retries,
            batch_size=settings.embedding_batch_size,
            dim=settings.embedding_dim,
        )
    raise ValueError(f"unknown embedding provider: {provider}")
