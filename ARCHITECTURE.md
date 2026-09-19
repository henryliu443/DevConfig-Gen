# Architecture

This document describes how DevConfig-Gen is put together and the decisions
behind its boundaries.

## Goal

Turn a structured input document (JSON or YAML) into a validated, normalized
structured configuration document (JSON or YAML), driven by an extensible
provider. The engine is provider-neutral; providers own schemas,
normalization, and validation.

## Layers

```text
CLI (`generate`/`validate`)   `init` wizard   `ui` studio
        |                          |               |
        +--------------------------+---------------+
                                   v
engine.py  ---- build_request / generate_pipeline / generate_from_file
  |            diagnose_request / describe_provider
  |            (the single shared pipeline)
  v
ProviderRegistry -> ConfigProvider (validate / diagnose / generate / steps)
  |
  v
formats.py  (JSON/YAML load, dump, detection, media types)
validation.py (path-aware Diagnostic helpers)
```

### Data contracts (`models.py`)

- `GenerationRequest` — immutable `context` (the input document) plus
  `options` (provider configuration such as `format` and `name`).
- `Diagnostic` — a structured validation result: `field` (dotted path),
  `message` (rendered text), and `severity` (`error` / `warning`).
- `GeneratedArtifact` — an output file: `name`, `content` (a data structure or
  a pre-rendered string), and `media_type`.
- `GenerationResult` — the provider name plus the artifacts it produced.
- `ProviderField` / `ProviderStep` — declarative field metadata for
  documentation and the interactive clients.
- `ConfigProvider` — the protocol providers implement.

### Engine (`engine.py`)

`generate()` is the single execution point: it looks up the provider, runs
`validate`, runs `generate`, and optionally persists artifacts. Higher-level
helpers (`generate_pipeline`, `generate_from_file`, `validate_request`,
`diagnose_request`, `describe_provider`) only build a request and delegate. The
CLI calls these helpers and adds no logic.

Persistence maps `media_type` to a serializer (`application/json`,
`application/yaml`) and refuses artifact names that escape the output
directory.

### Formats (`formats.py`)

- `loads` / `load_file` / `load_data` for input;
- `dumps` / `dump_data` / `dump_file` for output;
- `detect_format` / `resolve_format` for format selection;
- `media_type_for` / `format_from_media_type` for artifact metadata.

JSON uses the standard library. YAML uses PyYAML when installed and otherwise
a bundled subset parser/serializer with no external dependencies. See the
README for the exact support boundary.

### Validation (`validation.py`)

Small primitives (`expect_string`, `expect_integer`, `expect_enum`,
`expect_mapping`, `expect_string_mapping`) collect every problem in one pass as
`Diagnostic` objects instead of raising on the first failure. Messages use the
leaf field name (for example `port must be between 1 and 65535, got 99999`)
while `Diagnostic.field` keeps the full dotted path for tooling.

### Providers (`providers/`)

- `json` — a pass-through provider that normalizes/re-serializes an arbitrary
  document. It proves the pipeline without imposing a schema.
- `service` — the complete example provider. It normalizes defaults, coerces
  numeric strings, validates every field with a structured diagnostic, exposes
  declarative `steps`, and emits a structured service configuration document.

### Interactive clients (`interactive.py`, `web_ui.py`)

Two thin clients consume the same declarative metadata and pipeline; neither
contains generation, validation, or serialization logic of its own:

- `interactive.py` — the `devconfig-gen init` terminal wizard. It walks the
  provider's `steps`, prompts by `ProviderField.type`, validates through
  `diagnose_request`, and writes through `generate`. On validation failure it
  re-runs with the previous answers pre-filled instead of restarting.
- `web_ui.py` — the `devconfig-gen ui` single-page studio, served by the
  standard-library `ThreadingHTTPServer`. The HTML/CSS/JS is embedded (no build
  step) and it calls the engine through a small JSON API.

The web server is local-only by design:

- it rejects requests whose `Host` header is not loopback (DNS-rebinding
  defense);
- `/api/export` is sandboxed to a `workspace_root` (the current directory by
  default), so a page cannot write outside the workspace;
- `/api/schema`, `/api/validate`, `/api/generate`, and `/api/export` return
  structured JSON errors with 4xx status codes for bad input or unknown
  providers.

These modules are imported lazily from `devconfig_gen.__init__` (PEP 562), so
`import devconfig_gen` never imports `http.server` or `webbrowser`.

## Design decisions

1. `models.py` is the only stable core data contract.
2. `registry.py` is the extension seam; adding a provider is registering an
   object with a lowercase `name`.
3. The engine never imports a specific provider directly; it works through the
   registry.
4. The CLI and the Python API share one code path, so their output is
   byte-for-byte identical. The WebUI adds a third client over the same path.
5. Importing the package has no side effects. File output only happens when an
   explicit `output_dir` is supplied.
6. Provider metadata (`diagnose`, `steps`, `describe_schema`) is optional;
   minimal providers work with `name`, `validate`, and `generate` alone.
7. No remote operation, system mutation, credential handling, or deployment is
   part of the core engine. The only filesystem writes are explicit
   `output_dir` writes, bounded by the WebUI workspace sandbox.

## Out of scope

DevConfig-Gen does not perform deployment, remote repository operations,
service management, credential storage, or automatic migration of machine
state.
