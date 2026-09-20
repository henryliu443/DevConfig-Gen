"""Provider-based developer configuration generation.

The core package exposes the provider pipeline only. The interactive terminal
wizard and the local web studio are imported lazily so that ``import
devconfig_gen`` stays lightweight and free of any server or browser imports.
"""

from .engine import (
    build_request,
    describe_provider,
    diagnose_request,
    generate,
    generate_from_file,
    generate_pipeline,
    validate_request,
)
from .formats import (
    FormatError,
    coerce_scalar,
    deep_merge,
    dump_data,
    dump_file,
    dumps,
    load_data,
    load_file,
    loads,
)
from .models import (
    ConfigProvider,
    Diagnostic,
    GeneratedArtifact,
    GenerationRequest,
    GenerationResult,
    ProviderField,
    ProviderStep,
    WebUIWidgets,
)
from .registry import ProviderRegistry, default_registry
from .validation import ValidationError

__all__ = [
    "ConfigProvider",
    "Diagnostic",
    "FormatError",
    "GeneratedArtifact",
    "GenerationRequest",
    "GenerationResult",
    "ProviderField",
    "ProviderRegistry",
    "ProviderStep",
    "ValidationError",
    "WebUIWidgets",
    "build_request",
    "coerce_scalar",
    "deep_merge",
    "default_registry",
    "describe_provider",
    "diagnose_request",
    "dump_data",
    "dump_file",
    "dumps",
    "generate",
    "generate_from_file",
    "generate_pipeline",
    "load_data",
    "load_file",
    "loads",
    "run_interactive_wizard",
    "run_web_ui",
    "validate_request",
]
__version__ = "1.1.0"

_LAZY_EXPORTS = {
    "run_interactive_wizard": ("interactive", "run_interactive_wizard"),
    "run_web_ui": ("web_ui", "run_web_ui"),
}


def __getattr__(name):
    """Import the optional UI entry points on first use (PEP 562)."""

    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    import importlib

    module = importlib.import_module(f".{module_name}", __name__)
    value = getattr(module, attribute)
    globals()[name] = value
    return value
