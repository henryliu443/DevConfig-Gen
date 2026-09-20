# 安装与快速开始

## 环境要求

- Python 3.8 或更高版本（CI 覆盖 3.8–3.14，Linux 与 macOS）；
- 运行时零第三方依赖；
- 可选：安装 PyYAML 以获得完整 YAML 支持。未安装时使用内置 YAML 子集
  解析器/序列化器（支持边界见[格式支持与产物](formats.md)）。

## 安装

### 方式一：从仓库安装（开发模式）

```bash
git clone https://github.com/henryliu443/DevConfig-Gen.git
cd DevConfig-Gen
pip install -e ".[yaml]"     # 可选：安装 PyYAML
```

安装后可直接使用 `devconfig-gen` 命令。

### 方式二：从 PyPI 安装

发布工作流会在推送 `v*` 标签时构建并发布到 PyPI：

```bash
pip install devconfig-gen            # 运行时零依赖
pip install "devconfig-gen[yaml]"    # 可选 PyYAML
```

### 方式三：不安装，直接运行

```bash
PYTHONPATH=src python3 -m devconfig_gen.cli --help
```

下文示例使用已安装的 `devconfig-gen`；未安装时把该命令替换为
`PYTHONPATH=src python3 -m devconfig_gen.cli` 即可。

## 验证安装

```bash
devconfig-gen --version      # devconfig-gen 1.1.0
devconfig-gen providers      # 输出三行：custom、env、json
```

当前版本为 **1.1.0**，测试套件共 **143** 个用例。1.1.0 为 Web 工作台引入了
查表驱动的字段渲染（六种内置类型 + Provider 自定义 Widget）、`☰` 汉堡侧边栏
与空上下文检测；CLI 与 Python API 的行为保持不变。

## 第一个产物（3 分钟）

仓库自带示例输入 `examples/custom.yaml`：

```yaml
app:
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

生成 YAML 配置：

```bash
devconfig-gen generate \
  --provider custom \
  --input examples/custom.yaml \
  --output-dir generated \
  --format yaml
# 终端输出：generated generated/custom.yaml
```

只校验、不写文件：

```bash
devconfig-gen validate --provider custom --input examples/custom.yaml
# 终端输出：examples/custom.yaml: valid
```

生成 `.env`：

```bash
devconfig-gen generate --provider env --input examples/vars.yaml --output-dir generated
# 终端输出：generated generated/.env
cat generated/.env
# DATABASE_HOST=localhost
# DATABASE_PORT=5432
# DATABASE_NAME=appdb
# DEBUG=true
# LOG_LEVEL=info
```

查看 Provider 的声明式字段/步骤（JSON）：

```bash
devconfig-gen schema --provider env
```

多输入合并与覆盖：

```bash
devconfig-gen generate \
  --provider custom \
  --input configs/base.yaml \
  --input configs/prod.json \
  --set app.port=9090 \
  --output-dir generated --format yaml
```

## 引导式流程

终端向导（适合无头服务器 / SSH）：

```bash
devconfig-gen init --provider custom
```

本地 Web 工作台（默认 `http://127.0.0.1:8848`）：

```bash
devconfig-gen ui
devconfig-gen ui --workspace ~/projects/my-app --no-browser
```

工作台支持中英双语、亮/暗主题、分步表单、实时预览与草稿自动保存，字段渲染
查表驱动；`custom` 提供递归树编辑器。界面细节见
[Web 工作台与 HTTP API](web-ui.md)。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（`generate` 写出产物、`validate` 通过、向导完成、`ui` 被 Ctrl+C 停止） |
| `1` | 校验失败，或向导被取消/输入结束 |
| `2` | 输入或用法错误（未知 Provider、文件不存在、格式错误、`--set` 语法错误、产物名越界） |

## 下一步

CLI 是主要使用面，建议按此顺序继续：

- [CLI 命令参考](cli.md) — 每个命令、参数、`--input`/`--set` 与退出码；
- [CLI 配方](cli-cookbook.md) — 分层配置、管道输入、批量生成、CI 门禁；
- [输入合并与覆盖](input-and-merge.md) — 多源合并语义；
- [格式支持与产物](formats.md) — JSON/YAML 边界与产物命名。

编程集成与扩展：

- [Python API](python-api.md)
- [Provider 参考与开发](providers.md)
