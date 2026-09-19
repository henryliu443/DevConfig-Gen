# DevConfig-Gen

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Tests](https://img.shields.io/badge/tests-132%20passing-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey.svg)

DevConfig-Gen 是一个开发者工具，用于从结构化输入数据和映射关系生成和校验结构化配置。它围绕一个轻量的 Provider 契约构建，使生成流水线独立于任何特定的配置格式或目标系统。多个输入文档可以在生成前进行合并和覆盖。

A developer tool for generating and validating structured configuration from structured input data and mappings. Built around a small provider contract so the generation pipeline is independent of any particular configuration format or target system. Multiple input documents can be merged and overridden before generation.

内置三个 Provider / Ships with three providers:

- `json` — 无依赖的透传/重新序列化 / dependency-free pass-through/re-serialization;
- `service` — 完整的规范化、严格校验和 JSON/YAML 输出示例 / normalization, strict validation, and JSON/YAML output;
- `env` — 将嵌套数据扁平化为 `UPPER_SNAKE_CASE` 的 `.env` 文件 / flattens nested data into an `UPPER_SNAKE_CASE` `.env` file.

## 它是什么 / What it is

DevConfig-Gen：

- 加载结构化文档（JSON 或 YAML）/ loads a structured document (JSON or YAML);
- 将其规范化为可预测的结构 / normalizes it into a predictable shape;
- 校验并报告每个问题的精确字段路径 / validates and reports every problem with a precise field path;
- 通过 Provider 生成结构化配置文档 / generates a structured configuration document through a provider;
- 将结果写为 JSON 或 YAML / writes the result as JSON or YAML.

刻意保持本地化且无副作用 / Deliberately local and side-effect free. 不会访问远程服务、安装包、管理系统状态 / Does not contact remote services, install packages, or manage system state.

## 快速开始 / Quick start (3 minutes)

```bash
pip install devconfig-gen
devconfig-gen generate \
  --provider service --input examples/service.yaml --output-dir generated --format yaml
devconfig-gen validate --provider service --input examples/service.yaml
```

想要引导式流程？运行终端向导或打开本地 Web 工作台 / Prefer a guided flow?

```bash
devconfig-gen init --provider service   # 终端向导 / terminal wizard
devconfig-gen ui                         # Web 工作台 / web studio
```

## 安装 / Installation

从 PyPI 安装 / Install from PyPI:

```bash
pip install devconfig-gen
```

YAML 支持无需外部依赖 / YAML support works with **no external dependencies**.

```bash
pip install devconfig-gen[yaml]   # 可选：安装 PyYAML / optional: use PyYAML
```

开发模式 / Development (editable):

```bash
pip install -e ".[yaml]"
```

## 命令行 / CLI

列出可用 Provider / List available providers:

```bash
devconfig-gen providers
# env / json / service
```

生成配置 / Generate configuration:

```bash
devconfig-gen generate \
  --provider service \
  --input examples/service.yaml \
  --output-dir generated \
  --format yaml
```

仅校验不写入 / Validate without writing:

```bash
devconfig-gen validate --provider service --input examples/service.yaml
```

校验失败时报告字段路径 / Validation failure reports field paths:

```bash
$ devconfig-gen validate --provider service --input broken.yaml
invalid: missing required field: 'service.name'
invalid: port must be between 1 and 65535, got 99999
invalid: environment must be one of development, staging, production, got 'prod'
```

结构化诊断输出 / Structured diagnostics:

```bash
devconfig-gen validate --provider service --input broken.yaml --json
```

查看 Provider Schema / Inspect provider schema:

```bash
devconfig-gen schema --provider service
```

### 交互式终端向导 / Interactive Terminal Wizard

适用于无头环境、SSH 会话 / For headless servers, SSH sessions:

```bash
devconfig-gen init --provider service
```

向导提示每个字段，含默认值、类型校验、选项、边界检查 / Prompts every field with defaults, type validation, choices, bounds checking.

```text
========================================================
  DevConfig-Gen Interactive Wizard: 'service'
  Answer the prompts below. Press Enter to use defaults.
========================================================

--- [1/3] Service identity ---
? service.name (required): checkout-api
? service.version [0.1.0]:

--- [2/3] Runtime ---
? service.port (min 1, max 65535) (required): 99999
  [!] Value must be <= 65535.
? service.port (min 1, max 65535) (required): 8080
? service.environment - Select option:
    1) development
    2) staging
    3) production
  Enter choice number or name [development]: 3
...
[✓] All validations passed!
[✓] Generated artifact: .../service.yaml
```

### Web 可视化工作台 / Configuration Studio WebUI

启动本地 Web 工作台 / Launch local web studio:

```bash
devconfig-gen ui
devconfig-gen ui --workspace ~/projects/my-app   # 绑定项目目录 / bind to project dir
```

浏览器打开 `http://127.0.0.1:8848` / Opens at `http://127.0.0.1:8848`.

特性 / Features:
- 中英双语界面，一键切换，偏好本地保存 / Bilingual UI (中文/English) with one-click toggle and saved preference;
- Apple 原生排版，亮色/暗色主题 / Apple-native typography, light/dark theme;
- 分步表单向导，内联校验 / Step-by-step wizard with inline validation;
- 双栏实时预览 / Dual-pane live preview;
- 模板预设、文件上传、草稿保存、磁盘导出 / Template presets, file upload, auto-save, disk export;
- 零外部依赖 / Zero external build dependencies.

Provider 的步骤与字段元数据自带 `i18n` 翻译（内置 Provider 已提供中文）/ Provider step and field metadata carry optional `i18n` translations (the built-in providers ship Chinese).

仅绑定本地回环 / Binds to loopback only. 磁盘导出沙箱限制在工作空间内 / Disk export sandboxed to workspace root.

退出码 / Exit codes: `0` 成功/success, `1` 校验失败/validation failure, `2` 输入错误/input error.

### 多源合并与覆盖 / Multi-source input and overrides

`--input` 可重复，文档从左到右深度合并 / `--input` may be repeated, deep-merged left to right:

```bash
devconfig-gen generate \
  --provider service \
  --input configs/base.yaml \
  --input configs/prod.json \
  --set service.port=9090 \
  --set service.environment=production \
  --output-dir dist --format yaml
```

`--set` 值自动解析 JSON 类型 / `--set` values parsed as JSON when possible (`true`→bool, `42`→int, `null`→null).

### 生成 .env 文件 / Generating a .env file

```bash
devconfig-gen generate --provider env --input examples/vars.yaml --output-dir dist
# generated dist/.env
```

```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=appdb
DEBUG=true
LOG_LEVEL=info
```

## Python API

```python
from devconfig_gen import GenerationRequest, generate, generate_from_file

# 内存上下文 / In-memory context
result = generate(
    "service",
    GenerationRequest(
        context={"name": "checkout-api", "port": 8080, "environment": "production"},
        options={"format": "yaml"},
    ),
)
artifact = result.artifacts[0]
print(artifact.name, artifact.media_type)   # service.yaml application/yaml

# 文件到文件，与 CLI 相同流水线 / File to file, same pipeline as CLI
generate_from_file(
    "service",
    "examples/service.yaml",
    output_dir="generated",
    output_format="yaml",
)
```

直接加载和序列化 / Load and serialize directly:

```python
from devconfig_gen import load_file, loads, dumps

data = load_file("examples/service.yaml")
text = dumps(data, "json")
```

结构化诊断与 Schema 元数据 / Diagnostics and schema metadata:

```python
from devconfig_gen import diagnose_request, describe_provider

for d in diagnose_request("service", context={"port": 99999}):
    print(d.field, "->", d.message, f"({d.severity})")

for step in describe_provider("service"):
    print(step.id, step.title, [f.name for f in step.fields])
```

## 示例输入 / Example input

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

`examples/service.json` 是等效 JSON 文档 / is the equivalent JSON document.

## JSON/YAML 支持与限制 / Support and limitations

JSON 由标准库处理 / JSON handled by standard library. YAML 在安装 PyYAML 时使用，否则用内置解析器 / YAML uses PyYAML when available, otherwise bundled parser.

支持 / Supported:
- 缩进嵌套的映射和序列 / mappings and sequences by indentation;
- 标量：字符串、整数、浮点、布尔、`null` / scalars: strings, integers, floats, booleans, `null`;
- 引号字符串和裸字符串 / quoted and plain strings;
- 流式集合 `[a, b]` `{x: 1}` / flow collections;
- 注释和空行 / comments and blank lines;
- 块标量 `|` `>` 及 `-`/`+` 修剪 / block scalars with chomping.

不支持 / Not supported:
- 锚点别名 `&`/`*`、自定义标签 `!tag`、合并键 `<<` / anchors, aliases, tags, merge keys;
- 多文档 `---` / multiple documents;
- 块标 scalar 内注释可能丢失 / comments inside block scalars may be dropped.

需要完整 YAML 行为请安装 PyYAML / For full YAML, install PyYAML.

`env` Provider 渲染纯文本 `.env`（`media_type: text/plain`）/ renders plain-text `.env`.

## 架构与数据流 / Architecture and data flow

```text
输入文件 / 上下文 (input file / context)
        |
        v
  formats.load_*        JSON/YAML 解析 + 格式检测
        |
        v
  Provider.diagnose     规范化 + 结构化诊断
        |
        v
  Provider.generate     结构化配置文档
        |
        v
  engine.generate       产物序列化 + 可选持久化
        |
        v
   JSON / YAML 输出
```

CLI、Python API、向导、工作台调用相同的 engine 函数 / CLI, API, wizard, and studio all call the same engine functions. CLI 本身不含生成逻辑 / CLI contains no generation logic of its own.

核心模块 / Key modules:

| 模块 / Module | 职责 / Responsibility |
| --- | --- |
| `formats` | JSON/YAML 加载导出、格式检测、媒体类型 |
| `validation` | 路径感知校验辅助工具 / path-aware validation helpers |
| `models` | 请求、产物、诊断、字段、步骤、Provider 协议 |
| `registry` | ProviderRegistry 及内置 Provider |
| `engine` | 编排、诊断、Schema、持久化 / orchestration, diagnostics, persistence |
| `providers` | `json`、`service`、`env` Provider |
| `interactive` | `init` 终端向导（延迟加载）/ terminal wizard (lazy-loaded) |
| `web_ui` | `ui` 本地工作台（延迟加载）/ local studio (lazy-loaded) |
| `cli` | 仅参数解析 / argument parsing only |

## 编写自定义 Provider / Writing a custom provider (5 minutes)

实现 `ConfigProvider` 协议 / Implement the `ConfigProvider` protocol. 只需 `name`、`validate`、`generate` 必需 / Only `name`, `validate`, `generate` required.

```python
from devconfig_gen import (
    Diagnostic, GeneratedArtifact, GenerationResult,
    ProviderField, ProviderStep, ValidationError,
)

class GreetingProvider:
    name = "greeting"
    steps = (
        ProviderStep(
            id="input",
            title="Greeting input",
            i18n={"zh": {"title": "问候输入", "description": "输入要问候的对象。"}},
            fields=(
                ProviderField(
                    "who",
                    type="string",
                    required=True,
                    title="Who",
                    description="Who to greet.",
                    i18n={"zh": {"title": "对象", "description": "要问候的对象。"}},
                ),
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

注册并运行 / Register and run:

```python
from devconfig_gen import GenerationRequest, ProviderRegistry, generate
from devconfig_gen.providers import JsonProvider, ServiceProvider

registry = ProviderRegistry((JsonProvider(), ServiceProvider(), GreetingProvider()))
result = generate("greeting", GenerationRequest(context={"who": "world"}), registry=registry)
```

`GeneratedArtifact.content` 可以是数据结构或预渲染字符串 / may be a data structure or pre-rendered string.

## 开发与测试 / Development and testing

```bash
python -m unittest discover -s tests -v
# 或无需安装 / or without installing:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试覆盖格式解析、校验、Provider、多源合并、CLI/API 等价性、向导、WebUI / Covers format parsing, validation, providers, merging, CLI/API parity, wizard, WebUI.

## 许可证 / License

Apache-2.0. 详见 `LICENSE` / See `LICENSE`.
