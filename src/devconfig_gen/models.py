"""Stable public data structures for configuration providers."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence


@dataclass(frozen=True)
class GenerationRequest:
    """Input to a provider; mappings are treated as read-only."""

    context: Mapping[str, Any] = field(default_factory=dict)
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnostic:
    """A single, machine-readable validation message.

    ``field`` is the dotted path to the offending value (for example
    ``service.port``). ``message`` is the fully rendered, user-facing text
    (for example ``port must be between 1 and 65535, got 99999``).
    ``severity`` is ``"error"`` or ``"warning"``.
    """

    field: str
    message: str
    severity: str = "error"

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict:
        return {"field": self.field, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class GeneratedArtifact:
    name: str
    content: Any
    media_type: str = "application/json"


@dataclass(frozen=True)
class GenerationResult:
    provider: str
    artifacts: Sequence[GeneratedArtifact]
    diagnostics: Sequence[Diagnostic] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProviderField:
    """Declarative description of one provider input field.

    ``name`` is the dotted field path, e.g. ``service.port``. The remaining
    attributes describe the value for documentation and future UI generation.
    """

    name: str
    type: str = "string"
    required: bool = False
    default: Any = None
    description: str = ""
    choices: Sequence[str] = ()
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    def as_dict(self) -> dict:
        data = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }
        if self.choices:
            data["choices"] = list(self.choices)
        if self.minimum is not None:
            data["minimum"] = self.minimum
        if self.maximum is not None:
            data["maximum"] = self.maximum
        return data


@dataclass(frozen=True)
class ProviderStep:
    """A declarative step grouping fields for a guided input flow."""

    id: str
    title: str
    description: str = ""
    fields: Sequence[ProviderField] = ()

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "fields": [item.as_dict() for item in self.fields],
        }


class ConfigProvider(Protocol):
    """Structural contract every provider implements.

    ``validate`` returns rendered messages. Providers may additionally
    implement ``diagnose`` (structured ``Diagnostic`` values) and
    ``describe_schema`` / ``steps`` (declarative field metadata). Metadata
    methods are optional, so a minimal provider only needs ``name``,
    ``validate``, and ``generate``.
    """

    name: str

    def generate(self, request: GenerationRequest) -> GenerationResult:
        ...

    def validate(self, request: GenerationRequest) -> Sequence[str]:
        ...
