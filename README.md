# DevConfig-Gen

DevConfig-Gen is a developer tool for generating and validating structured
JSON/YAML configuration from structured input data and mappings. It is built
around a small provider contract so the generation pipeline is independent of
any particular configuration format or target system.

The project ships with a dependency-free JSON provider and a complete example
`service` provider that demonstrates normalization, strict validation with
structured field-level diagnostics, declarative step metadata, and JSON/YAML
output.

## What it is (and is not)

DevConfig-Gen:

- loads a structured document (JSON or YAML);
- normalizes it into a predictable shape;
- validates it and reports every problem with a precise field path;
- generates a structured configuration document through a provider;
- writes the result as JSON or YAML.

It is deliberately local and side-effect free. It does not contact remote
services, install packages, manage system state, or perform any deployment.
The Python API can be used without invoking the CLI, and importing the package
has no side effects.

## Installation

```bash
pip install -e .
```

YAML support works with **no external dependencies**. If PyYAML is available it
is used automatically; otherwise a bundled subset parser/serializer is used.

```bash
pip install -e ".[yaml]"   # optional: use PyYAML when present
```

## CLI

List the available providers:

```bash
devconfig-gen providers
# json
# service
```

Generate configuration from the bundled example:

```bash
devconfig-gen generate \
  --provider service \
  --input examples/service.yaml \
  --output-dir generated \
  --format yaml
# generated generated/service.yaml
```

Validate without writing anything:

```bash
devconfig-gen validate --provider service --input examples/service.yaml
# examples/service.yaml: valid
```

When validation fails, every problem is reported with the offending field path
and the CLI exits non-zero:

```bash
$ devconfig-gen validate --provider service --input broken.yaml
invalid: missing required field: 'service.name'
invalid: port must be between 1 and 65535, got 99999
invalid: environment must be one of development, staging, production, got 'prod'
```

Pass `--json` to get the same results as structured diagnostics for tooling:

```bash
devconfig-gen validate --provider service --input broken.yaml --json
```

```json
[
  {"field": "service.name", "message": "missing required field: 'service.name'", "severity": "error"},
  {"field": "service.port", "message": "port must be between 1 and 65535, got 99999", "severity": "error"}
]
```

Inspect a provider's declarative field schema:

```bash
devconfig-gen schema --provider service
```

### Interactive Terminal Wizard (Linux & Headless)

For headless Linux servers, SSH sessions, or terminal-first workflows, run the
interactive step-by-step wizard:

```bash
devconfig-gen init --provider service
```

The wizard prompts for every field defined in the provider's schema with defaults,
type validation, choices, bounds checking, and instant correction on errors.
You can also pass `--input existing.yaml` to pre-fill the wizard from an existing
configuration file.

### Configuration Studio WebUI (Mac-first)

Launch the zero-build, single-page local web studio:

```bash
devconfig-gen ui
# or bound to a project directory:
devconfig-gen ui --workspace ~/projects/my-app
```

Opens your default browser at `http://127.0.0.1:8848`. Features:
- Apple-native typography and light/dark theme matching macOS settings;
- Step-by-step form wizard with inline field validation;
- Dual-pane live preview updating YAML/JSON in real time;
- Template presets, file upload/reverse parsing, draft auto-saving, and disk export;
- Zero external build dependencies (pure Python standard library `http.server`).

The studio binds to loopback only and rejects requests with a non-loopback
`Host` header. Disk export is sandboxed to the workspace root (the current
directory by default, or `--workspace`), so a page cannot write outside it.

Exit codes: `0` success, `1` validation failure, `2` input/parse/provider error.

Output format resolution order: explicit `--format`, then the suffix of
`--name`, then the input file suffix, then JSON.

## Python API

```python
from devconfig_gen import GenerationRequest, generate, generate_from_file

# In-memory context
result = generate(
    "service",
    GenerationRequest(
        context={"name": "checkout-api", "port": 8080, "environment": "production"},
        options={"format": "yaml"},
    ),
)
artifact = result.artifacts[0]
print(artifact.name, artifact.media_type)   # service.yaml application/yaml

# File to file (same pipeline the CLI uses)
generate_from_file(
    "service",
    "examples/service.yaml",
    output_dir="generated",
    output_format="yaml",
)
```

Loading and serializing data directly:

```python
from devconfig_gen import load_file, loads, dumps

data = load_file("examples/service.yaml")
text = dumps(data, "json")
```

Structured diagnostics and declarative schema metadata:

```python
from devconfig_gen import diagnose_request, describe_provider

for diagnostic in diagnose_request("service", context={"port": 99999}):
    print(diagnostic.field, "->", diagnostic.message, f"({diagnostic.severity})")
# service.name -> missing required field: 'service.name' (error)
# service.port -> port must be between 1 and 65535, got 99999 (error)

for step in describe_provider("service"):
    print(step.id, step.title, [field.name for field in step.fields])
```

## Example input

`examples/service.yaml`:

