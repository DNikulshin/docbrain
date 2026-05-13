from __future__ import annotations


def split_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= size:
        raise ValueError(
            f"overlap must be strictly less than size, got overlap={overlap}, size={size}"
        )

    if not text:
        return []
    if len(text) <= size:
        return [text]

    step = size - overlap
    chunks: list[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + size
        chunks.append(text[start:end])
        if end >= text_len:
            break
        start += step
    return chunks
