"""Pass-through JSON/YAML provider.

This provider performs no field-level transformation; it exists so callers can
normalize or re-serialize an arbitrary structured document through the same
pipeline as richer providers.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import formats
from ..models import (
    GeneratedArtifact,
    GenerationRequest,
    GenerationResult,
    ProviderField,
    ProviderStep,
)
from ..validation import ValidationError


class JsonProvider:
    name = "json"

    steps: Sequence[ProviderStep] = (
        ProviderStep(
            id="document",
            title="Document",
            description="An arbitrary JSON/YAML document passed through unchanged.",
            i18n={"zh": {"title": "文档", "description": "任意 JSON/YAML 文档，原样透传。"}},
            fields=(
                ProviderField(
                    "document",
                    type="mapping",
                    required=True,
                    title="Document",
                    description="Root mapping of the input document.",
                    i18n={"zh": {"title": "文档", "description": "输入文档的根映射。"}},
                ),
            ),
        ),
    )

    def describe_schema(self) -> Sequence[ProviderStep]:
        return self.steps

    def validate(self, request: GenerationRequest):
        if not isinstance(request.context, Mapping):
            return ("document: expected a mapping at the root",)
        return ()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        errors = self.validate(request)
        if errors:
            raise ValidationError(errors)
        fmt = formats.resolve_format(
            request.options.get("format"),
            name=request.options.get("name"),
            default=formats.JSON,
        )
        suffix = "yaml" if fmt == formats.YAML else "json"
        filename = request.options.get("name") or f"config.{suffix}"
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name=str(filename),
                    content=dict(request.context),
                    media_type=formats.media_type_for(fmt),
                ),
            ),
        )
