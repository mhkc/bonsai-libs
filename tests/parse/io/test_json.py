"""Test reading json files."""

import io
from pathlib import Path

import json
from bonsai_libs.parse.io.json import read_json


def test_json_all_inputs(tmp_path: Path):
    """Test reading JSON from all supported input types."""

    payload = {"x": 1, "y": [2, 3]}
    raw = json.dumps(payload)

    # path
    p = tmp_path / "data.json"
    p.write_text(raw, encoding="utf-8")
    assert read_json(p) == payload

    # text stream
    assert read_json(io.StringIO(raw)) == payload

    # binary stream
    assert read_json(io.BytesIO(raw.encode())) == payload

    # bytes
    assert read_json(raw.encode()) == payload
