# Web 工作台与 HTTP API（ui）

`devconfig-gen ui` 启动一个零构建、零前端依赖的本地单页应用：HTML/CSS/JS
全部内嵌在 `src/devconfig_gen/web_ui.py` 中，由 Python 标准库
`ThreadingHTTPServer` 提供，不需要 npm / node_modules。

```bash
devconfig-gen ui
devconfig-gen ui --host 127.0.0.1 --port 8848 --workspace ~/projects/my-app --no-browser
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `8848` | 监听端口 |
| `--no-browser` | 否 | 不自动打开浏览器 |
| `--workspace` | 当前工作目录 | 允许 `/api/export` 写入的根目录 |

启动后终端打印本地地址、导出工作空间和停止方式；按 `Ctrl+C` 停止并返回
`0`。浏览器默认打开 `http://127.0.0.1:8848`。

## 界面功能

- **中英双语**：右上角 `中 / EN` 一键切换，偏好保存在
  `localStorage["dcg_lang"]`；步骤/字段文案优先使用 Provider 的 `i18n`
  翻译（内置 Provider 提供中文）。
- **分步表单向导**：按 Provider 的 `steps` 渲染步骤导航，逐字段编辑。
- **实时预览**：左侧编辑，右侧实时显示序列化后的产物；输入防抖 150ms。
- **内联校验**：预览区底部显示“配置有效”或问题数量，并把诊断挂到对应
  字段上。
- **按字段类型渲染**：
  - `tree`：结构模式（递归树编辑器，任意层级增删字段/项、切换类型
    string/number/boolean/object/array/null、嵌套、批量添加）+ 文本模式
    （直接输入 JSON/YAML）；
  - `document`：拖拽/点击上传 `.json`/`.yaml`/`.yml` 文件 + 内联文本编辑器
    （示例、格式化、清空）；
  - `mapping`：键值对表格；
  - `choices`：下拉框；`boolean`：复选框；`integer`：数字输入。
- **导入文件**：顶部按钮上传文档，通过 `/api/parse` 反向解析并回填表单。
- **加载预设**：为 `custom`/`json`/`env` 提供内置示例数据。
- **全部清空**：重置当前 Provider 的表单内容。
- **草稿保存**：每次编辑写入 `localStorage["devconfig_draft_<provider>"]`，
  切换 Provider 或刷新后自动恢复。
- **保存到磁盘**：弹出目标目录输入框，通过 `/api/export` 写入并返回保存
  的文件列表。
- **复制**：把预览内容复制到剪贴板。
- **快捷键**：`Cmd/Ctrl + Enter` 下一步（最后一步显示完成提示），
  `Cmd/Ctrl + S` 保存到磁盘。
- **输出格式开关**：YAML / JSON。XML 按钮是预留入口，点击只弹出
  “即将支持”提示，不会切换格式。

## 安全边界

Web 工作台按“仅本机”设计：

- **仅回环**：`Host` 头不是 `127.0.0.1`、`localhost`、`::1`（或空）的请求
  直接返回 `403 {"error": "forbidden host"}`，用于缓解 DNS rebinding；
- **导出沙箱**：`/api/export` 的目标目录必须等于或位于 `workspace_root`
  （默认当前目录）之内，否则返回 `400`；
- **不缓存页面**：`/` 与 `/index.html` 返回 `Cache-Control: no-store, ...`，
  JSON 接口返回 `Cache-Control: no-store`；
- **无外部资源**：页面不引用任何 CDN 或远程资源。

## HTTP API

所有接口仅接受本机请求。请求体必须是 UTF-8 编码的 JSON 对象；错误统一返回
`{"error": "<message>"}` 和 `400`（未知路由返回 `404`）。

### GET /api/providers

```json
{ "providers": ["custom", "env", "json"] }
```

### GET /api/schema?provider=<name>

返回 `[step.as_dict() ...]`。默认 Provider 为 `custom`；未知 Provider 返回
`400`。

```bash
curl 'http://127.0.0.1:8848/api/schema?provider=env'
```

### POST /api/validate

请求：

```json
{ "provider": "env", "context": {} }
```

响应：

```json
{
  "valid": false,
  "diagnostics": [
    { "field": "variables", "message": "variables must not be empty", "severity": "error" }
  ]
}
```

`provider` 默认 `custom`，`context` 默认 `{}`；未知 Provider 返回 `400`。

### POST /api/generate

请求：

```json
{ "provider": "custom", "context": { "document": { "app": { "name": "web" } } }, "format": "yaml" }
```

响应：

```json
{
  "artifacts": [
    {
      "name": "custom.yaml",
      "content": "app:\n  name: web\n",
      "media_type": "application/yaml"
    }
  ]
}
```

- `format` 默认 `yaml`；字符串产物（如 `.env`）原样返回，结构化产物按媒体
  类型序列化为字符串；
- 校验失败返回 `400`；
- 该接口不写文件，仅返回内容用于预览。

### POST /api/export

与 `/api/generate` 相同的请求字段，外加 `output_dir`：

```json
{
  "provider": "custom",
  "context": { "document": { "a": 1 } },
  "format": "json",
  "output_dir": "."
}
```

成功响应：

```json
{ "success": true, "saved": ["/abs/path/custom.json"] }
```

`output_dir` 相对 `workspace_root` 解析；越界返回 `400`。

### POST /api/parse

把 JSON/YAML 文本解析为上下文，用于文件上传和文本模式编辑：

```json
{ "content": "app:\n  name: parsed-svc\n" }
```

```json
{ "context": { "app": { "name": "parsed-svc" } } }
```

`content` 必须是字符串；解析失败返回 `400`。

## Python 入口

```python
from devconfig_gen import run_web_ui

run_web_ui(host="127.0.0.1", port=8848, open_browser=False, workspace_root=".")
```

`run_web_ui` 阻塞运行，直到 `Ctrl+C`。测试可以直接实例化
`devconfig_gen.web_ui.WebUIRequestHandler`，通过类属性 `registry` 和
`workspace_root` 注入自定义注册表与沙箱目录（`tests/test_web_ui.py` 即采用
这种方式）。
