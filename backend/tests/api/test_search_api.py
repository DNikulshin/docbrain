from httpx import AsyncClient


async def test_post_search_returns_top_hit_for_exact_text(async_client: AsyncClient) -> None:
    text = "alpha document content"
    upload = await async_client.post(
        "/api/documents",
        files={"file": ("alpha.txt", text.encode("utf-8"), "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    response = await async_client.post(
        "/api/search",
        json={"query": text, "top_k": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    hit = body[0]
    assert hit["document_id"] == doc_id
    assert hit["text"] == text
    assert hit["ord"] == 0
    assert "chunk_id" in hit
    assert hit["distance"] < 1e-6


async def test_post_search_default_top_k_is_five(async_client: AsyncClient) -> None:
    for i in range(7):
        await async_client.post(
            "/api/documents",
            files={"file": (f"doc-{i}.txt", f"content-{i}".encode(), "text/plain")},
        )

    response = await async_client.post("/api/search", json={"query": "content-0"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5


async def test_post_search_empty_query_returns_422(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/search", json={"query": ""})
    assert response.status_code == 422


async def test_post_search_top_k_zero_returns_422(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/search", json={"query": "x", "top_k": 0})
    assert response.status_code == 422


async def test_post_search_top_k_too_large_returns_422(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/search", json={"query": "x", "top_k": 100})
    assert response.status_code == 422


async def test_post_search_on_empty_db_returns_empty_list(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/search", json={"query": "anything"})
    assert response.status_code == 200
    assert response.json() == []
