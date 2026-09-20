# 全链路 Pluggable 定调（含 WebUI）

> 状态：**已实施（Step 1 + Step 2 完成）**
> 目标：全链路 pluggable，包括 WebUI。
> 核心结论：**Provider 是唯一扩展点**，UI 渲染是唯一缺口。
> 原则：不做大跃进。现有测试必须全程保持绿色，每一步独立可交付。
> 约束：遵循 `AGENTS.md` 与 `PROVIDER_STANDARD.md`；父仓库只承载中立基础设施，领域实现留在下游。

---

## 一、核心定调

| 问题 | 决策 |
|------|------|
| 扩展点 | **一个：Provider**。不引入 Stage / Plugin 等第二套扩展体系 |
| 缺口定位 | 链路里唯一不 pluggable 的是 **UI 渲染**（`field.type` → 前端 if/else 硬编码） |
| WebUI 零构建 | **保持**。不引入 npm/Vite，把前端 if/else 渲染升级为「Widget 注册表」 |
| Provider 的 UI 能力 | 新增可选方法 `web_ui_widgets()`；父仓库只定义机制，领域 widget 留在下游 |
| 重构方式 | **渐进迁移**，不重写。现有硬编码渲染抽成「默认 widget」，再开放注册口 |

---

## 二、链路逐环节归属

| 环节 | 归属 | 现状 | 需要动吗？ |
|---|---|---|---|
| 输入加载 | 调用方（函数参数） | `generate(context=...)` 可完全绕过 `build_request` | 否 |
| 合并策略 | 调用方（函数参数） | 调用方可自己合并好再传 `context` | 否 |
| 校验 / 生成 | Provider | `validate()` / `generate()` 已有 | 否 |
| 序列化 | Provider（通过 string content） | 返回 `str` 即接管，`env` 就是这么做的 | 否 |
| 持久化 | 调用方（`output_dir` 参数） | 不传 `output_dir` 就拿到 `GenerationResult` 自行处理 | 否 |
| **UI 渲染** | **缺入口** | `field.type` → 前端 if/else 硬编码，Provider 无法引入新类型 | **是** |

**结论**：唯一要补的缺口 = UI 渲染的 Provider 接入能力。

---

## 三、解决方案（两步）

### Step 1：WebUI 前端查表渲染

把 `web_ui.py` 的 `renderStep()` 从 if/else 改成查注册表，六种现有类型（string/integer/boolean/mapping/document/tree）抽成默认 widget。纯前端实现细节，行为不变。

| 变更 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/devconfig_gen/web_ui.py` | 前端 JS：WidgetRegistry + 默认 widgets |
| 新增 | `tests/test_web_ui_widgets.py` | 默认 widget 渲染、注册表覆盖、schema 联动 |
| 运行 | 全量测试 | 现有测试必须全绿 |

**验证标准**：`custom` / `json` / `env` 三个内置 Provider 的 WebUI 行为与重构前一致。

### Step 2：Provider 可选能力 `web_ui_widgets()` + `/api/widgets`

Provider 声明 `{field_type: js_factory_code}` → 后端 `/api/widgets?provider=x` 吐出 → 前端注册进同一张表。没实现的 Provider 行为完全不变。

| 变更 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/devconfig_gen/models.py` | 新增 `WebUIWidgets` 协议（纯文档性，不强制继承） |
| 修改 | `src/devconfig_gen/web_ui.py` | `/api/widgets` 读取 Provider 的 `web_ui_widgets()`；前端 loadSchema 后动态注册 |
| 新增 | `tests/test_web_ui_widgets.py` | 自定义 widget 注入、未知类型回退 string |
| 文档 | `PROVIDER_STANDARD.md` | 新增「WebUI Widget 扩展」章节 |
| 文档 | `ARCHITECTURE.md` / `README.md` | 同步说明 |
| 示例 | 下游仓库 | sing-box Provider 实现自定义节点编辑器 widget |

---

## 四、明确不做的事

- 不新增 `pipeline.py`；不引入 Stage / Plugin / Hook。
- 不把持久化下放给 Provider（安全红线）。
- 不开 WebUI 自定义 API 路由；所有扩展通过标准 API + widget 机制完成。
- 不修改 `ConfigProvider` 必需契约（`name` / `validate` / `generate`）。
- 不引入 npm/Vite；WebUI 保持零构建。

---

## 五、兼容性承诺

1. **API 兼容**：`generate()` / `generate_pipeline()` / `build_request()` 签名与行为不变。
2. **Provider 兼容**：现有 `CustomProvider` / `JsonProvider` / `EnvProvider` 及下游 Provider 无需改动。
3. **CLI 兼容**：`generate/validate/init/ui` 行为一致。
4. **测试兼容**：现有测试全部保留，不修改、不删除。

---

## 六、风险与回退

| 风险 | 缓解 |
|------|------|
| JS 重构引入前端 bug | Step 1 单独交付，先跑全量测试 + 手动验证三个内置 Provider |
| Widget 代码注入风险 | 仅接受同源 `/api/widgets` 返回的代码；Provider 代码由下游作者负责 |
| 过度设计 | 只有两个 Step；Step 1 完成即达成「WebUI pluggable」主体 |

---

## 七、维护要求

- 修改 Provider 可选能力或 Widget 协议时，必须同步更新本文件与 `ARCHITECTURE.md`。
- 任何领域实现（具体 widget、领域逻辑）**不得**回填进父仓库。
- 每步完成后运行：`PYTHONPATH=src python3 -m unittest discover -s tests -v`。
