from __future__ import annotations

from urllib.parse import urlparse

import httpx
import trafilatura

from app.parsers.docx import parse_docx
from app.parsers.pdf import parse_pdf

_CHUNK_SIZE = 65_536


async def parse_url(
    url: str,
    http: httpx.AsyncClient,
    max_bytes: int,
) -> tuple[str, bytes, str, str]:
    """Fetch URL and extract text. Returns (text, raw_bytes, filename, content_type)."""
    async with http.stream("GET", url) as response:
        response.raise_for_status()

        cl = response.headers.get("content-length")
        if cl is not None and int(cl) > max_bytes:
            raise ValueError(f"remote content exceeds size limit: {cl} bytes")

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes(_CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"stream exceeded size limit of {max_bytes} bytes")
            chunks.append(chunk)

        raw = b"".join(chunks)
        ct = response.headers.get("content-type", "text/html").split(";")[0].strip()

    filename = _filename_from_url(url, ct)

    if "html" in ct:
        extracted = trafilatura.extract(raw.decode("utf-8", errors="replace"))
        text = extracted or ""
    elif ct == "application/pdf":
        text = parse_pdf(raw)
    elif "wordprocessingml" in ct:
        text = parse_docx(raw)
    elif "text/plain" in ct:
        text = raw.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"unsupported content type: {ct!r}")

    return text, raw, filename, ct


def _filename_from_url(url: str, content_type: str) -> str:
    path = urlparse(url).path.rstrip("/")
    name = path.split("/")[-1] if path else ""
    if not name:
        name = _default_name(content_type)
    elif "." not in name:
        name = name + _ext_for_ct(content_type)
    return name


def _ext_for_ct(content_type: str) -> str:
    if "html" in content_type:
        return ".html"
    if "pdf" in content_type:
        return ".pdf"
    if "wordprocessingml" in content_type:
        return ".docx"
    return ".txt"


def _default_name(content_type: str) -> str:
    return "document" + _ext_for_ct(content_type)
