from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from app.rag.embeddings import EmbeddingProviderError, OpenRouterEmbeddingService

_DIM = 4


def _make_response(vectors: list[list[float]], status: int = 200) -> httpx.Response:
    body = json.dumps({"data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)]})
    return httpx.Response(status, text=body)


def _error_response(status: int) -> httpx.Response:
    return httpx.Response(status, text=json.dumps({"error": "server error"}))


class _SequentialTransport(httpx.AsyncBaseTransport):
    """Выдаёт ответы по одному на каждый запрос."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses: AsyncIterator[httpx.Response] = iter(responses)  # type: ignore[assignment]
        self._iter = iter(responses)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return next(self._iter)


def _make_svc(
    responses: list[httpx.Response],
    batch_size: int = 10,
    retries: int = 2,
    dim: int = _DIM,
) -> OpenRouterEmbeddingService:
    transport = _SequentialTransport(responses)
    return OpenRouterEmbeddingService(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="openai/text-embedding-3-small",
        timeout=5.0,
        retries=retries,
        batch_size=batch_size,
        dim=dim,
        _transport=transport,
    )


def _vec(seed: int) -> list[float]:
    return [float(seed)] * _DIM


async def test_happy_path_single_batch(monkeypatch):
    monkeypatch.setattr("app.rag.embeddings.asyncio.sleep", lambda _: None)
    texts = ["a", "b", "c"]
    expected = [_vec(1), _vec(2), _vec(3)]
    svc = _make_svc([_make_response(expected)])
    result = await svc.embed(texts)
    assert result == expected


async def test_two_batches_preserve_order(monkeypatch):
    monkeypatch.setattr("app.rag.embeddings.asyncio.sleep", lambda _: None)
    texts = ["a", "b", "c", "d", "e"]
    batch1 = [_vec(1), _vec(2)]
    batch2 = [_vec(3), _vec(4)]
    batch3 = [_vec(5)]
    svc = _make_svc(
        [_make_response(batch1), _make_response(batch2), _make_response(batch3)],
        batch_size=2,
    )
    result = await svc.embed(texts)
    assert result == batch1 + batch2 + batch3


async def _noop_sleep(_: float) -> None:
    pass


async def test_retry_on_503_then_success(monkeypatch):
    monkeypatch.setattr("app.rag.embeddings.asyncio.sleep", _noop_sleep)
    expected = [_vec(7)]
    svc = _make_svc([_error_response(503), _make_response(expected)], retries=2)
    result = await svc.embed(["hello"])
    assert result == expected


async def test_exhausted_retries_raises(monkeypatch):
    monkeypatch.setattr("app.rag.embeddings.asyncio.sleep", _noop_sleep)
    svc = _make_svc(
        [_error_response(503), _error_response(503), _error_response(503)],
        retries=2,
    )
    with pytest.raises(EmbeddingProviderError, match="attempt"):
        await svc.embed(["hello"])


async def test_dimension_mismatch_raises(monkeypatch):
    monkeypatch.setattr("app.rag.embeddings.asyncio.sleep", _noop_sleep)
    wrong_dim_vector = [1.0, 2.0, 3.0]  # длина 3, а dim=4
    svc = _make_svc([_make_response([wrong_dim_vector])], dim=_DIM)
    with pytest.raises(EmbeddingProviderError, match="dim"):
        await svc.embed(["hello"])
