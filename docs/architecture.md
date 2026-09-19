# 架构总览

本页是架构摘要。完整的设计决策与边界说明见仓库根目录
[ARCHITECTURE.md](https://github.com/henryliu443/DevConfig-Gen/blob/main/ARCHITECTURE.md)。

## 目标

把结构化输入文档（JSON/YAML）转换成经过校验、规范化的结构化配置产物
（JSON/YAML/纯文本），由可扩展的 Provider 驱动。引擎与具体领域无关，
schema、规范化与校验都属于 Provider。

## 分层

```text
CLI（generate/validate/schema）   init 向导   ui 工作台
        |                             |            |
        +-----------------------------+------------+
                                      v
engine.py  —— build_request / generate_pipeline / generate_from_file
  |           diagnose_request / describe_provider
  |           （唯一共享流水线，包含多源 deep_merge）
  v
ProviderRegistry -> ConfigProvider（custom / json / env）
  |
  v
formats.py   （JSON/YAML 加载、序列化、检测、媒体类型、deep_merge、coerce_scalar）
validation.py（路径感知的 Diagnostic 辅助函数）
```

## 数据流

```text
输入文件 / 内存上下文
        |
        v
formats.load_*          解析 + 格式检测
        |
        v
formats.deep_merge      多文件从左到右深度合并
        |
        v
engine._set_nested      点路径覆盖（最后应用）
        |
        v
Provider.validate / diagnose   规范化 + 结构化诊断
        |
        v
Provider.generate       产物（数据结构或预渲染字符串）
        |
        v
engine._persist         序列化 + 可选写入 output_dir
        |
        v
JSON / YAML / .env
```

## 数据契约（`models.py`）

- `GenerationRequest`：不可变的 `context`（输入文档）与 `options`
  （如 `format`、`name`）；
- `Diagnostic`：`field`（点路径）、`message`（渲染文本）、`severity`；
- `GeneratedArtifact`：`name`、`content`（数据结构或字符串）、`media_type`；
- `GenerationResult`：Provider 名称与产物；
- `ProviderField` / `ProviderStep`：声明式元数据，支持可选 `i18n`；
- `ConfigProvider`：Provider 协议。

## 引擎（`engine.py`）

`generate()` 是唯一执行点：查找 Provider → `validate` → `generate` →
可选持久化。更高层函数（`generate_pipeline`、`generate_from_file`、
`validate_request`、`diagnose_request`、`describe_provider`）只构建请求并
委托；CLI 不包含任何生成逻辑。

`build_request()` 组装上下文：内存上下文 → 多个输入文件（左到右
`deep_merge`）→ 点路径 `overrides`。

持久化按 `media_type` 选择序列化器；字符串产物原样写入；产物名逃逸输出
目录会被拒绝。

## 设计决策摘要

1. `models.py` 是唯一稳定的核心数据契约；
2. `registry.py` 是扩展缝：注册一个小写 `name` 的对象即可新增 Provider；
3. 引擎不直接导入任何具体 Provider，只通过注册表工作；
4. CLI、Python API、向导、Web 工作台共享同一条代码路径，产物逐字节一致；
5. 导入包无副作用；只有显式传入 `output_dir` 才会写文件；
6. Provider 元数据（`diagnose`、`steps`、`describe_schema`）可选，
   最小 Provider 只需 `name`、`validate`、`generate`；
7. 序列化确定：JSON/YAML 保留插入顺序；
8. 核心引擎不包含远程操作、系统修改、凭据处理或部署；唯一的文件写入是
   显式的 `output_dir`（Web UI 由 workspace 沙箱限制）。

## 范围之外

DevConfig-Gen 不执行部署、远端仓库操作、服务管理、凭据存储，也不自动迁移
机器状态。
