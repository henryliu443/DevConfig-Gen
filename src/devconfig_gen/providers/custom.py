"""A generic, schema-free provider for arbitrary JSON/YAML documents.

Unlike schema-bound providers that validate a fixed set of domain fields,
``custom`` imposes no schema at all: any nesting of mappings, sequences and
scalars is accepted, and callers can add, remove, or clear nodes at any level.
It exists so users are not forced into a particular domain model.
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

DEFAULT_ARTIFACT_STEM = "custom"


class CustomProvider:
    """Pass an arbitrary, freely-edited document through the pipeline."""

    name = "custom"

    steps: Sequence[ProviderStep] = (
        ProviderStep(
            id="document",
            title="Custom document",
            description="Build any nested JSON/YAML structure; add, remove, or clear nodes at any level.",
            i18n={
                "zh": {
                    "title": "自定义文档",
                    "description": "自由构建任意嵌套的 JSON/YAML 结构；任意层级都可增删或清空。",
                }
            },
            fields=(
                ProviderField(
                    "document",
                    type="tree",
                    required=False,
                    title="Document tree",
                    description="Arbitrary nested document; keys and values are fully editable.",
                    i18n={
                        "zh": {
                            "title": "文档结构",
                            "description": "任意嵌套文档；键与值均可自由编辑。",
                        }
                    },
                ),
            ),
        ),
    )

    def describe_schema(self) -> Sequence[ProviderStep]:
        return self.steps

    def _unwrap_context(self, context: Any) -> Any:
        if isinstance(context, Mapping) and set(context.keys()) == {"document"}:
            return context["document"]
        return context

    def validate(self, request: GenerationRequest):
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
        filename = request.options.get("name") or f"{DEFAULT_ARTIFACT_STEM}.{suffix}"
        context = self._unwrap_context(request.context)
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name=str(filename),
                    content=context,
                    media_type=formats.media_type_for(fmt),
                ),
            ),
        )
