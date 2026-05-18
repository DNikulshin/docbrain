import math

import pytest

from app.config import settings
from app.rag.embeddings import (
    EmbeddingService,
    OpenRouterEmbeddingService,
    StubEmbeddingService,
    get_embedding_service,
)


async def test_stub_embed_returns_vector_of_configured_dim():
    svc = StubEmbeddingService()
    [vec] = await svc.embed(["hello"])
    assert len(vec) == settings.embedding_dim


async def test_stub_embed_is_deterministic():
    svc = StubEmbeddingService()
    [v1] = await svc.embed(["the quick brown fox"])
    [v2] = await svc.embed(["the quick brown fox"])
    assert v1 == v2


async def test_stub_embed_is_l2_normalized():
    svc = StubEmbeddingService()
    [vec] = await svc.embed(["normalize me"])
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-9)


async def test_stub_embed_different_texts_produce_different_vectors():
    svc = StubEmbeddingService()
    [va, vb] = await svc.embed(["a", "b"])
    assert va != vb


async def test_stub_embed_batch_preserves_order_and_length():
    svc = StubEmbeddingService()
    inputs = ["alpha", "beta", "gamma"]
    batch = await svc.embed(inputs)
    assert len(batch) == 3
    for text, batch_vec in zip(inputs, batch, strict=True):
        [single_vec] = await svc.embed([text])
        assert batch_vec == single_vec


async def test_stub_embed_empty_string_returns_valid_vector():
    svc = StubEmbeddingService()
    [vec] = await svc.embed([""])
    assert len(vec) == settings.embedding_dim
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-9)


async def test_stub_embed_custom_dim_via_constructor():
    svc = StubEmbeddingService(dim=8)
    [vec] = await svc.embed(["custom"])
    assert len(vec) == 8
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-9)


def test_stub_embed_invalid_dim_zero_raises():
    with pytest.raises(ValueError, match="dim must be positive"):
        StubEmbeddingService(dim=0)


def test_stub_embed_invalid_dim_negative_raises():
    with pytest.raises(ValueError, match="dim must be positive"):
        StubEmbeddingService(dim=-1)


def test_get_embedding_service_returns_stub_by_default():
    svc = get_embedding_service()
    assert isinstance(svc, StubEmbeddingService)
    assert isinstance(svc, EmbeddingService)


def test_get_embedding_service_openrouter_no_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_embedding_service()


def test_get_embedding_service_openrouter_with_key_returns_instance(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test")
    svc = get_embedding_service()
    assert isinstance(svc, OpenRouterEmbeddingService)
