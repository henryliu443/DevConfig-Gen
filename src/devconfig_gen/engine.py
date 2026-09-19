"""Provider-independent generation orchestration.

Every entry point in this module funnels into :func:`generate`, so the CLI and
the Python API share one validation, generation, and persistence path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from . import formats
from .models import (
    Diagnostic,
    GeneratedArtifact,
    GenerationRequest,
    GenerationResult,
    ProviderStep,
)
from .registry import ProviderRegistry, default_registry


def generate(
    provider: str,
    request: GenerationRequest,
    registry: Optional[ProviderRegistry] = None,
    output_dir: Optional[str] = None,
) -> GenerationResult:
    """Validate, generate, and optionally persist provider artifacts."""

    selected = (registry or default_registry).get(provider)
    errors = tuple(selected.validate(request))
    if errors:
        raise ValueError("; ".join(errors))
    result = selected.generate(request)
    if output_dir is not None:
        _persist(result, output_dir)
    return result


def build_request(
    *,
    context: Any = None,
    input_path: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
    input_format: Optional[str] = None,
) -> GenerationRequest:
    """Build a request from an in-memory context and/or an input file."""

    if input_path is not None:
        context = formats.load_file(input_path, input_format)
    if context is None:
        context = {}
    return GenerationRequest(context=context, options=dict(options or {}))


def generate_pipeline(
    provider: str,
    *,
    context: Any = None,
    input_path: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
    output_dir: Optional[str] = None,
    output_format: Optional[str] = None,
    input_format: Optional[str] = None,
    registry: Optional[ProviderRegistry] = None,
) -> GenerationResult:
    """Run the full pipeline from a context or input file to optional output."""

    merged = dict(options or {})
    if output_format is not None:
        merged["format"] = output_format
    request = build_request(
        context=context, input_path=input_path, options=merged, input_format=input_format
    )
    return generate(provider, request, registry=registry, output_dir=output_dir)


def generate_from_file(
    provider: str,
    input_path: str,
    *,
    output_dir: Optional[str] = None,
    output_format: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
    registry: Optional[ProviderRegistry] = None,
) -> GenerationResult:
    """Convenience wrapper around :func:`generate_pipeline` for file input."""

    return generate_pipeline(
        provider,
        input_path=input_path,
        output_dir=output_dir,
        output_format=output_format,
        options=options,
        registry=registry,
    )


def validate_request(
    provider: str,
    *,
    context: Any = None,
    input_path: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
    input_format: Optional[str] = None,
    registry: Optional[ProviderRegistry] = None,
) -> Sequence[str]:
    """Return provider validation errors without generating or writing output."""

    request = build_request(
        context=context, input_path=input_path, options=options, input_format=input_format
    )
    selected = (registry or default_registry).get(provider)
    return tuple(selected.validate(request))


def diagnose_request(
    provider: str,
    *,
    context: Any = None,
    input_path: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
    input_format: Optional[str] = None,
    registry: Optional[ProviderRegistry] = None,
) -> Sequence[Diagnostic]:
    """Return structured diagnostics without generating or writing output."""

    request = build_request(
        context=context, input_path=input_path, options=options, input_format=input_format
    )
    selected = (registry or default_registry).get(provider)
    diagnose = getattr(selected, "diagnose", None)
    if callable(diagnose):
        return tuple(diagnose(request))
    return tuple(Diagnostic(field="", message=message) for message in selected.validate(request))


def describe_provider(
    provider: str,
    registry: Optional[ProviderRegistry] = None,
) -> Sequence[ProviderStep]:
    """Return a provider's declarative step/field metadata."""

    selected = (registry or default_registry).get(provider)
    describe = getattr(selected, "describe_schema", None)
    if callable(describe):
        return tuple(describe())
    return tuple(getattr(selected, "steps", ()))


def _persist(result: GenerationResult, output_dir: str) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for artifact in result.artifacts:
        relative_name = Path(artifact.name)
        if relative_name.is_absolute() or ".." in relative_name.parts:
            raise ValueError(f"artifact name escapes output directory: {artifact.name!r}")
        path = destination / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_serialize_artifact(artifact), encoding="utf-8")


def _serialize_artifact(artifact: GeneratedArtifact) -> str:
    if isinstance(artifact.content, str):
        return artifact.content
    try:
        fmt = formats.format_from_media_type(artifact.media_type)
    except formats.FormatError as exc:
        raise ValueError(
            f"cannot persist media type {artifact.media_type!r} for {artifact.name!r}"
        ) from exc
    return formats.dumps(artifact.content, fmt)
