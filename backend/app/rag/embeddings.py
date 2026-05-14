from __future__ import annotations

import hashlib
import math
import struct
from typing import Protocol, runtime_checkable

from app.config import settings


@runtime_checkable
class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


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
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("OpenRouter embedding service will be implemented in sprint 3")


def get_embedding_service() -> EmbeddingService:
    provider = settings.embedding_provider
    if provider == "stub":
        return StubEmbeddingService()
    if provider == "openrouter":
        return OpenRouterEmbeddingService()
    raise ValueError(f"unknown embedding provider: {provider}")
