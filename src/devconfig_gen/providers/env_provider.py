"""A second provider with real transformation: structured data -> ``.env``.

Nested mappings are flattened into ``UPPER_SNAKE_CASE`` variables. This is a
domain-neutral, non-JSON output format, which makes the provider contract's
``media_type`` handling and multi-source merging easy to demonstrate.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence, Tuple

from ..models import (
    Diagnostic,
    GeneratedArtifact,
    GenerationRequest,
    GenerationResult,
    ProviderField,
    ProviderStep,
)
from ..validation import ValidationError, is_mapping

_SEGMENT_RE = re.compile(r"[^A-Za-z0-9]+")

DEFAULT_ARTIFACT_NAME = ".env"
ENV_MEDIA_TYPE = "text/plain"


class EnvProvider:
    """Flatten a structured mapping into a ``.env`` document."""

    name = "env"

    steps: Sequence[ProviderStep] = (
        ProviderStep(
            id="variables",
            title="Environment variables",
            description="Nested keys are joined with '_' and upper-cased.",
            i18n={"zh": {"title": "环境变量", "description": "嵌套键用 '_' 连接并转为大写。"}},
            fields=(
                ProviderField(
                    "variables",
                    type="mapping",
                    required=True,
                    title="Variables",
                    description="Variables; nested keys become UPPER_SNAKE_CASE names.",
                    i18n={"zh": {"title": "变量", "description": "变量；嵌套键会转为 UPPER_SNAKE_CASE 名称。"}},
                ),
            ),
        ),
    )

    def describe_schema(self) -> Sequence[ProviderStep]:
        return self.steps

    def diagnose(self, request: GenerationRequest) -> Sequence[Diagnostic]:
        _, diagnostics = self._prepare(request)
        return tuple(diagnostics)

    def validate(self, request: GenerationRequest):
        return tuple(item.message for item in self.diagnose(request))

    def generate(self, request: GenerationRequest) -> GenerationResult:
        pairs, diagnostics = self._prepare(request)
        if diagnostics:
            raise ValidationError(diagnostics)
        text = "\n".join(f"{key}={value}" for key, value in pairs.items()) + "\n"
        name = request.options.get("name") or DEFAULT_ARTIFACT_NAME
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name=str(name),
                    content=text,
                    media_type=ENV_MEDIA_TYPE,
                ),
            ),
        )

    # -- normalization + validation -----------------------------------------

    def _prepare(self, request: GenerationRequest) -> Tuple[dict, list]:
        diagnostics: list = []
        context = request.context
        if not is_mapping(context):
            return {}, [Diagnostic("variables", "variables must be a mapping at the document root")]

        raw: Mapping = context
        if set(context.keys()) == {"variables"} and is_mapping(context["variables"]):
            raw = context["variables"]

        if not raw:
            return {}, [Diagnostic("variables", "variables must not be empty")]

        pairs: dict = {}
        origins: dict = {}
        self._flatten(raw, (), pairs, origins, diagnostics)
        return pairs, diagnostics

    def _flatten(
        self,
        source: Mapping,
        prefix: Tuple[str, ...],
        pairs: dict,
        origins: dict,
        diagnostics: list,
    ) -> None:
        for key, value in source.items():
            segment = self._segment(key, prefix, diagnostics)
            if segment is None:
                continue
            path = prefix + (segment,)

            if is_mapping(value):
                if not value:
                    env_key = "_".join(path)
                    self._assign(env_key, "", path, pairs, origins, diagnostics)
                else:
                    self._flatten(value, path, pairs, origins, diagnostics)
            elif isinstance(value, (list, tuple)):
                if any(is_mapping(item) for item in value):
                    diagnostics.append(
                        Diagnostic(
                            ".".join(path).lower(),
                            f"{'.'.join(path).lower()} must not contain mappings",
                        )
                    )
                    continue
                rendered = ",".join(self._scalar_to_env(item) for item in value)
                self._assign("_".join(path), rendered, path, pairs, origins, diagnostics)
            elif isinstance(value, (dict, set)):
                diagnostics.append(
                    Diagnostic(
                        ".".join(path).lower(),
                        f"{'.'.join(path).lower()} has an unsupported value type",
                    )
                )
            else:
                self._assign(
                    "_".join(path), self._scalar_to_env(value), path, pairs, origins, diagnostics
                )

    def _assign(
        self,
        env_key: str,
        value: str,
        path: Tuple[str, ...],
        pairs: dict,
        origins: dict,
        diagnostics: list,
    ) -> None:
        origin = ".".join(path).lower()
        if env_key in pairs and origins.get(env_key) != origin:
            diagnostics.append(
                Diagnostic(
                    origin,
                    f"'{env_key}' collides with '{origins[env_key]}' after normalization",
                )
            )
            return
        pairs[env_key] = value
        origins[env_key] = origin

    @staticmethod
    def _segment(key: Any, prefix: Tuple[str, ...], diagnostics: list) -> Optional[str]:
        segment = _SEGMENT_RE.sub("_", str(key)).strip("_").upper()
        path = ".".join(prefix + (str(key),)).lower()
        if not segment:
            label = path or "<root>"
            diagnostics.append(Diagnostic(path, f"{label} is not a valid variable name"))
            return None
        return segment

    @staticmethod
    def _scalar_to_env(value: Any) -> str:
        if value is None:
            return ""
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)
