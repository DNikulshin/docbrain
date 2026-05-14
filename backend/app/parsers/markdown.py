from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?:.*?\r?\n)??(?:---|\.\.\.)[ \t]*\r?\n?",
    re.DOTALL,
)


def parse_markdown(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    return _FRONTMATTER_RE.sub("", text, count=1)
