# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

### Added

- `custom` provider: a schema-free generic document that accepts any JSON/YAML
  nesting (mapping, sequence, or scalar root) and is editable at any depth.
- WebUI tree editor for `custom` with per-container bulk add and a "nest"
  action, plus a JSON/YAML text mode and a header "Clear All" reset.

### Removed

- The `service` provider and its `examples/service.*` samples. Use `custom` for
  arbitrary documents, `json` for pass-through, and `env` for `.env` output.

### Changed

- `devconfig-gen init` now defaults to `--provider custom`.

## [0.3.0]
### Added

- `env` provider: flattens nested structured data into an `UPPER_SNAKE_CASE`
  `.env` document, including declarative `steps` metadata.
- Multi-source input: `generate_pipeline` / `build_request` accept multiple
  input files and deep-merge them left to right (`formats.deep_merge`).
- CLI `--input` is repeatable and a new `--set KEY=VALUE` option applies dotted
  path overrides after merging.
- `devconfig-gen schema` command and `devconfig-gen validate --json` structured
  diagnostics output.
- CI workflow testing Linux and macOS across Python 3.8–3.14.

### Changed

- JSON output now preserves insertion order (`sort_keys=False`), matching YAML,
  so generated configuration keeps the provider's semantic field order.
- Corrected YAML block scalar chomping (`|`, `|-`, `|+`, `>`, `>-`, `>+`) and
  folded-scalar handling of blank lines.
- Unknown fields in the `service` provider now include a "did you mean" hint.

### Fixed

- Exported `ValidationError` from the package root.
- Imported `Union` in `engine.py` so `typing.get_type_hints` works.
- The interactive wizard preserves previous answers when retrying after a
  validation failure and aborts cleanly on end-of-input.
- The WebUI returns structured JSON errors for bad input/unknown providers,
  rejects non-loopback `Host` headers, and sandboxes disk export to a workspace
  root.

## [0.2.0]

### Added

- Structured `Diagnostic(field, message, severity)` values and declarative
  `ProviderField` / `ProviderStep` metadata.
- `service` provider with normalization, strict validation, and JSON/YAML
  output.
- `devconfig-gen init` terminal wizard and `devconfig-gen ui` local studio.
- Self-contained, dependency-free JSON/YAML load and dump (`formats`).

### Changed

- CLI and Python API share a single pipeline in `devconfig_gen.engine`.

## [0.1.0]

### Added

- Initial provider contract, registry, JSON provider, and CLI skeleton.
