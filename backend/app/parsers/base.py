from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.parsers.markdown import parse_markdown
from app.parsers.text import parse_text


class UnsupportedFormatError(ValueError):
    pass


_PARSERS: dict[str, Callable[[bytes], str]] = {
    ".txt": parse_text,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
}


def parse(filename: str, payload: bytes) -> str:
    ext = Path(filename).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormatError(f"unsupported file extension: {ext or '<none>'}")
    return parser(payload)
