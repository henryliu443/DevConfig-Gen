"""A complete, domain-neutral example provider.

The ``service`` provider turns a small, human-authored service description into
a normalized service configuration document. It demonstrates the full
pipeline: input loading, normalization, validation with field-level diagnostics,
declarative step metadata, and JSON or YAML output.
"""

from __future__ import annotations

import difflib
from typing import Any, Mapping, Optional, Sequence, Tuple

from .. import formats
from ..models import (
    Diagnostic,
    GeneratedArtifact,
    GenerationRequest,
    GenerationResult,
    ProviderField,
    ProviderStep,
)
from ..validation import (
    ValidationError,
    expect_enum,
    expect_integer,
    expect_mapping,
    expect_string,
    expect_string_mapping,
    is_mapping,
)

SUPPORTED_ENVIRONMENTS = ("development", "staging", "production")

_DEFAULT_VERSION = "0.1.0"
_DEFAULT_ENVIRONMENT = "development"
_DEFAULT_REPLICAS = 1
_DEFAULT_HEALTH_PATH = "/healthz"
_DEFAULT_HEALTH_INTERVAL = 10
_DEFAULT_HEALTH_TIMEOUT = 5

_KNOWN_FIELDS = frozenset(
    {"name", "version", "port", "environment", "replicas", "image", "labels", "health_check"}
)
_KNOWN_HEALTH_FIELDS = frozenset({"path", "interval_seconds", "timeout_seconds"})


