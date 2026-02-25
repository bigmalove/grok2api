"""
Pydantic v1/v2 compatibility helpers.
"""

from __future__ import annotations

from typing import Any


def model_dump(instance: Any, **kwargs) -> dict:
    """Return model data for both Pydantic v1 and v2."""
    dump = getattr(instance, "model_dump", None)
    if callable(dump):
        return dump(**kwargs)
    as_dict = getattr(instance, "dict", None)
    if callable(as_dict):
        return as_dict(**kwargs)
    raise TypeError(f"Object of type {type(instance).__name__} is not a Pydantic model")


def model_field_names(model_cls: Any) -> set[str]:
    """Return field names for both Pydantic v1 and v2 model classes."""
    fields = getattr(model_cls, "model_fields", None)
    if isinstance(fields, dict):
        return set(fields.keys())
    legacy_fields = getattr(model_cls, "__fields__", None)
    if isinstance(legacy_fields, dict):
        return set(legacy_fields.keys())
    return set()


__all__ = ["model_dump", "model_field_names"]
