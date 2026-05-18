from __future__ import annotations

import io

import docx as _docx
import httpx
import pypdf
import pytest

from app.parsers.url import parse_url

_HTML = b"""
<html><head><title>Test</title></head>
<body><article><p>Hello from the web page content.</p></article></body>
</html>
"""

_PDF_BYTES: bytes


def _make_docx_bytes(text: str) -> bytes:
    doc = _docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf_bytes() -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _mock_transport(
    content: bytes,
    content_type: str,
    content_length: int | None = None,
) -> httpx.MockTransport:
    headers = {"content-type": content_type}
    if content_length is not None:
        headers["content-length"] = str(content_length)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers=headers)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_html_url_returns_text():
    transport = _mock_transport(_HTML, "text/html")
    async with httpx.AsyncClient(transport=transport) as http:
        text, raw, filename, ct = await parse_url("http://example.com/page", http, 10_000_000)
    assert isinstance(text, str)
    assert raw == _HTML
    assert "html" in ct


@pytest.mark.asyncio
async def test_html_url_filename_derived_from_path():
    transport = _mock_transport(_HTML, "text/html")
    async with httpx.AsyncClient(transport=transport) as http:
        _, _, filename, _ = await parse_url("http://example.com/about", http, 10_000_000)
    assert "about" in filename


@pytest.mark.asyncio
async def test_html_url_default_filename_for_root():
    transport = _mock_transport(_HTML, "text/html")
    async with httpx.AsyncClient(transport=transport) as http:
        _, _, filename, _ = await parse_url("http://example.com/", http, 10_000_000)
    assert filename  # non-empty


@pytest.mark.asyncio
async def test_pdf_url_returns_str():
    pdf_bytes = _make_pdf_bytes()
    transport = _mock_transport(pdf_bytes, "application/pdf")
    async with httpx.AsyncClient(transport=transport) as http:
        text, raw, filename, ct = await parse_url("http://example.com/doc.pdf", http, 10_000_000)
    assert isinstance(text, str)
    assert raw == pdf_bytes
    assert ct == "application/pdf"
    assert filename.endswith(".pdf")


@pytest.mark.asyncio
async def test_docx_url_returns_text():
    docx_bytes = _make_docx_bytes("DOCX from URL")
    ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    transport = _mock_transport(docx_bytes, ct)
    async with httpx.AsyncClient(transport=transport) as http:
        text, _, _, _ = await parse_url("http://example.com/doc.docx", http, 10_000_000)
    assert "DOCX from URL" in text


@pytest.mark.asyncio
async def test_plain_text_url():
    transport = _mock_transport(b"plain text content", "text/plain")
    async with httpx.AsyncClient(transport=transport) as http:
        text, _, _, _ = await parse_url("http://example.com/file.txt", http, 10_000_000)
    assert "plain text content" in text


@pytest.mark.asyncio
async def test_size_limit_via_content_length():
    transport = _mock_transport(b"x" * 100, "text/html", content_length=200)
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ValueError, match="size limit"):
            await parse_url("http://example.com/", http, max_bytes=100)


@pytest.mark.asyncio
async def test_size_limit_via_stream():
    big = b"x" * 200
    transport = _mock_transport(big, "text/html")
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ValueError, match="size limit"):
            await parse_url("http://example.com/", http, max_bytes=100)


@pytest.mark.asyncio
async def test_unsupported_content_type_raises():
    transport = _mock_transport(b"\x00\x01", "application/octet-stream")
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ValueError, match="unsupported content type"):
            await parse_url("http://example.com/blob.bin", http, 10_000_000)
