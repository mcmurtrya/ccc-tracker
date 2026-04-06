from citycouncil.rag.search import body_preview


def test_body_preview_short_unchanged() -> None:
    assert body_preview("hello", 400) == "hello"


def test_body_preview_truncates_with_ellipsis() -> None:
    s = "a" * 500
    out = body_preview(s, 400)
    assert len(out) == 400
    assert out.endswith("…")


def test_body_preview_strips_whitespace() -> None:
    assert body_preview("  hi  ", 10) == "hi"