```yaml
service:
  name: checkout-api
  version: "2.4.0"
  port: 8080
  environment: production
  replicas: 3
  labels:
    team: payments
    tier: backend
  health_check:
    path: /healthz
    interval_seconds: 15
    timeout_seconds: 5
```

`examples/service.json` is the equivalent JSON document. The `service` provider
accepts the fields either nested under `service:` or at the document root.

## JSON/YAML support and limitations

JSON is handled by the standard library. YAML is handled by PyYAML when it is
installed and otherwise by a bundled, dependency-free parser. The bundled
parser intentionally covers the subset used for configuration documents:

Supported:

- mappings and sequences nested by indentation;
- scalars: strings, integers, floats, booleans, `null`;
- quoted strings (single and double) and plain strings;
- flow collections: `[a, b]` and `{x: 1}`;
- comments (`# ...`) and blank lines;
- literal/folded block scalars (`|`, `>`) with `-`/`+` chomping.

Not supported by the bundled parser:

- anchors and aliases (`&` / `*`), custom tags (`!tag`), and merge keys (`<<`);
- multiple documents in one stream (`---` separated documents);
- explicit complex mapping keys;
- comments or blank lines inside block scalars may be dropped;
- very large or pathological documents (no streaming).

If you need full YAML 1.1/1.2 behavior, install the optional `yaml` extra and
PyYAML is used transparently.

## Architecture and data flow

```text
input file / context
        |
        v
  formats.load_*        JSON/YAML parsing + format detection
        |
        v
  Provider.diagnose     normalization + structured Diagnostics
        |
        v
  Provider.generate     structured configuration document
        |
        v
  engine.generate       artifact serialization + optional persistence
        |
        v
   JSON / YAML output
```

Both `devconfig-gen` and the Python API call the same functions in
`devconfig_gen.engine` (`generate_pipeline`, `generate_from_file`,
`validate_request`, `diagnose_request`, `describe_provider`). The `init` wizard
and the `ui` studio are thin clients over those same functions, so all three
produce identical artifacts. The CLI contains no generation logic of its own.

Key modules:

| Module | Responsibility |
| --- | --- |
| `devconfig_gen.formats` | JSON/YAML load, dump, detection, media types |
| `devconfig_gen.validation` | reusable path-aware validation helpers |
| `devconfig_gen.models` | `GenerationRequest`, `GeneratedArtifact`, `GenerationResult`, `Diagnostic`, `ProviderField`, `ProviderStep`, `ConfigProvider` |
| `devconfig_gen.registry` | `ProviderRegistry` and the built-in providers |
| `devconfig_gen.engine` | orchestration, diagnostics, schema metadata, persistence |
| `devconfig_gen.providers` | `json` and `service` providers |
| `devconfig_gen.interactive` | `init` terminal wizard (lazy-loaded) |
| `devconfig_gen.web_ui` | `ui` local studio server (lazy-loaded) |
| `devconfig_gen.cli` | argument parsing only |

## Writing and registering a provider

A provider implements the `ConfigProvider` protocol. Only `name`, `validate`,
and `generate` are required. `diagnose` and `describe_schema` / `steps` are
optional metadata used by tooling and the interactive clients.

```python
from devconfig_gen import (
    Diagnostic,
    GeneratedArtifact,
    GenerationResult,
    ProviderField,
    ProviderStep,
    ValidationError,
)


class GreetingProvider:
    name = "greeting"

    steps = (
        ProviderStep(
            id="input",
            title="Greeting input",
            fields=(
                ProviderField("who", type="string", required=True, description="Who to greet."),
            ),
        ),
    )

    def describe_schema(self):
        return self.steps

    def diagnose(self, request):
        if not request.context.get("who"):
            return (Diagnostic("who", "missing required field: 'who'"),)
        return ()

    def validate(self, request):
        return tuple(item.message for item in self.diagnose(request))

    def generate(self, request):
        diagnostics = self.diagnose(request)
        if diagnostics:
            raise ValidationError(diagnostics)
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name="greeting.json",
                    content={"message": f"hello {request.context['who']}"},
                    media_type="application/json",
                ),
            ),
        )
```

Register it on a registry and run the pipeline:

```python
from devconfig_gen import GenerationRequest, ProviderRegistry, generate
from devconfig_gen.providers import JsonProvider, ServiceProvider

registry = ProviderRegistry((JsonProvider(), ServiceProvider(), GreetingProvider()))
result = generate("greeting", GenerationRequest(context={"who": "world"}), registry=registry)
```

`GeneratedArtifact.content` may be a data structure (serialized using its
`media_type`) or a pre-rendered string. `describe_provider` and
`diagnose_request` in `devconfig_gen.engine` fall back gracefully for providers
that only implement `validate`.

## Development and testing

```bash
python -m unittest discover -s tests -v
# or, without installing:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The suite covers format loading/serialization, validation error messages, the
example provider, CLI/Python API byte-for-byte parity, the terminal wizard
(including retry and EOF handling), the WebUI JSON API and its parity with the
engine, and a real subprocess CLI end-to-end run against `examples/`.

## License

Apache-2.0. See `LICENSE`.
