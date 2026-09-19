"""Pass-through JSON/YAML provider.

This provider performs no field-level transformation; it exists so callers can
normalize or re-serialize an arbitrary structured document through the same
pipeline as richer providers.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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
            description="Upload, paste, or edit an arbitrary JSON/YAML document to pass through unchanged.",
            i18n={"zh": {"title": "文档", "description": "支持上传文件或直接粘贴/编辑任意 JSON/YAML 文档，原样透传与格式转换。"}},
            fields=(
                ProviderField(
                    "document",
                    type="document",
                    required=True,
                    title="Document Content",
                    description="Upload a JSON/YAML file or paste/edit document content directly.",
                    i18n={"zh": {"title": "文档内容", "description": "支持直接上传 JSON/YAML 文件，或直接粘贴/编辑文档内容。"}},
                ),
            ),
        ),
    )

    def describe_schema(self) -> Sequence[ProviderStep]:
        return self.steps

    def _unwrap_context(self, context: Any) -> Any:
        if (
            isinstance(context, Mapping)
            and set(context.keys()) == {"document"}
            and isinstance(context["document"], Mapping)
        ):
            return context["document"]
        return context

    def validate(self, request: GenerationRequest):
        context = self._unwrap_context(request.context)
        if not isinstance(context, Mapping):
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
        context = self._unwrap_context(request.context)
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name=str(filename),
                    content=dict(context),
                    media_type=formats.media_type_for(fmt),
                ),
            ),
        )
