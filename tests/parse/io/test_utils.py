"""Test helper functions."""

from pathlib import Path
from bonsai_libs.parse.io.utils import ensure_text_stream


def test_ensure_text_stream_from_path(tmp_path: Path):
    p = tmp_path / "f.txt"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    ts = ensure_text_stream(p)
    assert ts.read().startswith("a,b")


def test_ensure_text_stream_from_bytes():
    data = b"a,b\n1,2\n"
    ts = ensure_text_stream(data)
    assert ts.read().splitlines()[0] == "a,b"
