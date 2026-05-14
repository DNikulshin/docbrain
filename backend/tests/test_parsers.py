import pytest

from app.parsers import UnsupportedFormatError, parse, parse_markdown, parse_text


def test_parse_text_ascii():
    assert parse_text(b"hello world") == "hello world"


def test_parse_text_utf8_cyrillic():
    assert parse_text("привет мир".encode()) == "привет мир"


def test_parse_text_invalid_bytes_replaced():
    result = parse_text(b"\xff\xfe abc")
    assert "abc" in result
    assert "�" in result


def test_parse_text_empty():
    assert parse_text(b"") == ""


def test_parse_markdown_no_frontmatter_unchanged():
    src = "# title\n\nbody text\n"
    assert parse_markdown(src.encode()) == src


def test_parse_markdown_strips_frontmatter():
    src = b"---\ntitle: x\nauthor: me\n---\n# body\n"
    assert parse_markdown(src) == "# body\n"


def test_parse_markdown_strips_crlf_frontmatter():
    src = b"---\r\ntitle: x\r\n---\r\n# body\r\n"
    assert parse_markdown(src) == "# body\r\n"


def test_parse_markdown_strips_frontmatter_closed_with_dots():
    src = b"---\ntitle: x\n...\n# body\n"
    assert parse_markdown(src) == "# body\n"


def test_parse_markdown_keeps_horizontal_rule_in_body():
    src = "# title\n\n---\n\nbody\n"
    assert parse_markdown(src.encode()) == src


def test_parse_markdown_strips_empty_frontmatter():
    src = b"---\n---\n# body\n"
    assert parse_markdown(src) == "# body\n"


def test_parse_markdown_unclosed_frontmatter_left_alone():
    src = "---\ntitle: x\nno close here\n"
    assert parse_markdown(src.encode()) == src


def test_parse_dispatch_txt():
    assert parse("notes.txt", b"plain") == "plain"


def test_parse_dispatch_md():
    assert parse("readme.md", b"---\nt: x\n---\n# h\n") == "# h\n"


def test_parse_dispatch_markdown_extension():
    assert parse("doc.markdown", b"# h\n") == "# h\n"


def test_parse_dispatch_uppercase_extension():
    assert parse("README.MD", b"# h\n") == "# h\n"


def test_parse_unknown_extension_raises():
    with pytest.raises(UnsupportedFormatError, match="unsupported file extension"):
        parse("blob.bin", b"\x00\x01")


def test_parse_empty_filename_raises():
    with pytest.raises(UnsupportedFormatError, match="<none>"):
        parse("", b"data")


def test_parse_filename_without_extension_raises():
    with pytest.raises(UnsupportedFormatError, match="<none>"):
        parse("noext", b"data")