class ServiceProvider:
    """Normalize and validate a service description into a config document."""

    name = "service"

    steps: Sequence[ProviderStep] = (
        ProviderStep(
            id="identity",
            title="Service identity",
            description="Human-readable name and version of the service.",
            i18n={"zh": {"title": "服务标识", "description": "服务的可读名称和版本。"}},
            fields=(
                ProviderField(
                    "service.name",
                    type="string",
                    required=True,
                    title="Service name",
                    description="Service name, used as the image repository name.",
                    i18n={"zh": {"title": "服务名称", "description": "服务名称，用作镜像仓库名称。"}},
                ),
                ProviderField(
                    "service.version",
                    type="string",
                    default=_DEFAULT_VERSION,
                    title="Version",
                    description="Service version tag.",
                    i18n={"zh": {"title": "版本", "description": "服务版本标签。"}},
                ),
                ProviderField(
                    "service.image",
                    type="string",
                    title="Container image",
                    description="Container image; defaults to '<name>:<version>'.",
                    i18n={"zh": {"title": "容器镜像", "description": "容器镜像，默认为 '<名称>:<版本>'。"}},
                ),
            ),
        ),
        ProviderStep(
            id="runtime",
            title="Runtime",
            description="Where and how the service runs.",
            i18n={"zh": {"title": "运行时", "description": "服务的运行位置和方式。"}},
            fields=(
                ProviderField(
                    "service.port",
                    type="integer",
                    required=True,
                    minimum=1,
                    maximum=65535,
                    title="Port",
                    description="TCP port exposed by the service.",
                    i18n={"zh": {"title": "端口", "description": "服务暴露的 TCP 端口。"}},
                ),
                ProviderField(
                    "service.environment",
                    type="string",
                    default=_DEFAULT_ENVIRONMENT,
                    choices=SUPPORTED_ENVIRONMENTS,
                    title="Environment",
                    description="Deployment environment.",
                    i18n={"zh": {"title": "环境", "description": "部署环境。"}},
                ),
                ProviderField(
                    "service.replicas",
                    type="integer",
                    default=_DEFAULT_REPLICAS,
                    minimum=1,
                    maximum=10000,
                    title="Replicas",
                    description="Desired number of replicas.",
                    i18n={"zh": {"title": "副本数", "description": "期望的副本数量。"}},
                ),
            ),
        ),
        ProviderStep(
            id="metadata",
            title="Metadata and health",
            description="Labels and health-check configuration.",
            i18n={"zh": {"title": "元数据与健康检查", "description": "标签与健康检查配置。"}},
            fields=(
                ProviderField(
                    "service.labels",
                    type="mapping",
                    default={},
                    title="Labels",
                    description="Free-form string labels.",
                    i18n={"zh": {"title": "标签", "description": "自由格式的字符串标签。"}},
                ),
                ProviderField(
                    "service.health_check.path",
                    type="string",
                    default=_DEFAULT_HEALTH_PATH,
                    title="Health path",
                    description="HTTP path used for health checks.",
                    i18n={"zh": {"title": "健康检查路径", "description": "用于健康检查的 HTTP 路径。"}},
                ),
                ProviderField(
                    "service.health_check.interval_seconds",
                    type="integer",
                    default=_DEFAULT_HEALTH_INTERVAL,
                    minimum=1,
                    maximum=86400,
                    title="Interval (seconds)",
                    description="Seconds between health checks.",
                    i18n={"zh": {"title": "检查间隔（秒）", "description": "健康检查之间的间隔秒数。"}},
                ),
                ProviderField(
                    "service.health_check.timeout_seconds",
                    type="integer",
                    default=_DEFAULT_HEALTH_TIMEOUT,
                    minimum=1,
                    maximum=86400,
                    title="Timeout (seconds)",
                    description="Health-check timeout in seconds.",
                    i18n={"zh": {"title": "超时（秒）", "description": "健康检查超时秒数。"}},
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
        return tuple(diagnostic.message for diagnostic in self.diagnose(request))

    def generate(self, request: GenerationRequest) -> GenerationResult:
        config, diagnostics = self._prepare(request)
        if diagnostics:
            raise ValidationError(diagnostics)
        fmt = formats.resolve_format(
            request.options.get("format"),
            name=request.options.get("name"),
            default=formats.JSON,
        )
        suffix = "yaml" if fmt == formats.YAML else "json"
        filename = request.options.get("name") or f"service.{suffix}"
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name=str(filename),
                    content=config,
                    media_type=formats.media_type_for(fmt),
                ),
            ),
        )

    # -- normalization + validation -----------------------------------------

    def _prepare(self, request: GenerationRequest) -> Tuple[dict, list]:
        diagnostics: list = []
        context = request.context
        if not is_mapping(context):
            diagnostics.append(
                Diagnostic("service", "service must be a mapping at the document root")
            )
            return {}, diagnostics

        if "service" in context:
            nested = context["service"]
            if not is_mapping(nested):
                diagnostics.append(Diagnostic("service", "service must be a mapping"))
                return {}, diagnostics
            raw = nested
        else:
            raw = context

        base = "service"

        name = self._read_required_string(raw, "name", base, diagnostics)
        version = self._read_optional_string(raw, "version", base, diagnostics, _DEFAULT_VERSION)
        port = self._read_required_integer(raw, "port", base, diagnostics, 1, 65535)
        environment = self._read_environment(raw, base, diagnostics)
        replicas = self._read_optional_integer(
            raw, "replicas", base, diagnostics, _DEFAULT_REPLICAS, 1, 10000
        )
        labels = self._read_labels(raw, base, diagnostics)
        health_check = self._read_health_check(raw, base, diagnostics)
        image = self._read_image(raw, base, diagnostics, name, version)

        for key in raw:
            if key not in _KNOWN_FIELDS:
                diagnostics.append(self._unknown_field(base, key, _KNOWN_FIELDS))

        config = {
            "service": {
                "name": name,
                "version": version,
                "image": image,
                "environment": environment,
                "port": port,
                "replicas": replicas,
                "labels": labels,
                "health_check": health_check,
            }
        }
        return config, diagnostics

    @staticmethod
    def _coerce_int(value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if text.lstrip("+").isdigit():
                return int(text)
        return value

    @staticmethod
    def _missing(path: str) -> Diagnostic:
        return Diagnostic(path, f"missing required field: '{path}'")

    @staticmethod
    def _unknown_field(base: str, key: str, known) -> Diagnostic:
        path = f"{base}.{key}"
        message = f"unknown field: '{path}'"
        suggestion = difflib.get_close_matches(key, sorted(known), n=1, cutoff=0.6)
        if suggestion:
            message += f"; did you mean '{base}.{suggestion[0]}'?"
        return Diagnostic(path, message)

    def _read_required_string(
        self, raw: Mapping, key: str, base: str, errors: list
    ) -> Optional[str]:
        path = f"{base}.{key}"
        if key not in raw or raw[key] is None:
            errors.append(self._missing(path))
            return None
        return expect_string(raw[key], path, errors)

    def _read_optional_string(
        self, raw: Mapping, key: str, base: str, errors: list, default: str
    ) -> Optional[str]:
        if key not in raw or raw[key] is None:
            return default
        value = expect_string(raw[key], f"{base}.{key}", errors)
        return default if value is None else value

    def _read_required_integer(
        self,
        raw: Mapping,
        key: str,
        base: str,
        errors: list,
        minimum: int,
        maximum: int,
    ) -> Optional[int]:
        path = f"{base}.{key}"
        if key not in raw or raw[key] is None:
            errors.append(self._missing(path))
            return None
        return expect_integer(
            self._coerce_int(raw[key]), path, errors, minimum=minimum, maximum=maximum
        )

    def _read_optional_integer(
        self,
        raw: Mapping,
        key: str,
        base: str,
        errors: list,
        default: int,
        minimum: int,
        maximum: int,
    ) -> Optional[int]:
        if key not in raw or raw[key] is None:
            return default
        value = expect_integer(
            self._coerce_int(raw[key]),
            f"{base}.{key}",
            errors,
            minimum=minimum,
            maximum=maximum,
        )
        return default if value is None else value

    def _read_environment(self, raw: Mapping, base: str, errors: list) -> Optional[str]:
        if "environment" not in raw or raw["environment"] is None:
            return _DEFAULT_ENVIRONMENT
        value = expect_enum(
            raw["environment"], f"{base}.environment", errors, allowed=SUPPORTED_ENVIRONMENTS
        )
        return _DEFAULT_ENVIRONMENT if value is None else value

    def _read_labels(self, raw: Mapping, base: str, errors: list) -> dict:
        if "labels" not in raw or raw["labels"] is None:
            return {}
        return expect_string_mapping(raw["labels"], f"{base}.labels", errors) or {}

    def _read_health_check(self, raw: Mapping, base: str, errors: list) -> dict:
        health = {
            "path": _DEFAULT_HEALTH_PATH,
            "interval_seconds": _DEFAULT_HEALTH_INTERVAL,
            "timeout_seconds": _DEFAULT_HEALTH_TIMEOUT,
        }
        if "health_check" not in raw or raw["health_check"] is None:
            return health

        path = f"{base}.health_check"
        candidate = expect_mapping(raw["health_check"], path, errors)
        if candidate is None:
            return health

        if "path" in candidate and candidate["path"] is not None:
            value = expect_string(candidate["path"], f"{path}.path", errors)
            if value is not None:
                if not value.startswith("/"):
                    errors.append(
                        Diagnostic(
                            f"{path}.path",
                            f"health_check.path must start with '/', got {value!r}",
                        )
                    )
                else:
                    health["path"] = value

        if "interval_seconds" in candidate and candidate["interval_seconds"] is not None:
            health["interval_seconds"] = expect_integer(
                self._coerce_int(candidate["interval_seconds"]),
                f"{path}.interval_seconds",
                errors,
                minimum=1,
                maximum=86400,
            )

        if "timeout_seconds" in candidate and candidate["timeout_seconds"] is not None:
            health["timeout_seconds"] = expect_integer(
                self._coerce_int(candidate["timeout_seconds"]),
                f"{path}.timeout_seconds",
                errors,
                minimum=1,
                maximum=86400,
            )

        for key in candidate:
            if key not in _KNOWN_HEALTH_FIELDS:
                errors.append(self._unknown_field(path, key, _KNOWN_HEALTH_FIELDS))

        return health

    def _read_image(
        self,
        raw: Mapping,
        base: str,
        errors: list,
        name: Optional[str],
        version: Optional[str],
    ) -> Optional[str]:
        if "image" in raw and raw["image"] is not None:
            return expect_string(raw["image"], f"{base}.image", errors)
        if name and version:
            return f"{name}:{version}"
        return None
