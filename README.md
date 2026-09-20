# DevConfig-Gen

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](CHANGELOG.md)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Tests](https://img.shields.io/badge/tests-143%20passing-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey.svg)

> Provider 驱动的结构化配置生成与校验引擎。
> A provider-driven engine for generating and validating structured configuration.

DevConfig-Gen 把「结构化输入 + 映射逻辑」变成「可预测、可校验、确定性的 JSON/YAML
配置产物」。核心是一个极小的 Provider 契约，使生成流水线独立于任何具体格式或目标
系统；多个输入文档可以在生成前深度合并与覆盖。CLI、Python API、终端向导、Web
工作台全部走同一条 `engine` 流水线，产物逐字节一致。

- **零副作用**：不联网、不装包、不改系统状态；仅在你显式指定 `output_dir` 时写文件。
- **确定性输出**：JSON/YAML 均保持语义插入顺序，同输入连跑两次 byte-for-byte 一致。
- **可插拔扩展**：Provider 是唯一扩展点——领域转换、甚至 WebUI 字段渲染都可扩展。

## 文档 / Documentation

| 主题 / Topic | 本地 / Local | 在线 / Online |
| --- | --- | --- |
| 快速开始 | [`docs/getting-started.md`](docs/getting-started.md) | [getting-started](https://henryliu443.github.io/DevConfig-Gen/docs/getting-started/) |
| CLI 参考 | [`docs/cli.md`](docs/cli.md) | [cli](https://henryliu443.github.io/DevConfig-Gen/docs/cli/) |
| CLI 配方 | [`docs/cli-cookbook.md`](docs/cli-cookbook.md) | [cli-cookbook](https://henryliu443.github.io/DevConfig-Gen/docs/cli-cookbook/) |
| 输入合并与覆盖 | [`docs/input-and-merge.md`](docs/input-and-merge.md) | [input-and-merge](https://henryliu443.github.io/DevConfig-Gen/docs/input-and-merge/) |
| 格式支持与产物 | [`docs/formats.md`](docs/formats.md) | [formats](https://henryliu443.github.io/DevConfig-Gen/docs/formats/) |
| 校验与诊断 | [`docs/validation.md`](docs/validation.md) | [validation](https://henryliu443.github.io/DevConfig-Gen/docs/validation/) |
| Provider 开发 | [`docs/providers.md`](docs/providers.md) | [providers](https://henryliu443.github.io/DevConfig-Gen/docs/providers/) |
| Python API | [`docs/python-api.md`](docs/python-api.md) | [python-api](https://henryliu443.github.io/DevConfig-Gen/docs/python-api/) |
| 交互式向导 | [`docs/wizard.md`](docs/wizard.md) | [wizard](https://henryliu443.github.io/DevConfig-Gen/docs/wizard/) |
| Web 工作台与 HTTP API | [`docs/web-ui.md`](docs/web-ui.md) | [web-ui](https://henryliu443.github.io/DevConfig-Gen/docs/web-ui/) |
| 架构总览 | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/architecture.md`](docs/architecture.md) | [architecture](https://henryliu443.github.io/DevConfig-Gen/docs/architecture/) |
| Provider 铁标准 | [`PROVIDER_STANDARD.md`](PROVIDER_STANDARD.md) | — |
| 全链路 pluggable 计划 | [`PIPELINE_PLAN.md`](PIPELINE_PLAN.md) | — |
| 开发与测试 | [`docs/development.md`](docs/development.md) | [development](https://henryliu443.github.io/DevConfig-Gen/docs/development/) |

## 安装 / Install

```bash
pip install devconfig-gen          # 零外部依赖 / no external dependencies
pip install "devconfig-gen[yaml]"  # 可选 PyYAML / optional PyYAML
pipx install devconfig-gen         # 单命令可用 / single-command install
```

## 快速开始 / Quick start (3 minutes)

```bash
devconfig-gen generate \
  --provider custom --input examples/custom.yaml --output-dir generated --format yaml
devconfig-gen validate --provider custom --input examples/custom.yaml
```

想要引导式流程 / Prefer a guided flow:

```bash
devconfig-gen init --provider custom   # 终端向导 / terminal wizard
devconfig-gen ui                       # 本地 Web 工作台 / local web studio
```

## 内置 Provider / Built-in providers

| Provider | 作用 / Purpose |
| --- | --- |
| `custom` | 无 schema 的通用文档，任意 JSON/YAML 层级可增删清空 / schema-free generic document, editable at any depth |
| `json` | 透传 / 重新序列化任意文档 / pass-through and re-serialization |
| `env` | 嵌套数据扁平化为 `UPPER_SNAKE_CASE` 的 `.env` / flattens nested data into `UPPER_SNAKE_CASE` `.env` |

```bash
devconfig-gen providers
# custom / env / json
```

## 命令行 / CLI

```bash
# 生成 / generate
devconfig-gen generate --provider custom --input examples/custom.yaml --output-dir dist --format yaml

# 仅校验 / validate only
devconfig-gen validate --provider custom --input examples/custom.yaml
devconfig-gen validate --provider env --input broken.yaml --json   # 结构化诊断

# 查看 schema
devconfig-gen schema --provider custom
```

多源合并与覆盖 / Multi-source merge and overrides (`--input` 可重复，`--set` 最后生效):

```bash
devconfig-gen generate \
  --provider custom \
  --input configs/base.yaml \
  --input configs/prod.json \
  --set app.port=9090 \
  --set app.environment=production \
  --output-dir dist --format yaml
```

`--set` 值自动解析 JSON 字面量（`true`→bool、`42`→int、`null`→null）。
完整命令见 [`docs/cli.md`](docs/cli.md) 与 [`docs/cli-cookbook.md`](docs/cli-cookbook.md)。

退出码 / Exit codes: `0` 成功, `1` 校验失败, `2` 输入错误。

## Web 工作台 / Configuration Studio

```bash
devconfig-gen ui
devconfig-gen ui --workspace ~/projects/my-app --no-browser
```

浏览器打开 `http://127.0.0.1:8848`。零构建、零 npm，仅用 Python 标准库
`ThreadingHTTPServer` 提供内嵌单页应用。

- 中英双语、亮/暗主题、双栏实时预览、内联校验、草稿自动保存；
- `custom` 递归树编辑器（任意层级增删/换类型/嵌套/批量添加）+ JSON/YAML 文本模式；
- `json` 文档拖拽上传与内联编辑器；
- `env` 键值对表格；
- 左上角 `☰` 汉堡侧边栏：仓库、文档站点、问题反馈、邮箱；
- 字段渲染**查表驱动**，Provider 可用可选方法 `web_ui_widgets()` 注册自定义 Widget。

安全边界：仅绑定回环、拒绝非本地 `Host`（DNS rebinding 防护）、导出沙箱限制在
`workspace_root`。详见 [`docs/web-ui.md`](docs/web-ui.md)。

## Python API

```python
from devconfig_gen import GenerationRequest, generate, generate_from_file

result = generate(
    "custom",
    GenerationRequest(
        context={"document": {"app": {"name": "checkout-api", "port": 8080}}},
        options={"format": "yaml"},
    ),
)
print(result.artifacts[0].name, result.artifacts[0].media_type)  # custom.yaml application/yaml

generate_from_file("custom", "examples/custom.yaml", output_dir="generated", output_format="yaml")
```

多源输入 / Multi-source:

```python
from devconfig_gen import generate_pipeline

generate_pipeline(
    "custom",
    input_path=["configs/base.yaml", "configs/prod.json"],
    overrides={"app.port": 9090},
    output_dir="dist",
    output_format="yaml",
)
```

结构化诊断与 schema 元数据 / Diagnostics and schema metadata:

```python
from devconfig_gen import diagnose_request, describe_provider

for d in diagnose_request("env", context={}):
    print(d.field, "->", d.message, f"({d.severity})")

for step in describe_provider("custom"):
    print(step.id, step.title, [f.name for f in step.fields])
```

完整 API 见 [`docs/python-api.md`](docs/python-api.md)。

## 编写自定义 Provider / Writing a provider

只需实现 `ConfigProvider` 的 `name`、`validate`、`generate`；`diagnose` /
`describe_schema` / `web_ui_widgets` 均为可选。

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
from devconfig_gen.providers import CustomProvider, JsonProvider

registry = ProviderRegistry((CustomProvider(), JsonProvider(), GreetingProvider()))
generate("greeting", GenerationRequest(context={"who": "world"}), registry=registry)
```

转换型（rich domain）Provider 请遵循 [`PROVIDER_STANDARD.md`](PROVIDER_STANDARD.md)
（零副作用、变体隔离、无版本追逐、凭据即输入）。WebUI 字段渲染可通过可选方法
`web_ui_widgets()` 扩展，协议见 [`docs/providers.md`](docs/providers.md) 与
[`docs/web-ui.md`](docs/web-ui.md)。

## 架构 / Architecture

```text
输入文件 / 上下文  →  formats.load_*  →  Provider.diagnose  →  Provider.generate
                                                              →  engine.generate（序列化 + 可选持久化）
                                                              →  JSON / YAML 产物
```

`engine.py` 是唯一执行路径：`generate()` 查表、校验、生成、可选落盘；`build_request`
负责多源合并与 `overrides`。CLI 与 `init`/`ui` 客户端只调用这些共享函数，不重复实现
生成逻辑。详见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

核心模块 / Key modules:

| 模块 | 职责 |
| --- | --- |
| `formats` | JSON/YAML 加载导出、格式检测、媒体类型、`deep_merge`、`coerce_scalar` |
| `validation` | 路径感知校验辅助（一次收集全部问题） |
| `models` | `GenerationRequest` / `GenerationResult` / `Diagnostic` / `ProviderField` / `ProviderStep` / `ConfigProvider` / `WebUIWidgets` |
| `registry` | `ProviderRegistry` 与内置 Provider |
| `engine` | 编排、诊断、schema、持久化 |
| `providers` | `custom` / `json` / `env` |
| `interactive` | `init` 终端向导（延迟加载） |
| `web_ui` | `ui` 本地工作台（延迟加载） |
| `cli` | 仅参数解析 |

## JSON/YAML 支持与限制

JSON 由标准库处理；YAML 在安装 PyYAML 时使用 PyYAML，否则使用内置子集解析器
（零依赖）。支持缩进映射/序列、标量、引号与裸字符串、流式集合 `[a, b] {x: 1}`、
注释空行、块标量 `|` `>` 及 `-`/`+` chomping。不支持锚点别名、自定义标签、合并键
`<<`、多文档 `---`。需要完整 YAML 行为请安装 PyYAML。详见
[`docs/formats.md`](docs/formats.md)。

## 仓库关系 / Repo relationship

- 本仓库是 **父仓库（parent / upstream）**，承载中立核心与 Provider 标准。
- **子仓库（child / fork）**：`DevConfig-Gen_SingBox`，领域集成分支。
- 领域 Provider（如 `providers/singbox/`）只存在于下游，**不回填父仓库**。

权威方向为 **parent → child → downstream**。约定见 [`AGENTS.md`](AGENTS.md)。

## 开发与测试 / Development

```bash
pip install -e ".[yaml]"
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

构建文档站 / Build the docs site:

```bash
pip install -e ".[docs]"
mkdocs build --strict
```

测试覆盖格式解析、校验、Provider、多源合并、CLI/API 逐字节等价、向导、WebUI
widget 注册表。详见 [`docs/development.md`](docs/development.md)。

## 许可证 / License

Apache-2.0. 详见 [`LICENSE`](LICENSE)。
