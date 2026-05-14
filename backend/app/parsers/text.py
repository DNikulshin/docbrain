from __future__ import annotations


def parse_text(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")
