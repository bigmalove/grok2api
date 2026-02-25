"""
JSON compatibility layer.

Uses ``orjson`` when available and falls back to the standard ``json`` module.
"""

from __future__ import annotations

from typing import Any

try:
    import orjson as _orjson

    dumps = _orjson.dumps
    loads = _orjson.loads
    JSONDecodeError = _orjson.JSONDecodeError
    OPT_SORT_KEYS = _orjson.OPT_SORT_KEYS
    OPT_INDENT_2 = _orjson.OPT_INDENT_2
except Exception:  # pragma: no cover - fallback path
    import json as _json

    OPT_SORT_KEYS = 1 << 0
    OPT_INDENT_2 = 1 << 1
    JSONDecodeError = _json.JSONDecodeError

    def dumps(obj: Any, *, option: int = 0) -> bytes:
        kwargs: dict[str, Any] = {"ensure_ascii": False}
        if option & OPT_SORT_KEYS:
            kwargs["sort_keys"] = True
        if option & OPT_INDENT_2:
            kwargs["indent"] = 2
        return _json.dumps(obj, **kwargs).encode("utf-8")

    def loads(data: str | bytes | bytearray) -> Any:
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        return _json.loads(data)


__all__ = [
    "dumps",
    "loads",
    "JSONDecodeError",
    "OPT_SORT_KEYS",
    "OPT_INDENT_2",
]

