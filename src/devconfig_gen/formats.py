"""Loading and serializing structured configuration data.

JSON is handled by the standard library. YAML is handled by PyYAML when it is
installed and otherwise by a bundled, dependency-free parser that covers the
subset of YAML used for configuration documents. See ``README.md`` for the
exact support boundary.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Union

JSON = "json"
YAML = "yaml"

JSON_MEDIA_TYPE = "application/json"
YAML_MEDIA_TYPE = "application/yaml"

_MEDIA_TYPES = {
    JSON: JSON_MEDIA_TYPE,
    YAML: YAML_MEDIA_TYPE,
}

_FORMAT_ALIASES = {
    "json": JSON,
    "application/json": JSON,
    "yaml": YAML,
    "yml": YAML,
    "application/yaml": YAML,
    "application/x-yaml": YAML,
}

try:  # pragma: no cover - exercised only when PyYAML is installed
    import yaml as _pyyaml
except Exception:  # pragma: no cover - the common case on a clean install
    _pyyaml = None

HAS_PYYAML = _pyyaml is not None


class FormatError(ValueError):
    """Raised when input cannot be parsed or output cannot be serialized."""


class YamlError(FormatError):
    """Raised for errors raised by the bundled YAML subset parser."""


def deep_merge(base: Any, overlay: Any) -> Any:
    """Recursively merge overlay into base."""
    if isinstance(base, Mapping) and isinstance(overlay, Mapping):
        merged = dict(base)
        for key, value in overlay.items():
            if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return overlay


def normalize_format(value: Optional[str]) -> Optional[str]:
    """Return the canonical format name for ``value`` or ``None``."""

    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    try:
        return _FORMAT_ALIASES[key]
    except KeyError as exc:
        supported = ", ".join(sorted({JSON, YAML}))
        raise FormatError(f"unsupported format {value!r}; expected one of: {supported}") from exc


def format_from_media_type(media_type: str) -> str:
    key = str(media_type).strip().lower()
    if key in (JSON_MEDIA_TYPE, JSON):
        return JSON
    if key in (YAML_MEDIA_TYPE, YAML):
        return YAML
    raise FormatError(f"unsupported media type {media_type!r}")


def media_type_for(fmt: str) -> str:
    canonical = normalize_format(fmt)
    if canonical is None:
        raise FormatError("format must not be empty")
    return _MEDIA_TYPES[canonical]


def detect_format(*, path: Optional[Union[str, os.PathLike]] = None, text: Optional[str] = None) -> str:
    """Best-effort detection of a document format from a path and/or text."""

    if path is not None:
        suffix = Path(path).suffix.lower()
        if suffix == ".json":
            return JSON
        if suffix in (".yaml", ".yml"):
            return YAML
    if text is not None:
        stripped = text.lstrip("\ufeff \t\r\n")
        if stripped.startswith("{") or stripped.startswith("["):
            return JSON
        return YAML
    if path is not None:
        return YAML
    return JSON


def resolve_format(
    explicit: Optional[str] = None,
    *,
    name: Optional[Union[str, os.PathLike]] = None,
    path: Optional[Union[str, os.PathLike]] = None,
    default: str = JSON,
) -> str:
    """Resolve the effective format from explicit input, a filename, or a path."""

    canonical = normalize_format(explicit)
    if canonical is not None:
        return canonical
    if name is not None:
        suffix = Path(name).suffix.lower()
        if suffix == ".json":
            return JSON
        if suffix in (".yaml", ".yml"):
            return YAML
    if path is not None:
        return detect_format(path=path)
    return normalize_format(default) or JSON


def coerce_scalar(value: Any) -> Any:
    """Interpret a string as a JSON value when possible.

    ``"9090"`` becomes ``9090``, ``"true"`` becomes ``True``, ``"null"`` becomes
    ``None``. Non-JSON text such as ``"production"`` is returned unchanged, and
    non-string inputs pass through untouched.
    """

    if not isinstance(value, str):
        return value
    text = value.strip()
    if text == "":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def loads(text: str, fmt: Optional[str] = None) -> Any:
    """Parse ``text`` as JSON or YAML.

    When ``fmt`` is omitted the format is detected: JSON is attempted first
    because every JSON document is also a valid YAML document.
    """

    if not isinstance(text, str):
        raise FormatError(f"expected a string to parse, got {type(text).__name__}")
    canonical = normalize_format(fmt)
    if canonical is None:
        canonical = detect_format(text=text)
    if canonical == JSON:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FormatError(f"invalid JSON: {exc}") from exc
    return _yaml_loads(text)


def load_file(path: Union[str, os.PathLike], fmt: Optional[str] = None) -> Any:
    """Read and parse a JSON or YAML file."""

    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FormatError(f"cannot read {file_path}: {exc}") from exc
    canonical = normalize_format(fmt) or detect_format(path=file_path, text=text)
    return loads(text, canonical)


def load_data(source: Union[str, os.PathLike], fmt: Optional[str] = None) -> Any:
    """Load structured data from a path or from raw document text.

    ``Path`` instances are always treated as files. Strings are treated as a
    file path when they point at an existing file without newlines, and as
    document text otherwise.
    """

    if isinstance(source, os.PathLike):
        return load_file(source, fmt)
    if isinstance(source, str):
        if "\n" not in source and "\r" not in source:
            candidate = Path(source)
            if candidate.exists() and candidate.is_file():
                return load_file(candidate, fmt)
        return loads(source, fmt)
    raise FormatError(f"expected a path or document string, got {type(source).__name__}")


def dumps(data: Any, fmt: str = JSON) -> str:
    """Serialize ``data`` to a JSON or YAML string."""

    canonical = normalize_format(fmt)
    if canonical is None:
        raise FormatError("a format is required to serialize data")
    if canonical == JSON:
        return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    return _yaml_dumps(data)


def dump_data(data: Any, fmt: str = JSON) -> str:
    """Alias of :func:`dumps` kept for a stable, descriptive public API."""

    return dumps(data, fmt)


def dump_file(data: Any, path: Union[str, os.PathLike], fmt: Optional[str] = None) -> Path:
    """Serialize ``data`` to ``path``; the format follows the suffix if unset."""

    file_path = Path(path)
    canonical = resolve_format(fmt, name=file_path, default=JSON)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(dumps(data, canonical), encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# YAML subset parser
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_NULL_TOKENS = {"", "~", "null", "Null", "NULL"}
_TRUE_TOKENS = {"true", "True", "TRUE"}
_FALSE_TOKENS = {"false", "False", "FALSE"}
_BLOCK_INDICATORS = {"|", ">", "|-", ">-", "|+", ">+"}


class _Line:
    __slots__ = ("indent", "content", "raw")

    def __init__(self, indent, content, raw):
        self.indent = indent
        self.content = content
        self.raw = raw


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    out = []
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1] in " \t":
                break
        out.append(char)
    return "".join(out)


def _scan(text: str) -> list:
    lines = []
    for raw in text.splitlines():
        stripped = raw.lstrip(" ")
        indentation = raw[: len(raw) - len(stripped)]
        if "\t" in indentation:
            raise YamlError("tab characters are not allowed for indentation")
        indent = len(indentation)
        if stripped == "" or stripped.startswith("#"):
            lines.append(_Line(None, "", raw))
            continue
        content = _strip_comment(stripped).rstrip()
        if content == "":
            lines.append(_Line(None, "", raw))
            continue
        lines.append(_Line(indent, content, raw))
    return lines


def _split_key_value(content: str):
    in_single = False
    in_double = False
    depth = 0
    for index, char in enumerate(content):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == ":" and depth == 0:
                if index + 1 == len(content) or content[index + 1] in " \t":
                    key = content[:index].strip()
                    value = content[index + 1 :].strip()
                    return _parse_key(key), value
    raise YamlError(f"invalid mapping entry: {content!r}")


def _parse_key(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return str(_parse_quoted(raw))
    return raw


def _parse_quoted(raw: str):
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise YamlError(f"invalid double-quoted string {raw!r}: {exc}") from exc
    inner = raw[1:-1].replace("''", "'")
    return inner


def _parse_scalar(raw: str):
    text = raw.strip()
    if text == "" or text in _NULL_TOKENS:
        return None
    if text.startswith("[") or text.startswith("{"):
        return _parse_flow(text)
    if text.startswith('"') or text.startswith("'"):
        if len(text) < 2 or text[-1] != text[0]:
            raise YamlError(f"unterminated quoted string: {raw!r}")
        return _parse_quoted(text)
    if text in _TRUE_TOKENS:
        return True
    if text in _FALSE_TOKENS:
        return False
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    if text in (".inf", ".Inf", ".INF", "+.inf"):
        return math.inf
    if text in ("-.inf", "-.Inf", "-.INF"):
        return -math.inf
    if text in (".nan", ".NaN", ".NAN"):
        return math.nan
    return text


def _split_flow(inner: str) -> list:
    parts = []
    depth = 0
    in_single = False
    in_double = False
    current = []
    for char in inner:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
        current.append(char)
    parts.append("".join(current))
    return [part for part in parts if part.strip() != ""]


def _parse_flow(text: str):
    if text.startswith("["):
        if not text.endswith("]"):
            raise YamlError(f"unterminated flow sequence: {text!r}")
        inner = text[1:-1].strip()
        if inner == "":
            return []
        return [_parse_scalar(part) for part in _split_flow(inner)]
    if text.startswith("{"):
        if not text.endswith("}"):
            raise YamlError(f"unterminated flow mapping: {text!r}")
        inner = text[1:-1].strip()
        if inner == "":
            return {}
        result = {}
        for part in _split_flow(inner):
            key, value = _split_key_value(part.strip())
            result[key] = _parse_scalar(value) if value.strip() else None
        return result
    raise YamlError(f"invalid flow collection: {text!r}")


class _Parser:
    def __init__(self, lines):
        self.lines = lines
        self.pos = 0

    def _skip_blanks(self):
        while self.pos < len(self.lines) and self.lines[self.pos].indent is None:
            self.pos += 1

    def parse(self):
        self._skip_blanks()
        if self.pos >= len(self.lines):
            return None
        if self.lines[self.pos].content in ("---", "..."):
            self.pos += 1
            self._skip_blanks()
        if self.pos >= len(self.lines):
            return None
        value = self._parse_node(self.lines[self.pos].indent)
        self._skip_blanks()
        if self.pos < len(self.lines):
            line = self.lines[self.pos]
            raise YamlError(f"unexpected content at line {self.pos + 1}: {line.content!r}")
        return value

    def _parse_node(self, indent):
        line = self.lines[self.pos]
        if line.content == "-" or line.content.startswith("- "):
            return self._parse_sequence(indent)
        return self._parse_mapping(indent)

    def _parse_sequence(self, indent):
        items = []
        while True:
            self._skip_blanks()
            if self.pos >= len(self.lines):
                break
            line = self.lines[self.pos]
            if line.indent is None:
                continue
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError(f"unexpected indentation at line {self.pos + 1}: {line.content!r}")
            content = line.content
            if not (content == "-" or content.startswith("- ")):
                break
            rest = content[2:].strip() if content.startswith("- ") else ""
            if rest == "":
                self.pos += 1
                self._skip_blanks()
                if (
                    self.pos < len(self.lines)
                    and self.lines[self.pos].indent is not None
                    and self.lines[self.pos].indent > indent
                ):
                    items.append(self._parse_node(self.lines[self.pos].indent))
                else:
                    items.append(None)
            elif _looks_like_mapping_entry(rest):
                self.lines[self.pos] = _Line(indent + 2, rest, self.lines[self.pos].raw)
                items.append(self._parse_mapping(indent + 2))
            else:
                items.append(_parse_scalar(rest))
                self.pos += 1
        return items

    def _parse_mapping(self, indent):
        result = {}
        while True:
            self._skip_blanks()
            if self.pos >= len(self.lines):
                break
            line = self.lines[self.pos]
            if line.indent is None:
                continue
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError(f"unexpected indentation at line {self.pos + 1}: {line.content!r}")
            key, value = _split_key_value(line.content)
            self.pos += 1
            if value == "":
                saved = self.pos
                self._skip_blanks()
                if (
                    self.pos < len(self.lines)
                    and self.lines[self.pos].indent is not None
                    and self.lines[self.pos].indent > indent
                ):
                    result[key] = self._parse_node(self.lines[self.pos].indent)
                else:
                    self.pos = saved
                    result[key] = None
            elif value in _BLOCK_INDICATORS:
                result[key] = self._parse_block_scalar(indent, value)
            else:
                result[key] = _parse_scalar(value)
        return result

    def _parse_block_scalar(self, parent_indent, indicator):
        collected = []
        block_indent = None
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.indent is None:
                collected.append(None)
                self.pos += 1
                continue
            if line.indent <= parent_indent:
                break
            if block_indent is None:
                block_indent = line.indent
            collected.append(line.raw[block_indent:] if len(line.raw) >= block_indent else line.content)
            self.pos += 1

        keep = indicator.endswith("+")
        strip = indicator.endswith("-")

        trailing_blanks = 0
        while collected and collected[-1] is None:
            collected.pop()
            trailing_blanks += 1

        raw_lines = ["" if item is None else item for item in collected]
        if indicator[0] == ">":
            parts = []
            pending_breaks = 0
            first = True
            for item in raw_lines:
                if item == "":
                    pending_breaks += 1
                    continue
                if first:
                    parts.append(item)
                    first = False
                elif pending_breaks:
                    parts.append("\n" * pending_breaks + item)
                    pending_breaks = 0
                else:
                    parts.append(" " + item)
            core = "".join(parts)
        else:
            core = "\n".join(raw_lines)

        if strip:
            return core.rstrip("\n")
        if keep:
            if not core:
                return "\n" * trailing_blanks
            return core.rstrip("\n") + "\n" * (1 + trailing_blanks)
        if not core:
            return ""
        return core.rstrip("\n") + "\n"


def _looks_like_mapping_entry(text: str) -> bool:
    in_single = False
    in_double = False
    depth = 0
    for index, char in enumerate(text):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == ":" and depth == 0:
                if index + 1 == len(text) or text[index + 1] in " \t":
                    return True
    return False


def _yaml_loads(text: str):
    if HAS_PYYAML:
        try:
            return _pyyaml.safe_load(text)
        except _pyyaml.YAMLError as exc:  # pragma: no cover - depends on PyYAML
            raise YamlError(f"invalid YAML: {exc}") from exc
    if not isinstance(text, str):
        raise YamlError("expected YAML text")
    return _Parser(_scan(text)).parse()


# ---------------------------------------------------------------------------
# YAML subset serializer
# ---------------------------------------------------------------------------

_PLAIN_SAFE_RE = re.compile(r"^[A-Za-z0-9_/][A-Za-z0-9_\-./ ]*$")
_PLAIN_RESERVED = {
    "null",
    "true",
    "false",
    "yes",
    "no",
    "on",
    "off",
    "~",
}


def _is_number_like(text: str) -> bool:
    return bool(_INT_RE.match(text) or _FLOAT_RE.match(text))


def _yaml_string(value: str) -> str:
    if value == "":
        return '""'
    needs_quotes = (
        value != value.strip()
        or "\n" in value
        or "\r" in value
        or "\t" in value
        or any(ord(char) < 0x20 for char in value)
        or value.lower() in _PLAIN_RESERVED
        or _is_number_like(value)
        or not _PLAIN_SAFE_RE.match(value)
    )
    if needs_quotes:
        return json.dumps(value, ensure_ascii=False)
    return value


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return ".nan"
        if math.isinf(value):
            return ".inf" if value > 0 else "-.inf"
        return repr(value)
    if isinstance(value, str):
        return _yaml_string(value)
    raise FormatError(f"cannot serialize value of type {type(value).__name__} to YAML")


def _yaml_block(data, indent: int) -> list:
    prefix = " " * indent
    lines = []
    if isinstance(data, Mapping):
        if not data:
            lines.append(prefix + "{}")
            return lines
        for key, value in data.items():
            key_text = _yaml_string(str(key))
            if isinstance(value, Mapping) and value:
                lines.append(f"{prefix}{key_text}:")
                lines.extend(_yaml_block(value, indent + 2))
            elif isinstance(value, (list, tuple)) and value:
                lines.append(f"{prefix}{key_text}:")
                lines.extend(_yaml_block(value, indent + 2))
            elif isinstance(value, Mapping):
                lines.append(f"{prefix}{key_text}: {{}}")
            elif isinstance(value, (list, tuple)):
                lines.append(f"{prefix}{key_text}: []")
            else:
                lines.append(f"{prefix}{key_text}: {_yaml_scalar(value)}")
        return lines
    if isinstance(data, (list, tuple)):
        if not data:
            lines.append(prefix + "[]")
            return lines
        for item in data:
            if isinstance(item, Mapping) and item:
                sub = _yaml_block(item, indent + 2)
                first = sub[0]
                lines.append(f"{prefix}- {first[indent + 2:]}")
                lines.extend(sub[1:])
            elif isinstance(item, (list, tuple)) and item:
                lines.append(prefix + "-")
                lines.extend(_yaml_block(item, indent + 2))
            elif isinstance(item, Mapping):
                lines.append(prefix + "- {}")
            elif isinstance(item, (list, tuple)):
                lines.append(prefix + "- []")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    lines.append(f"{prefix}{_yaml_scalar(data)}")
    return lines


def _yaml_dumps(data) -> str:
    if HAS_PYYAML:  # pragma: no cover - depends on PyYAML
        return _pyyaml.safe_dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return "\n".join(_yaml_block(data, 0)) + "\n"
