# DevConfig-Gen_SingBox

> **A sing-box domain implementation built on top of DevConfig-Gen.**
> **构建在 `DevConfig-Gen` 之上的 sing-box 领域实现（child / fork）。**

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](CHANGELOG.md)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Tests](https://img.shields.io/badge/tests-177%20passing-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey.svg)

**DevConfig-Gen is a deterministic configuration transformation engine built around bounded domain scopes.**
**`DevConfig-Gen` 是一个以有限领域 Scope 为边界的确定性配置转换引擎。**

This repository defines one such scope: the bounded **`singbox` domain** — its domain
model, validation rules, protocol transformations, configuration variants, and
share-link representations. `DevConfig-Gen` supplies the neutral execution engine
and the stable Provider contract; this repository supplies the sing-box-specific
domain implementation.

```text
DevConfig-Gen
  neutral engine · provider contract · execution pipeline
        │
        ▼
DevConfig-Gen_SingBox
  sing-box domain · validation · transformations · server/client variants
        │
        ▼
downstream configurations
```

**The parent owns the engine. The child owns the domain.**
**父仓库拥有引擎，子仓库拥有领域。**

## What this repository is

> **A Provider is a bounded domain implementation, not merely a format adapter.**

A generic configuration tool can push a document through a schema. A domain
provider does more: it carries the *knowledge* of one system — its concepts,
relationships, constraints, variants, and artifacts — and turns a structured
context into validated, deterministic, system-specific configuration.

This repository is **not** a "universal config generator". It deliberately picks a
scope and completes the whole chain inside it:

```text
knowledge → constraints → transformation → validation → artifacts
```

## Domain Scope: sing-box

This repository implements the **`singbox`** domain scope on top of DevConfig-Gen.

```text
Structured context
        │
        ▼
sing-box domain model
        │
        ▼
validation
        │
        ▼
domain transformation
        │
        ▼
server / client configurations
        │
        ▼
share links
```

The domain itself:

```text
SingBox Domain
├── protocols                 (anytls / tuic / hysteria2)
├── authentication            (independent auth per protocol)
├── TLS / Reality             (cert paths, REALITY keypair, decoy handshake)
├── server / client variants
├── routing                   (DNS split, route rules, geo rule sets)
├── network / domain semantics (hosts, subdomain prefixes)
├── credential handling       (credentials are explicit inputs)
├── share-link representations
└── output generation         (server / client / links)
```

The domain implementation lives in:

```text
src/devconfig_gen/providers/singbox/
├── provider.py      # dispatch + assembly (no variant field names)
├── schema.py        # context schema + structural validation
├── models.py        # domain data structures
├── plugins/         # one module per protocol variant
│   ├── anytls.py
│   ├── tuic.py
│   └── hysteria2.py
├── route.py         # DNS + route assembly (reads data/rules.json)
├── links.py         # share-link aggregation
└── data/rules.json  # embedded routing rule table
```

## Parent / Child Architecture

```text
DevConfig-Gen                         (parent · 主)
│  neutral engine
│  provider contract
│  execution pipeline
│
└── DevConfig-Gen_SingBox             (child · 兵)
       │  sing-box domain knowledge
       │  domain validation
       │  protocol transformations
       │  server / client variants
       │  share-link generation
       │
       └── downstream (Automated-sing-box-json-generator — reference only, retiring)
```

**The parent owns the neutral engine and the provider contract; the child owns the domain.**

- Authority flows **parent → child → downstream**.
- Core changes land in the parent first, then flow down through the `upstream` remote.
- This repository never forks or re-implements the neutral core
  (`engine` / `formats` / `validation`); it only adds `providers/singbox/`.

## Domain Model & Transformations

Input context is partitioned by semantics: `network` (protocols / routing / DNS),
`client` (client-only options), `options` (artifact options). `schema.py`
normalizes it, `provider.py` + the plugins validate it, and the plugins
transform each protocol into its sing-box representation.

```yaml
network:
  domain_root: example.com
  subdomain_prefixes: {reality: a1b2c3d4, tuic: e5f6a7b8, hy2: c9d0e1f2}
  tunnel_mode: proxy            # none | proxy | tun
  protocols:
    - type: anytls              # anytls | tuic | hysteria2
      enabled: true
      port: 23244
      auth: {password: replace-me}
      reality: {private_key: ..., public_key: ..., short_id: ...}
    - type: tuic
      enabled: true
      port: 9443
      auth: {uuid: ..., password: ...}
      tls: {cert_path: /etc/.../tuic.crt, key_path: /etc/.../tuic.key}
    - type: hysteria2
      enabled: true
      port: 7443
      auth: {password: ..., obfs_password: ...}
      tls: {cert_path: /etc/.../hy2.crt, key_path: /etc/.../hy2.key}
  routing: {rules_source: embedded, geoip_cn: true}   # custom_rules 可覆盖/补充
  dns: {direct_servers: [223.5.5.5, 119.29.29.29], remote_server: 1.1.1.1}
client:
  server_ip: 203.0.113.10       # TUN 排除路由
  fingerprint: chrome
options:
  target: both                  # server | client | both
  format: json                  # json | yaml
```

**Isolation contract.** Every protocol's field names and structure live only in
`plugins/<variant>.py`. An upstream sing-box change edits **one plugin file**;
`schema.py` / `provider.py` / `route.py` and the artifact contract do not move.
There is no version chasing.

**Independent auth.** Each protocol carries its own `auth` (and variant) block —
credentials are explicit inputs, never generated, stored, or read from the
environment.

## Generated Artifacts

| Artifact | Condition | Media type |
| --- | --- | --- |
| `sing-box.server.{json,yaml}` | `target != client` | `application/json` / `application/yaml` |
| `sing-box.client.{json,yaml}` | `target != server` | `application/json` / `application/yaml` |
| `sing-box-links.txt` | `target != server` | `text/plain` |

`{fmt}` follows `options.format`; the artifact set follows `options.target`.

## Input Example

```bash
devconfig-gen generate --provider singbox --input examples/singbox.yaml --output-dir dist
devconfig-gen validate --provider singbox --input examples/singbox.yaml
devconfig-gen schema   --provider singbox
```

See [`examples/singbox.yaml`](examples/singbox.yaml) for a complete context.

## Validation & Determinism

- **Path-aware diagnostics** — every problem is reported as a dotted path such as
  `network.protocols.0.auth.password`, and all problems are collected in one pass.
- **Deterministic output** — JSON/YAML preserve semantic insertion order; the same
  input produces byte-for-byte identical artifacts across runs and across the CLI,
  Python API, and WebUI.
- **Zero side effects** — the provider does not read environment variables, write
  state, or invoke subprocesses; credentials and subdomain prefixes are explicit
  inputs.

## Inherited DevConfig-Gen Engine

> This repository inherits the following infrastructure from DevConfig-Gen:

- deterministic generation pipeline (`engine.generate` / `generate_pipeline`)
- structured validation and diagnostics (`diagnostic` / `ValidationError`)
- JSON/YAML serialization (standard library + optional PyYAML, bundled subset fallback)
- multi-source merge and dotted-path overrides (`deep_merge`, `--set`)
- CLI and Python API
- optional local WebUI with a table-driven widget registry

It also inherits the neutral providers `custom` / `json` / `env`. This repository
adds the domain provider `singbox`:

```bash
devconfig-gen providers
# custom / env / json / singbox
```

> **These capabilities are infrastructure. The sing-box domain remains the responsibility of this child repository.**

## CLI / Python API

```bash
# generate / validate / inspect
devconfig-gen generate --provider singbox --input examples/singbox.yaml --output-dir dist --format yaml
devconfig-gen validate --provider singbox --input examples/singbox.yaml --json
devconfig-gen schema   --provider singbox
```

```python
from devconfig_gen import GenerationRequest, generate, generate_pipeline

result = generate(
    "singbox",
    GenerationRequest(
        context={
            "network": {
                "domain_root": "example.com",
                "subdomain_prefixes": {"reality": "a1b2", "tuic": "c3d4", "hy2": "e5f6"},
                "tunnel_mode": "proxy",
                "protocols": [
                    {
                        "type": "anytls",
                        "enabled": True,
                        "auth": {"password": "..."},
                        "reality": {"private_key": "...", "public_key": "...", "short_id": "..."},
                    }
                ],
            },
            "options": {"target": "server"},
        },
    ),
)
print([a.name for a in result.artifacts])   # ['sing-box.server.json']

generate_pipeline(
    "singbox",
    input_path="examples/singbox.yaml",
    output_dir="dist",
    output_format="yaml",
)
```

## Documentation

| Topic | Local | Online |
| --- | --- | --- |
| 快速开始 / Getting started | [`docs/getting-started.md`](docs/getting-started.md) | [getting-started](https://henryliu443.github.io/DevConfig-Gen/docs/getting-started/) |
| CLI 参考 | [`docs/cli.md`](docs/cli.md) | [cli](https://henryliu443.github.io/DevConfig-Gen/docs/cli/) |
| 输入合并与覆盖 | [`docs/input-and-merge.md`](docs/input-and-merge.md) | [input-and-merge](https://henryliu443.github.io/DevConfig-Gen/docs/input-and-merge/) |
| 格式支持与产物 | [`docs/formats.md`](docs/formats.md) | [formats](https://henryliu443.github.io/DevConfig-Gen/docs/formats/) |
| 校验与诊断 | [`docs/validation.md`](docs/validation.md) | [validation](https://henryliu443.github.io/DevConfig-Gen/docs/validation/) |
| Provider 开发 | [`docs/providers.md`](docs/providers.md) | [providers](https://henryliu443.github.io/DevConfig-Gen/docs/providers/) |
| Python API | [`docs/python-api.md`](docs/python-api.md) | [python-api](https://henryliu443.github.io/DevConfig-Gen/docs/python-api/) |
| Web 工作台与 HTTP API | [`docs/web-ui.md`](docs/web-ui.md) | [web-ui](https://henryliu443.github.io/DevConfig-Gen/docs/web-ui/) |
| 架构总览 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | — |
| Provider 铁标准 | [`PROVIDER_STANDARD.md`](PROVIDER_STANDARD.md) | — |

## Development & Testing

```bash
pip install -e ".[yaml]"
PYTHONPATH=src python3 -m unittest discover -s tests -v

# repeatable smoke: suite + API/CLI/WebUI byte-parity + frontend
python3 scripts/smoke_rounds.py 8
```

## Repository Relationship

- This repository is the **child (子仓库 / fork)**: `DevConfig-Gen_SingBox`.
- The **parent (父仓库 / upstream)** is
  [`DevConfig-Gen`](https://github.com/henryliu443/DevConfig-Gen), which owns the
  neutral core and [`PROVIDER_STANDARD.md`](PROVIDER_STANDARD.md).
- Domain providers (such as `providers/singbox/`) live **here**, never in the parent.

Authority flows **parent → child → downstream**. Core changes land in the parent
first and flow down via the `upstream` remote; the neutral core is never forked or
rewritten here.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
