from __future__ import annotations

import io

import pypdf


def parse_pdf(payload: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(payload))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
