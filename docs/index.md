# DevConfig-Gen 文档

DevConfig-Gen 是一个本地、Provider 驱动的结构化配置生成与校验工具。它把
JSON/YAML 输入文档合并、覆盖、校验后，通过 Provider 生成结构化配置产物
（JSON、YAML 或 `.env` 文本）。核心引擎不包含任何网络、部署、服务管理、
凭据处理或系统修改行为。

本页是文档总入口和能力清单。安装与第一个产物请从
[安装与快速开始](getting-started.md) 开始。

## 推荐阅读顺序（CLI 优先）

CLI 是主要使用面，建议按下面的顺序阅读：

1. [安装与快速开始](getting-started.md) — 安装、第一个产物、退出码；
2. [CLI 命令参考](cli.md) — 每个命令、参数、`--input`/`--set`/格式与产物规则；
3. [CLI 配方](cli-cookbook.md) — 分层配置、管道输入、批量生成、CI 门禁等可复制命令；
4. [输入合并与覆盖](input-and-merge.md) — 多源合并与覆盖的完整语义；
5. [格式支持与产物](formats.md) — JSON/YAML 边界、序列化、产物命名与持久化；
6. [校验与诊断](validation.md) — `Diagnostic` 与退出码的编程约定。

需要编程集成时再看 [Python API](python-api.md)；需要扩展时看
[Provider 参考与开发](providers.md)。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [安装与快速开始](getting-started.md) | 环境要求、安装方式、最小可运行示例 |
| [CLI 命令参考](cli.md) | `providers` / `schema` / `generate` / `validate` / `init` / `ui` 全部参数、行为与示例 |
| [CLI 配方](cli-cookbook.md) | 面向脚本的常用命令组合与注意事项 |
| [输入合并与覆盖](input-and-merge.md) | 多输入文件、`deep_merge` 规则、`--set` 覆盖与类型推断 |
| [格式支持与产物](formats.md) | JSON/YAML 支持边界、格式检测、序列化、产物命名与持久化 |
| [校验与诊断](validation.md) | `Diagnostic`、`diagnose`/`validate` 的区别、校验辅助函数 |
| [Provider 参考与开发](providers.md) | 三个内置 Provider 的准确行为、元数据模型、自定义 Provider 指南 |
| [Python API](python-api.md) | 包级导出、engine、formats、registry、models、validation |
| [交互式向导](wizard.md) | `devconfig-gen init` 的提示类型、默认值、重试与输出选择 |
| [Web 工作台与 HTTP API](web-ui.md) | `devconfig-gen ui` 的功能、HTTP 接口、安全边界 |
| [开发与测试](development.md) | 项目结构、测试、CI、打包、文档维护 |
| [架构总览](architecture.md) | 分层、数据流、扩展点；完整设计决策见仓库根目录 [ARCHITECTURE.md](https://github.com/henryliu443/DevConfig-Gen/blob/main/ARCHITECTURE.md) |

## 能力清单

以下能力均可在当前实现中验证（括号内为对应实现文件）。

### 核心引擎与契约

- Provider 协议：`name`、`validate`、`generate` 为必需，`diagnose`、
  `describe_schema`/`steps` 可选（`models.py`、`engine.py`）。
- 单入口流水线：CLI、Python API、向导、Web 工作台都调用
  `devconfig_gen.engine.generate`（`engine.py`）。
- 数据契约：`GenerationRequest`、`GenerationResult`、`GeneratedArtifact`、
  `Diagnostic`、`ProviderField`、`ProviderStep`（`models.py`）。
- Provider 注册表：名称必须为非空小写字符串，重复注册或未知名称抛出
  `ValueError`（`registry.py`）。

### 命令行（重点）

- 六个子命令：`providers`（发现）、`schema`（元数据）、`generate`（生成）、
  `validate`（校验）、`init`（终端向导）、`ui`（Web 工作台）（`cli.py`）。
- 脚本友好的稳定契约：退出码 `0`/`1`/`2`；`validate --json` 输出诊断数组；
  `schema` 输出步骤数组；产物确定性可 diff。
- 多输入 `--input`（可重复、从左到右深度合并）与点路径 `--set` 覆盖，
  值按 JSON 字面量推断类型（`cli.py`、`engine.build_request`）。
- 输出格式解析：`--format` → `--name` 后缀 → Provider 默认；产物名支持子目录，
  拒绝绝对路径与 `..`。
- 详细参考见 [CLI 命令参考](cli.md)，配方见 [CLI 配方](cli-cookbook.md)。

### 输入

- JSON 与 YAML 文件加载，按扩展名或内容自动检测格式（`formats.py`）。
- 多个输入文件按从左到右深度合并；映射递归合并，标量/列表整体替换；
  不修改输入对象（`formats.deep_merge`、`engine.build_request`）。
- 点路径覆盖（`--set app.port=9090`），值按 JSON 字面量推断类型
  （`engine._set_nested`、`formats.coerce_scalar`）。

### 校验与诊断

- `Diagnostic(field, message, severity)`：字段为点路径，severity 为
  `error` 或 `warning`（`models.py`）。
- 校验辅助函数：`expect_mapping`、`expect_string`、`expect_integer`、
  `expect_enum`、`expect_string_mapping`，一次收集全部问题
  （`validation.py`）。
- `validate` 返回渲染后的消息字符串；`diagnose` 返回结构化 `Diagnostic`；
  未实现 `diagnose` 的 Provider 由引擎自动降级包装（`engine.diagnose_request`）。

### 内置 Provider

- `custom`：无 schema，接受任意 JSON/YAML 结构（映射、序列或标量根），
  原样输出；`tree` 类型字段驱动 Web 工作台的递归编辑器。
- `json`：透传/重新序列化；要求根为映射；产物默认名为
  `config.json` / `config.yaml`。
- `env`：把嵌套映射扁平化为 `UPPER_SNAKE_CASE` 变量，输出 `.env` 纯文本
  （`media_type: text/plain`）。

### 其他客户端

- Python API：`generate`、`generate_pipeline`、`generate_from_file`、
  `validate_request`、`diagnose_request`、`describe_provider`、
  `build_request`（`engine.py`）。
- 终端向导 `init`：按 `ProviderField.type` 提示，支持默认值、选项、上下界、
  从文件加载文档、校验失败后保留答案重试（`interactive.py`）。
- Web 工作台 `ui`：标准库 `ThreadingHTTPServer` 提供的单页应用 + JSON API；
  中英双语、实时预览、草稿保存、磁盘导出沙箱、仅回环访问（`web_ui.py`）。

### 产物与输出

- 产物 `GeneratedArtifact(name, content, media_type)`；`content` 为字符串时
  原样写入，否则按媒体类型序列化（`engine._persist`、`engine._serialize_artifact`）。
- 默认名：`custom.json`/`custom.yaml`、`config.json`/`config.yaml`、`.env`；
  `--name` 可覆盖，格式按 `--format` → 文件名后缀 → 默认 JSON 的顺序解析。
- 产物名不允许绝对路径或 `..`，拒绝逃逸输出目录；子目录会自动创建。
- JSON 使用标准库 `json`（2 空格缩进、保留插入顺序、保留非 ASCII、末尾换行）；
  YAML 优先使用 PyYAML，未安装时使用内置子集解析器/序列化器。

### 工程化

- 测试套件 135 个用例，覆盖格式、校验、Provider、合并、CLI/API 等价性、
  向导、Web UI（`tests/`）。
- GitHub Actions CI：Linux/macOS × Python 3.8–3.14（`.github/workflows/ci.yml`）。
- 发布工作流：推送 `v*` 标签构建 sdist/wheel 并发布到 PyPI
  （`.github/workflows/release.yml`）。

## 模块地图

```text
src/devconfig_gen/
├── __init__.py       包导出与惰性 UI 入口（PEP 562）
├── models.py         稳定数据契约：请求/结果/产物/诊断/字段/步骤/协议
├── engine.py         唯一执行流水线：构建请求、校验、生成、持久化
├── formats.py        JSON/YAML 加载与序列化、格式检测、深度合并、类型推断
├── validation.py     路径感知的校验辅助函数与 ValidationError
├── registry.py       ProviderRegistry 与内置 Provider 注册
├── cli.py            命令行入口（仅参数解析与调用 engine）
├── interactive.py    `init` 终端向导（惰性导入）
├── web_ui.py         `ui` 本地工作台与 HTTP API（惰性导入）
└── providers/
    ├── custom.py     custom Provider
    ├── json_provider.py  json Provider
    └── env_provider.py   env Provider
```

## 版本

当前版本 `1.0.0`（`pyproject.toml`、`devconfig_gen.__version__` 与
`devconfig-gen --version` 保持一致）。
