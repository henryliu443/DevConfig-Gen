# Provider 参考与开发

Provider 是 DevConfig-Gen 的扩展点：它决定输入如何被校验、规范化并转换成产物。
引擎本身不包含任何领域逻辑，只通过注册表调用 Provider。

## Provider 契约

`devconfig_gen.models.ConfigProvider` 是一个结构化协议（`Protocol`），实现者
不需要继承任何基类。必需成员：

| 成员 | 说明 |
| --- | --- |
| `name: str` | 非空小写名称，注册表的键 |
| `validate(request) -> Sequence[str]` | 返回渲染后的错误消息；空序列表示通过 |
| `generate(request) -> GenerationResult` | 生成产物；出错时应抛出 `ValidationError` 或 `ValueError` |

可选成员（引擎会探测并按需降级）：

| 成员 | 作用 |
| --- | --- |
| `diagnose(request) -> Sequence[Diagnostic]` | 结构化诊断；未实现时 `diagnose_request` 把 `validate` 的消息包装为 `field=""` 的 `Diagnostic` |
| `describe_schema() -> Sequence[ProviderStep]` | 声明式步骤/字段；未实现时读取 `steps` 属性，再退回空元组 |
| `steps` | 类属性形式的步骤元数据 |

`generate` 的约定：先自行校验（`engine.generate` 也会先调用 `validate`），
失败时抛出 `ValidationError`；成功时返回
`GenerationResult(provider=self.name, artifacts=(...))`。

## 声明式元数据

`ProviderStep` 与 `ProviderField` 用于驱动终端向导、Web 工作台、`schema`
命令和任何第三方客户端。序列化规则（`as_dict()`）：

- `ProviderField`：`name`、`title`、`type`、`required`、`default`、
  `description`，可选 `choices`、`minimum`、`maximum`、`i18n`；
  `title` 为空时回退为 `name`，空 `i18n` 会被省略。
- `ProviderStep`：`id`、`title`、`description`、`fields`，可选 `i18n`。
- `i18n` 的结构为 `{"<locale>": {"title": ..., "description": ...}}`，内置
  Provider 提供 `zh` 翻译；规范英文文案始终保留在默认字段中。

`ProviderField.type` 决定客户端渲染方式：

| `type` | 终端向导 | Web 工作台 |
| --- | --- | --- |
| `string` | 文本提示，支持默认值/选项 | 文本框或下拉框（有 `choices` 时） |
| `integer` | 整数提示，支持 `minimum`/`maximum` | 数字输入框 |
| `boolean` | y/n 提示 | 复选框 |
| `mapping` / `dict` | 逐行 `key=value` 输入 | 键值对表格 |
| `document` | 可输入文件路径，或退化为 `key=value` | 拖拽上传 + 内联文本编辑器 |
| `tree` | 同 `document` | 结构模式（递归树）+ 文本模式（JSON/YAML） |

`required`、`choices`、`minimum`、`maximum`、`default` 是客户端提示和
约束元数据；是否真正强制由各 Provider 的 `validate` 决定。

## 内置 Provider

### custom

- 名称：`custom`
- 元数据：步骤 `document`（标题 “Custom document”），字段 `document`
  （`type="tree"`，`required=False`）
- 行为：无 schema、无字段校验（`validate` 永远返回空）；接受任意 JSON/YAML
  结构，包括映射、序列和标量根。
- 上下文解包：当上下文是映射且**唯一键**为 `document` 时，输出该键的值；
  否则原样输出整个上下文。
- 产物：默认 `custom.json` 或 `custom.yaml`，媒体类型
  `application/json` / `application/yaml`。

```python
from devconfig_gen import GenerationRequest, generate

generate("custom", GenerationRequest(context={"document": {"a": {"b": [1, 2]}}}))
# -> custom.json，内容 {"a": {"b": [1, 2]}}

generate("custom", GenerationRequest(context={"document": [1, 2, 3]}))
# -> custom.json，内容 [1, 2, 3]

generate("custom", GenerationRequest(context={"document": {"a": 1}, "extra": 2}))
# -> custom.json，内容 {"document": {"a": 1}, "extra": 2}
```

### json

- 名称：`json`
- 元数据：步骤 `document`（标题 “Document”），字段 `document`
  （`type="document"`，`required=True`）
- 行为：透传/重新序列化，不做字段转换。
- 校验：解包后上下文必须是映射，否则返回
  `"document: expected a mapping at the root"`。
- 上下文解包：仅当唯一键 `document` 的值是**映射**时解包；若
  `document` 的值是列表等非映射，则保留 `document` 键。
- 产物：默认 `config.json` 或 `config.yaml`。

```python
generate("json", GenerationRequest(context={"document": {"a": 1}}))
# -> config.json，内容 {"a": 1}

generate("json", GenerationRequest(context={"document": [1, 2]}))
# -> config.json，内容 {"document": [1, 2]}
```

### env

- 名称：`env`
- 元数据：步骤 `variables`（标题 “Environment variables”），字段
  `variables`（`type="mapping"`，`required=True`）
- 行为：把嵌套映射扁平化为 `UPPER_SNAKE_CASE` 变量，输出 `.env` 文本
  （`media_type: text/plain`），默认文件名 `.env`，可用 `options["name"]`
  覆盖（例如 `.env.production`）。
