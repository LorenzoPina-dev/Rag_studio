"""Helpers to convert runtime payloads into JSON-safe structures.

Node outputs may contain Pydantic models, enums, datetimes, and nested
collections. Artifact storage and API result views must be able to serialize
them without losing structure (unlike a plain ``default=str`` fallback).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any


def to_jsonable(value: Any) -> Any:
    """Recursively convert common Python/Pydantic values into JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if hasattr(value, "model_dump"):
        try:
            return to_jsonable(value.model_dump(mode="json"))
        except Exception:
            return to_jsonable(value.model_dump())
    return str(value)
