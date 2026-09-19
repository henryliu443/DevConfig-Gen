"""Reusable, path-aware validation helpers.

Providers use these primitives to collect every problem in one pass instead of
failing on the first field. Each helper appends a :class:`Diagnostic` to the
supplied list. The rendered message uses the leaf field name so it reads
naturally, for example ``port must be between 1 and 65535, got 99999``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .models import Diagnostic


class ValidationError(ValueError):
    """Raised when one or more validation errors are present."""

    def __init__(self, diagnostics: Sequence[Any]):
        self.diagnostics = tuple(_as_diagnostic(item) for item in diagnostics)
        self.errors = tuple(item.message for item in self.diagnostics)
        super().__init__("; ".join(self.errors))


def _as_diagnostic(value: Any) -> Diagnostic:
    if isinstance(value, Diagnostic):
        return value
    return Diagnostic(field="", message=str(value))


def _leaf(path: str) -> str:
    return path.rsplit(".", 1)[-1] if path else path


def is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def expect_mapping(value: Any, path: str, errors: list) -> Optional[Mapping]:
    if not is_mapping(value):
        errors.append(
            Diagnostic(path, f"{_leaf(path)} must be a mapping, got {_describe(value)}")
        )
        return None
    return value


def expect_string(value: Any, path: str, errors: list, *, allow_empty: bool = False) -> Optional[str]:
    leaf = _leaf(path)
    if not isinstance(value, str):
        errors.append(Diagnostic(path, f"{leaf} must be a string, got {_describe(value)}"))
        return None
    text = value.strip()
    if not text and not allow_empty:
        errors.append(Diagnostic(path, f"{leaf} must not be empty"))
        return None
    return text


def expect_integer(
    value: Any,
    path: str,
    errors: list,
    *,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> Optional[int]:
    leaf = _leaf(path)
    if not is_integer(value):
        errors.append(Diagnostic(path, f"{leaf} must be an integer, got {_describe(value)}"))
        return None
    if minimum is not None and maximum is not None:
        if value < minimum or value > maximum:
            errors.append(
                Diagnostic(path, f"{leaf} must be between {minimum} and {maximum}, got {value}")
            )
            return None
    elif minimum is not None and value < minimum:
        errors.append(Diagnostic(path, f"{leaf} must be >= {minimum}, got {value}"))
        return None
    elif maximum is not None and value > maximum:
        errors.append(Diagnostic(path, f"{leaf} must be <= {maximum}, got {value}"))
        return None
    return value


def expect_enum(
    value: Any,
    path: str,
    errors: list,
    *,
    allowed: Sequence[str],
    case_insensitive: bool = True,
) -> Optional[str]:
    leaf = _leaf(path)
    options = ", ".join(str(option) for option in allowed)
    if not isinstance(value, str):
        errors.append(
            Diagnostic(path, f"{leaf} must be one of {options}, got {_describe(value)}")
        )
        return None
    candidate = value.strip()
    if case_insensitive:
        for option in allowed:
            if candidate.lower() == option.lower():
                return option
    elif candidate in allowed:
        return candidate
    errors.append(Diagnostic(path, f"{leaf} must be one of {options}, got {value!r}"))
    return None


def expect_string_mapping(value: Any, path: str, errors: list) -> Optional[dict]:
    if not is_mapping(value):
        errors.append(
            Diagnostic(path, f"{_leaf(path)} must be a mapping of labels, got {_describe(value)}")
        )
        return None
    normalized = {}
    for key, item in value.items():
        key_text = str(key).strip()
        if not key_text:
            errors.append(Diagnostic(path, "label keys must not be empty"))
            continue
        if isinstance(item, (dict, list, tuple)):
            errors.append(
                Diagnostic(
                    f"{path}.{key_text}",
                    f"labels.{key_text} must be a scalar value, got {_describe(item)}",
                )
            )
            continue
        normalized[key_text] = "" if item is None else str(item)
    return normalized


def _describe(value: Any) -> str:
    if isinstance(value, str):
        return f"string {value!r}"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"boolean {value}"
    return f"{type(value).__name__} {value!r}"
