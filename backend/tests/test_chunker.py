import pytest

from app.rag.chunker import split_text


def test_split_empty_returns_empty_list():
    assert split_text("") == []


def test_split_short_returns_single_chunk():
    text = "abc"
    assert split_text(text, size=10, overlap=2) == [text]


def test_split_exact_size_boundary():
    text = "a" * 800
    assert split_text(text) == [text]


def test_split_size_plus_one():
    text = "a" * 801
    chunks = split_text(text, size=800, overlap=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 800
    assert len(chunks[1]) == 101


def test_split_long_text_overlap_correct():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(2500))
    chunks = split_text(text, size=800, overlap=100)
    assert len(chunks) > 1
    for i in range(len(chunks) - 1):
        assert chunks[i][-100:] == chunks[i + 1][:100], f"overlap mismatch at i={i}"


def test_split_long_text_covers_all_chars():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(2500))
    chunks = split_text(text, size=800, overlap=100)
    reconstructed = chunks[0] + "".join(c[100:] for c in chunks[1:])
    assert reconstructed == text
    assert len(reconstructed) == len(text)


def test_split_chunks_max_size():
    text = "x" * 3000
    chunks = split_text(text, size=800, overlap=100)
    for c in chunks[:-1]:
        assert len(c) == 800
    assert 0 < len(chunks[-1]) <= 800


def test_split_zero_overlap_is_disjoint():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(1234))
    chunks = split_text(text, size=100, overlap=0)
    assert "".join(chunks) == text


def test_split_custom_params_deterministic():
    result = split_text("abcdefghijklmnopqrst", size=10, overlap=3)
    assert result == ["abcdefghij", "hijklmnopq", "opqrst"]


def test_split_invalid_size_zero_raises():
    with pytest.raises(ValueError, match="size must be positive"):
        split_text("hello", size=0, overlap=0)


def test_split_invalid_size_negative_raises():
    with pytest.raises(ValueError, match="size must be positive"):
        split_text("hello", size=-1, overlap=0)


def test_split_invalid_overlap_negative_raises():
    with pytest.raises(ValueError, match="overlap must be non-negative"):
        split_text("hello", size=5, overlap=-1)


def test_split_invalid_overlap_equal_size_raises():
    with pytest.raises(ValueError, match="overlap must be strictly less than size"):
        split_text("hello", size=5, overlap=5)


def test_split_invalid_overlap_greater_than_size_raises():
    with pytest.raises(ValueError, match="overlap must be strictly less than size"):
        split_text("hello", size=5, overlap=6)