- 忽略 `format` 选项：无论 `--format` 是什么，产物都是 `.env` 文本。

转换规则：

1. 上下文必须是映射。唯一键为 `variables` 且其值为映射时，使用该值作为
   变量根。
2. 空映射（包括 `{}` 与 `{"variables": {}}`）报错
   `variables must not be empty`；非映射报错
   `variables must be a mapping at the document root`。
3. 每个键段先做规范化：把 `[^A-Za-z0-9]+` 替换为 `_`，去掉首尾 `_`，
   再转大写。空键段报错 `<path> is not a valid variable name`。
4. 嵌套映射递归展开，路径用 `_` 连接；空嵌套映射生成空值变量
   （如 `A=`）。
5. 列表/元组：若包含映射则报错 `<path> must not contain mappings`；
   否则各项用逗号连接。标量转换：`None`→空串、`True`/`False`→
   `true`/`false`、数字→十进制文本、其他→`str()`。
6. 集合（`set`）等不支持的值类型报错 `<path> has an unsupported value type`。
7. 不同路径扁平化后撞名时报错
   `'<KEY>' collides with '<origin>' after normalization`（例如
   `{"a": {"b": 1}, "a_b": 2}` 产生 `'A_B' collides with 'a.b'`）。
   注意：同一层中两个直接规范化后同名的键（如 `a-b` 与 `a_b`）不会被
   检测为冲突，后出现的键会覆盖先出现的键。

示例：

```python
generate("env", GenerationRequest(context={"database": {"host": "localhost", "port": 5432}, "debug": True}))
# .env:
# DATABASE_HOST=localhost
# DATABASE_PORT=5432
# DEBUG=true

generate("env", GenerationRequest(context={"enabled": False, "ratio": 0.5, "empty": None, "tags": ["a", "b"]}))
# ENABLED=false
# RATIO=0.5
# EMPTY=
# TAGS=a,b
```

## 内置 Provider 汇总

| Provider | 根要求 | 默认产物 | 媒体类型 | 字段校验 |
| --- | --- | --- | --- | --- |
| `custom` | 任意（映射/序列/标量） | `custom.json` / `custom.yaml` | `application/json` / `application/yaml` | 无 |
| `json` | 映射 | `config.json` / `config.yaml` | `application/json` / `application/yaml` | 根必须是映射 |
| `env` | 映射 | `.env` | `text/plain` | 非空映射；列表不得含映射等 |

## 编写自定义 Provider

最小实现只需要 `name`、`validate`、`generate`：

```python
from devconfig_gen import (
    GeneratedArtifact, GenerationResult, ValidationError,
)


class UpperProvider:
    name = "upper"

    def validate(self, request):
        if not isinstance(request.context, dict):
            return ("context must be a mapping",)
        return ()

    def generate(self, request):
        errors = self.validate(request)
        if errors:
            raise ValidationError(errors)
        return GenerationResult(
            provider=self.name,
            artifacts=(
                GeneratedArtifact(
                    name="upper.json",
                    content={str(k).upper(): v for k, v in request.context.items()},
                ),
            ),
        )
```

注册并调用：

```python
from devconfig_gen import GenerationRequest, ProviderRegistry, generate

registry = ProviderRegistry((UpperProvider(),))
result = generate("upper", GenerationRequest(context={"a": 1}), registry=registry)
```

要获得完整的向导/工作台支持，再补充 `steps`/`describe_schema` 与 `diagnose`：

```python
from devconfig_gen import Diagnostic, ProviderField, ProviderStep


class GreetingProvider:
    name = "greeting"

    steps = (
        ProviderStep(
            id="input",
            title="Greeting input",
            i18n={"zh": {"title": "问候输入"}},
            fields=(
                ProviderField(
                    "who",
                    type="string",
                    required=True,
                    title="Who",
                    description="Who to greet.",
                    i18n={"zh": {"title": "对象"}},
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
                ),
            ),
        )
```

注册规则：

- `name` 必须是非空字符串，且 `str(name).strip().lower() == name`
  （即已经全小写且无首尾空白），否则 `ProviderRegistry.register` 抛出
  `ValueError`；
- 同名重复注册抛出 `ValueError`；
- 自定义注册表可通过 `generate(..., registry=registry)`、向导的
  `registry=` 参数和 Web 工作台测试中的 `WebUIRequestHandler.registry`
  传入。

### 使用内置 Provider 作为参考

- `src/devconfig_gen/providers/custom.py`：最简结构，演示 `tree` 元数据与
  上下文解包；
- `src/devconfig_gen/providers/json_provider.py`：演示 `document` 元数据与
  根类型校验；
- `src/devconfig_gen/providers/env_provider.py`：演示真实转换、`diagnose`
  结构化诊断、多字段校验与纯文本产物。

## 元数据驱动的客户端

- CLI `devconfig-gen schema --provider <name>` 打印
  `[step.as_dict() for step in describe_provider(name)]`；
- `devconfig-gen init` 遍历 `steps`，按 `ProviderField.type` 提示输入；
- Web 工作台的 `/api/schema` 返回相同结构，前端按类型渲染表单。

新增 Provider 后无需修改 CLI、向导或 Web 工作台：注册到 `default_registry`
（或传入自定义 `registry`）即可被三者识别。
