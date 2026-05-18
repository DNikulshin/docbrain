from __future__ import annotations

import io

import docx


def parse_docx(payload: bytes) -> str:
    doc = docx.Document(io.BytesIO(payload))
    return "\n".join(p.text for p in doc.paragraphs)
