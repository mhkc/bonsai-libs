"""Read json files."""

import json
from typing import Any, Mapping

from bonsai_libs.parse.exceptions import DataFormatError

from .types import StreamOrPath
from .utils import ensure_text_stream


def read_json(source: StreamOrPath, *, encoding: str = "utf-8") -> Any:
    """
    Read JSON from a path, string path, or file-like object (text or bytes).

    Returns decoded Python object (dict/list/...).
    """
    try:
        stream = ensure_text_stream(source, encoding=encoding)
        return json.loads(stream.read())
    except TypeError as exc:
        raise DataFormatError(f"Failed to read JSON from source of type {type(source)!r}") from exc


def require_mapping(obj: Any, *, what: str) -> Mapping[str, Any]:
    """Read JSON object and ensure it's a dict/mapping."""

    if not isinstance(obj, dict):
        raise DataFormatError(
            f"Expected object '{what}' to be a JSON object/dict, got {type(obj)!r}"
        )
    return obj
