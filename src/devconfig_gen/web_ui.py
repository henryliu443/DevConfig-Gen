"""Embedded local WebUI for DevConfig-Gen.

Provides a zero-build, Mac-first, self-contained web wizard with live preview,
split-view editing, template pre-filling, and config export. Zero npm/node_modules
required — runs out-of-the-box using the Python standard library http.server.
"""

from __future__ import annotations

import json
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from . import formats
from .engine import describe_provider, diagnose_request, generate
from .models import GenerationRequest
from .registry import ProviderRegistry, default_registry

_HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevConfig-Gen — 配置工作台</title>
  <style>
    :root {
      --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      
      --bg: #f5f5f7;
      --card-bg: #ffffff;
      --card-border: #e5e5ea;
      --text: #1d1d1f;
      --text-muted: #86868b;
      --primary: #0071e3;
      --primary-hover: #0077ed;
      --accent: #34c759;
      --danger: #ff3b30;
      --code-bg: #1e1e24;
      --code-text: #e1e1e6;
      --input-bg: #ffffff;
      --input-border: #d2d2d7;
      --input-focus: #0071e3;
      --nav-bg: rgba(255, 255, 255, 0.85);
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #000000;
        --card-bg: #1c1c1e;
        --card-border: #2c2c2e;
        --text: #f5f5f7;
        --text-muted: #86868b;
        --primary: #2997ff;
        --primary-hover: #40a9ff;
        --accent: #30d158;
        --danger: #ff453a;
        --code-bg: #121214;
        --code-text: #e1e1e6;
        --input-bg: #2c2c2e;
        --input-border: #3a3a3c;
        --input-focus: #2997ff;
        --nav-bg: rgba(28, 28, 30, 0.85);
      }
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-sans);
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }

    header {
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--nav-bg);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.75rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 600;
      font-size: 1.05rem;
      letter-spacing: -0.01em;
    }
    .brand-tag {
      font-size: 0.75rem;
      padding: 0.15rem 0.4rem;
      background: var(--primary);
      color: #fff;
      border-radius: 4px;
      font-weight: 500;
    }

    .header-controls {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .container {
      display: flex;
      flex: 1;
      max-width: 1600px;
      width: 100%;
      margin: 0 auto;
      padding: 1.5rem;
      gap: 1.5rem;
    }

    .wizard-panel {
      flex: 1.1;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    .preview-panel {
      flex: 0.9;
      display: flex;
      flex-direction: column;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    }

    /* Steps Bar */
    .stepper-nav {
      display: flex;
      gap: 0.5rem;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 0.5rem;
    }
    .step-btn {
      flex: 1;
      padding: 0.6rem 0.8rem;
      background: transparent;
      border: none;
      border-radius: 8px;
      font-family: inherit;
      font-size: 0.85rem;
      font-weight: 500;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
    }
    .step-btn.active {
      background: var(--primary);
      color: #fff;
      box-shadow: 0 2px 8px rgba(0, 113, 227, 0.25);
    }
    .step-btn.completed {
      color: var(--text);
    }

    /* Card */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    }

    .card-title {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
      letter-spacing: -0.01em;
    }
    .card-desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-bottom: 1.5rem;
    }

    /* Form Fields */
    .form-group {
      margin-bottom: 1.25rem;
    }
    .form-label {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.4rem;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .form-hint {
      color: var(--text-muted);
      font-size: 0.8rem;
      font-weight: normal;
      margin-top: 0.25rem;
    }
    .form-error {
      color: var(--danger);
      font-size: 0.8rem;
      margin-top: 0.25rem;
      display: none;
    }
    .has-error .form-error { display: block; }
    .has-error input, .has-error select, .has-error textarea {
      border-color: var(--danger) !important;
    }

    input[type="text"], input[type="number"], select, textarea {
      width: 100%;
      padding: 0.65rem 0.85rem;
      font-family: inherit;
      font-size: 0.9rem;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 8px;
      color: var(--text);
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
      outline: none;
    }
    input[type="text"]:focus, input[type="number"]:focus, select:focus, textarea:focus {
      border-color: var(--input-focus);
      box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15);
    }

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 500;
    }
    .checkbox-label input {
      width: 1.1rem;
      height: 1.1rem;
      accent-color: var(--primary);
    }

    /* Buttons */
    .btn {
      padding: 0.6rem 1rem;
      border-radius: 8px;
      font-family: inherit;
      font-size: 0.85rem;
      font-weight: 600;
      border: 1px solid transparent;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
    }
    .btn-primary {
      background: var(--primary);
      color: #fff;
    }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-secondary {
      background: var(--card-bg);
      border-color: var(--card-border);
      color: var(--text);
    }
    .btn-secondary:hover {
      background: rgba(128, 128, 128, 0.08);
    }

    .wizard-actions {
      display: flex;
      justify-content: space-between;
      margin-top: 1.5rem;
      padding-top: 1.25rem;
      border-top: 1px solid var(--card-border);
    }

    /* Preview Panel */
    .preview-header {
      padding: 0.75rem 1.25rem;
      background: var(--card-bg);
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .preview-title {
      font-size: 0.9rem;
      font-weight: 600;
    }
    .preview-toolbar {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }
    .format-toggle {
      display: flex;
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 2px;
    }
    .format-btn {
      padding: 0.25rem 0.6rem;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-size: 0.75rem;
      font-weight: 600;
      border-radius: 4px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
    }
    .format-btn.active {
      background: var(--primary);
      color: #fff;
    }
    .format-btn.reserved {
      opacity: 0.7;
    }
    .format-btn.reserved:hover {
      opacity: 0.95;
    }
    .format-badge {
      font-size: 0.6rem;
      padding: 1px 4px;
      border-radius: 3px;
      background: rgba(128, 128, 128, 0.2);
      color: var(--text-muted);
      font-weight: 500;
      text-transform: uppercase;
    }

    /* Document Upload & Raw Editor */
    .doc-editor-card {
      border: 1px solid var(--card-border);
      border-radius: 8px;
      overflow: hidden;
      margin-top: 0.5rem;
      background: var(--card-bg);
    }
    .doc-dropzone {
      border: 2px dashed var(--card-border);
      border-radius: 8px;
      padding: 1.25rem 1rem;
      text-align: center;
      cursor: pointer;
      background: rgba(128, 128, 128, 0.03);
      transition: all 0.2s ease;
      margin-bottom: 0.75rem;
    }
    .doc-dropzone:hover, .doc-dropzone.drag-over {
      border-color: var(--primary);
      background: rgba(0, 113, 227, 0.06);
    }
    .doc-dropzone-icon {
      font-size: 1.5rem;
      margin-bottom: 0.25rem;
    }
    .doc-dropzone-text {
      font-size: 0.85rem;
      font-weight: 500;
      color: var(--text);
    }
    .doc-dropzone-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.2rem;
    }
    .doc-editor-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.4rem 0.75rem;
      background: var(--input-bg);
      border-bottom: 1px solid var(--card-border);
      font-size: 0.75rem;
    }
    .doc-editor-toolbar-actions {
      display: flex;
      gap: 0.4rem;
    }
    .doc-editor-textarea {
      width: 100%;
      min-height: 220px;
      padding: 0.75rem;
      font-family: var(--font-mono);
      font-size: 0.82rem;
      line-height: 1.5;
      background: var(--code-bg);
      color: var(--code-text);
      border: none;
      resize: vertical;
      outline: none;
      box-sizing: border-box;
      display: block;
    }

    /* Recursive Tree Editor */
    .tree-root {
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 0.6rem 0.75rem;
      background: var(--card-bg);
      overflow-x: auto;
    }
    .tree-children {
      border-left: 2px solid var(--card-border);
      margin-left: 0.35rem;
      padding-left: 0.5rem;
      margin-top: 0.3rem;
    }
    .tree-row {
      display: flex;
      align-items: flex-start;
      gap: 0.4rem;
      margin-bottom: 0.35rem;
    }
    .tree-row > .tree-node {
      flex: 1 1 auto;
      min-width: 0;
    }
    .tree-row input.tree-key {
      flex: 0 0 8rem;
      width: 8rem;
      min-width: 6rem;
      padding: 0.35rem 0.5rem;
      font-size: 0.8rem;
    }
    .tree-type {
      flex: 0 0 auto;
      width: auto;
      padding: 0.3rem 0.4rem;
      font-size: 0.75rem;
    }
    .tree-row input.tree-value {
      flex: 1 1 6rem;
      min-width: 5rem;
      width: auto;
      padding: 0.35rem 0.5rem;
      font-size: 0.8rem;
    }
    .tree-btn {
      padding: 0.25rem 0.5rem;
      font-size: 0.72rem;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      background: var(--input-bg);
      color: var(--text);
      cursor: pointer;
      white-space: nowrap;
    }
    .tree-btn.remove {
      color: var(--danger);
    }
    .tree-btn.add {
      color: var(--primary);
    }
    .tree-btn.nest {
      color: var(--text);
      font-weight: 600;
    }
    .tree-bulk {
      display: flex;
      gap: 0.35rem;
      margin-top: 0.3rem;
      align-items: center;
    }
    .tree-bulk input {
      flex: 1 1 auto;
      min-width: 8rem;
      padding: 0.35rem 0.5rem;
      font-size: 0.78rem;
    }
    .tree-bulk .tree-btn {
      flex: 0 0 auto;
    }
    .tree-null {
      font-size: 0.8rem;
      color: var(--text-muted);
      padding: 0.35rem 0;
    }
    .tree-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.4rem;
    }
    .tree-toolbar-title {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text);
    }
    .editor-mode-toggle {
      display: inline-flex;
      gap: 2px;
      padding: 2px;
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      margin-bottom: 0.6rem;
    }
    .mode-btn {
      padding: 0.25rem 0.8rem;
      font-size: 0.75rem;
      font-weight: 600;
      border: none;
      background: transparent;
      color: var(--text-muted);
      border-radius: 6px;
      cursor: pointer;
    }
    .mode-btn.active {
      background: var(--primary);
      color: #fff;
    }

    .preview-body {
      flex: 1;
      padding: 1.25rem;
      background: var(--code-bg);
      color: var(--code-text);
      font-family: var(--font-mono);
      font-size: 0.85rem;
      line-height: 1.6;
      overflow: auto;
      white-space: pre;
    }

    .preview-status {
      padding: 0.5rem 1.25rem;
      font-size: 0.8rem;
      border-top: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .status-ok { color: var(--accent); }
    .status-err { color: var(--danger); }

    /* Key-Value Mapping Table */
    .mapping-table {
      width: 100%;
      margin-bottom: 0.5rem;
    }
    .mapping-row {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.4rem;
    }
    .mapping-row input { flex: 1; }
    .mapping-remove {
      padding: 0.4rem 0.6rem;
      background: transparent;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      color: var(--danger);
      cursor: pointer;
    }

    /* Modal / Toast */
    .toast {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: #333;
      color: #fff;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      font-size: 0.85rem;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
      display: none;
      z-index: 1000;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>⚙️ DevConfig-Gen</span>
      <span class="brand-tag" data-i18n="studio">工作台</span>
    </div>
    <div class="header-controls">
      <select id="providerSelect" style="width: auto; padding: 0.4rem 0.8rem;">
        <option value="custom">Provider: custom</option>
      </select>
      <button class="btn btn-secondary" id="btnClearAll" data-i18n="clearAll">🧹 全部清空</button>
      <button class="btn btn-secondary" id="btnUploadConfig" data-i18n="importFile">⬆️ 导入文件</button>
      <input type="file" id="fileInput" style="display: none;" accept=".json,.yaml,.yml">
      <button class="btn btn-secondary" id="btnPreset" data-i18n="loadPreset">✨ 加载预设</button>
      <button class="btn btn-primary" id="btnExport" data-i18n="saveToDisk">💾 保存到磁盘</button>
      <button class="btn btn-secondary" id="btnLang" style="padding: 0.4rem 0.7rem; font-size: 0.8rem;">中 / EN</button>
    </div>
  </header>

  <div class="container">
    <div class="wizard-panel">
      <div class="stepper-nav" id="stepperNav"></div>
      
      <div class="card" id="stepCard">
        <h2 class="card-title" id="stepTitle">步骤标题</h2>
        <p class="card-desc" id="stepDesc">步骤描述</p>
        
        <div id="stepFields"></div>

        <div class="wizard-actions">
          <button class="btn btn-secondary" id="btnPrev" disabled data-i18n="prev">← 上一步</button>
          <div style="font-size: 0.8rem; color: var(--text-muted); align-self: center;">
            <span data-i18n="shortcut">快捷键</span>: <kbd>⌘</kbd> + <kbd>Enter</kbd>
          </div>
          <button class="btn btn-primary" id="btnNext" data-i18n="next">下一步 →</button>
        </div>
      </div>
    </div>

    <div class="preview-panel">
      <div class="preview-header">
        <span class="preview-title" data-i18n="livePreview">实时配置预览</span>
        <div class="preview-toolbar">
          <div class="format-toggle">
            <button class="format-btn active" id="fmtYaml" onclick="setFormat('yaml')">YAML</button>
            <button class="format-btn" id="fmtJson" onclick="setFormat('json')">JSON</button>
            <button class="format-btn reserved" id="fmtXml" onclick="setFormat('xml')" title="XML 格式开关预留（即将支持）/ Reserved XML switch">XML <span class="format-badge">soon</span></button>
          </div>
          <button class="btn btn-secondary" id="btnCopy" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" data-i18n="copy">📋 复制</button>
        </div>
      </div>
      <div class="preview-body" id="previewCode"># 生成预览中...</div>
      <div class="preview-status" id="previewStatus">
        <span class="status-ok">●</span> <span data-i18n="validConfig">配置有效</span>
      </div>
    </div>
  </div>

  <div class="toast" id="toast">通知消息</div>

  <script>
    // ── i18n ──────────────────────────────────────────────
    const i18n = {
      zh: {
        studio: "工作台", importFile: "⬆️ 导入文件", loadPreset: "✨ 加载预设",
        saveToDisk: "💾 保存到磁盘", prev: "← 上一步", next: "下一步 →",
        finish: "完成 ✓", shortcut: "快捷键", livePreview: "实时配置预览",
        copy: "📋 复制", validConfig: "配置有效", providerLabel: "Provider: ",
        issues: (n) => `${n} 个校验问题`,
        allDone: "✓ 全部步骤完成！可以保存或复制。",
        copied: "📋 已复制配置到剪贴板！",
        presetLoaded: "✨ 已加载预设！",
        saved: (f) => `💾 已保存: ${f}`,
        saveFail: (e) => `保存失败: ${e}`,
        exportErr: (e) => `导出错误: ${e}`,
        enterDir: "请输入保存配置的目标目录:",
        parseFail: (e) => `解析失败: ${e}`,
        uploadOk: (n) => `⬆️ 已从 ${n} 反向解析并填充！`,
        uploadErr: (e) => `上传失败: ${e}`,
        noEntries: "暂无条目",
        keyValuePairs: "键值对",
        add: "+ 添加",
        key: "键", value: "值",
        generating: "# 生成预览中...",
        validationError: "# 校验错误:\\n# ",
        xmlSoon: "XML 格式开关已预留，后续版本即将接入！",
        uploadOrDrop: "点击或拖拽 JSON / YAML 文件到此处上传",
        dropHint: "支持 .json, .yaml, .yml 格式文档，自动反向解析填充",
        docEditor: "文档编辑器 (JSON / YAML)",
        sampleDoc: "✨ 载入示例",
        formatDoc: "格式化",
        clearDoc: "清空",
        clearAll: "🧹 全部清空",
        clearAllDone: "🧹 已清空全部内容。",
        treeEmpty: "暂无字段，点击下方按钮添加。",
        treeAddField: "+ 添加字段",
        treeAddItem: "+ 添加项",
        treeRemove: "删除",
        treeNest: "往里",
        treeNestHint: "用 { } 包起来，里面可以继续嵌套",
        treeBulkAdd: "批量添加",
        treeBulkObj: "批量：a, b, c 或 a=1, b=2, …（逗号分隔，一次可加很多）",
        treeBulkArr: "批量：1, 2, 3, …（逗号分隔，一次可加很多）",
        treeRoot: "根节点",
        treeKey: "键名",
        treeType: "类型",
        modeTree: "结构模式",
        modeText: "文本模式",
        textHint: '直接输入 JSON 或 YAML：列表 [1,2,3,4,5]、嵌套 {"1":{"2":{}}}、混合都行。',
        textParseError: "解析失败",
      },
      en: {
        studio: "Studio", importFile: "⬆️ Import File", loadPreset: "✨ Load Preset",
        saveToDisk: "💾 Save to Disk", prev: "← Previous", next: "Next →",
        finish: "Finish ✓", shortcut: "Shortcut", livePreview: "Live Generated Configuration",
        copy: "📋 Copy", validConfig: "Valid configuration", providerLabel: "Provider: ",
        issues: (n) => `${n} validation ${n === 1 ? 'issue' : 'issues'}`,
        allDone: "✓ All steps completed! Ready to save or copy.",
        copied: "📋 Copied configuration to clipboard!",
        presetLoaded: "✨ Loaded preset!",
        saved: (f) => `💾 Saved: ${f}`,
        saveFail: (e) => `Save failed: ${e}`,
        exportErr: (e) => `Export error: ${e}`,
        enterDir: "Enter target directory to save configuration:",
        parseFail: (e) => `Parse failed: ${e}`,
        uploadOk: (n) => `⬆️ Successfully backfilled from ${n}!`,
        uploadErr: (e) => `Upload failed: ${e}`,
        noEntries: "No entries defined",
        keyValuePairs: "Key-Value pairs",
        add: "+ Add",
        key: "Key", value: "Value",
        generating: "# Generating preview...",
        validationError: "# Validation Error:\\n# ",
        xmlSoon: "XML format switch is reserved and will be supported in an upcoming release!",
        uploadOrDrop: "Click or drag & drop a JSON / YAML file here to upload",
        dropHint: "Supports .json, .yaml, .yml documents with auto-parsing",
        docEditor: "Document Editor (JSON / YAML)",
        sampleDoc: "✨ Sample",
        formatDoc: "Format",
        clearDoc: "Clear",
        clearAll: "🧹 Clear All",
        clearAllDone: "🧹 Cleared all content.",
        treeEmpty: "No fields yet. Use the button below to add one.",
        treeAddField: "+ Add field",
        treeAddItem: "+ Add item",
        treeRemove: "Remove",
        treeNest: "Nest",
        treeNestHint: "Wrap in { }; you can keep nesting inside",
        treeBulkAdd: "Add all",
        treeBulkObj: "Bulk: a, b, c or a=1, b=2, … (comma-separated, many at once)",
        treeBulkArr: "Bulk: 1, 2, 3, … (comma-separated, many at once)",
        treeRoot: "Root",
        treeKey: "Key",
        treeType: "Type",
        modeTree: "Tree mode",
        modeText: "Text mode",
        textHint: 'Type JSON or YAML directly: lists [1,2,3,4,5], nesting {"1":{"2":{}}}, or anything mixed.',
        textParseError: "Parse failed",
      }
    };
    let currentLang = localStorage.getItem("dcg_lang") || "zh";

    function t(key, arg) {
      const val = i18n[currentLang][key];
      return typeof val === "function" ? val(arg) : val;
    }

    // Localize a schema object (step or field) using its i18n map.
    function loc(item, key) {
      if (item && item.i18n && item.i18n[currentLang] && item.i18n[currentLang][key]) {
        return item.i18n[currentLang][key];
      }
      return item ? item[key] : undefined;
    }

    function applyLang() {
      document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        const v = t(key);
        if (v !== undefined) el.textContent = v;
      });
      document.getElementById("previewCode").textContent =
        (currentLang === "zh") ? "# 生成预览中..." : "# Generating preview...";
      document.getElementById("toast").textContent =
        (currentLang === "zh") ? "通知消息" : "Notice message";
      const btn = document.getElementById("btnLang");
      btn.textContent = (currentLang === "zh") ? "EN" : "中";
      document.documentElement.lang = (currentLang === "zh") ? "zh" : "en";
      document.title = (currentLang === "zh")
        ? "DevConfig-Gen — 配置工作台"
        : "DevConfig-Gen — Configuration Studio";
      // Refresh provider option labels
      document.querySelectorAll("#providerSelect option").forEach(opt => {
        opt.textContent = `${t("providerLabel")}${opt.value}`;
      });
    }

    // ── Core State ────────────────────────────────────────
    let currentProvider = "custom";
    let schemaSteps = [];
    let activeStepIdx = 0;
    let formData = {};
    let currentFormat = "yaml";
    let debounceTimer = null;

    // Escape untrusted strings before HTML/attribute interpolation
    function esc(value) {
      return String(value === null || value === undefined ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    // Toast
    function showToast(msg, duration = 2500) {
      const toast = document.getElementById("toast");
      toast.textContent = msg;
      toast.style.display = "block";
      setTimeout(() => { toast.style.display = "none"; }, duration);
    }

    // Deep setter for dotted path
    function setDotted(obj, path, val) {
      const parts = path.split(".");
      let cur = obj;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!cur[parts[i]] || typeof cur[parts[i]] !== "object") cur[parts[i]] = {};
        cur = cur[parts[i]];
      }
      cur[parts[parts.length - 1]] = val;
    }

    // Deep getter for dotted path
    function getDotted(obj, path, def = null) {
      if (!obj) return def;
      const parts = path.split(".");
      let cur = obj;
      for (const p of parts) {
        if (!cur || typeof cur !== "object" || !(p in cur)) return def;
        cur = cur[p];
      }
      return cur !== undefined ? cur : def;
    }

    // ── Recursive tree editor ─────────────────────────────
    const TREE_TYPES = ["string", "number", "boolean", "object", "array", "null"];

    function valueType(v) {
      if (v === null) return "null";
      if (Array.isArray(v)) return "array";
      if (typeof v === "object") return "object";
      if (typeof v === "boolean") return "boolean";
      if (typeof v === "number") return "number";
      return "string";
    }

    function defaultForType(type) {
      if (type === "number") return 0;
      if (type === "boolean") return false;
      if (type === "null") return null;
      if (type === "object") return {};
      if (type === "array") return [];
      return "";
    }

    // Interpret a typed token as number/boolean/null when it clearly is one.
    function coerceToken(text) {
      const s = String(text).trim();
      if (s === "true") return true;
      if (s === "false") return false;
      if (s === "null") return null;
      if (s !== "" && !isNaN(Number(s))) return Number(s);
      return s;
    }

    // Build an editor for one value. onChange(newValue) is called on every edit.
    function buildValueEditor(value, onChange, depth) {
      const wrap = document.createElement("div");
      wrap.className = "tree-node";
      const type = valueType(value);

      const head = document.createElement("div");
      head.className = "tree-row";

      const typeSel = document.createElement("select");
      typeSel.className = "tree-type";
      TREE_TYPES.forEach(tt => {
        const o = document.createElement("option");
        o.value = tt;
        o.textContent = tt;
        if (tt === type) o.selected = true;
        typeSel.appendChild(o);
      });
      typeSel.onchange = () => onChange(defaultForType(typeSel.value), true);
      head.appendChild(typeSel);

      if (type === "string" || type === "number") {
        const inp = document.createElement("input");
        inp.type = type === "number" ? "number" : "text";
        inp.className = "tree-value";
        inp.value = value === null || value === undefined ? "" : value;
        inp.oninput = () => {
          if (type === "number") {
            onChange(inp.value === "" ? 0 : Number(inp.value), false);
          } else {
            onChange(inp.value, false);
          }
        };
        head.appendChild(inp);
      } else if (type === "boolean") {
        const inp = document.createElement("input");
        inp.type = "checkbox";
        inp.checked = !!value;
        inp.onchange = () => onChange(inp.checked, false);
        head.appendChild(inp);
      } else if (type === "null") {
        const span = document.createElement("span");
        span.className = "tree-null";
        span.textContent = "null";
        head.appendChild(span);
      }
      wrap.appendChild(head);

      if (type === "object") {
        wrap.appendChild(buildContainerEditor(value, onChange, depth, false));
      } else if (type === "array") {
        wrap.appendChild(buildContainerEditor(value, onChange, depth, true));
      }
      return wrap;
    }

    function buildContainerEditor(obj, onChange, depth, isArray) {
      const box = document.createElement("div");
      box.className = "tree-children";

      const keys = isArray ? obj.map((_, i) => String(i)) : Object.keys(obj);
      if (keys.length === 0) {
        const empty = document.createElement("div");
        empty.className = "tree-null";
        empty.textContent = t("treeEmpty");
        box.appendChild(empty);
      }

      keys.forEach(k => {
        const row = document.createElement("div");
        row.className = "tree-row";

        if (!isArray) {
          const keyInp = document.createElement("input");
          keyInp.type = "text";
          keyInp.className = "tree-key";
          keyInp.placeholder = t("treeKey");
          keyInp.value = k;
          keyInp.onchange = () => {
            const newKey = keyInp.value.trim();
            if (!newKey || newKey === k) { keyInp.value = k; return; }
            const next = {};
            Object.keys(obj).forEach(kk => {
              if (kk === k) next[newKey] = obj[k];
              else next[kk] = obj[kk];
            });
            onChange(next, true);
          };
          row.appendChild(keyInp);
        } else {
          const idx = document.createElement("span");
          idx.className = "tree-null";
          idx.style.flex = "0 0 auto";
          idx.textContent = `[${k}]`;
          row.appendChild(idx);
        }

        const childEditor = buildValueEditor(
          isArray ? obj[Number(k)] : obj[k],
          (nv, structural) => {
            if (structural) {
              if (isArray) {
                const arr = obj.slice();
                arr[Number(k)] = nv;
                onChange(arr, true);
              } else {
                const next = Object.assign({}, obj);
                next[k] = nv;
                onChange(next, true);
              }
            } else {
              if (isArray) obj[Number(k)] = nv;
              else obj[k] = nv;
              onChange(obj, false);
            }
          },
          depth + 1
        );
        row.appendChild(childEditor);

        const nest = document.createElement("button");
        nest.type = "button";
        nest.className = "tree-btn nest";
        nest.textContent = t("treeNest");
        nest.title = t("treeNestHint");
        nest.onclick = () => {
          const cur = isArray ? obj[Number(k)] : obj[k];
          const wrapped = (cur === undefined || cur === null || cur === "")
            ? {}
            : (typeof cur === "object" ? cur : { value: cur });
          if (isArray) {
            const arr = obj.slice();
            arr[Number(k)] = wrapped;
            onChange(arr, true);
          } else {
            const next = Object.assign({}, obj);
            next[k] = wrapped;
            onChange(next, true);
          }
        };
        row.appendChild(nest);

        const rm = document.createElement("button");
        rm.type = "button";
        rm.className = "tree-btn remove";
        rm.textContent = "✕";
        rm.title = t("treeRemove");
        rm.onclick = () => {
          if (isArray) {
            const arr = obj.slice();
            arr.splice(Number(k), 1);
            onChange(arr, true);
          } else {
            const next = Object.assign({}, obj);
            delete next[k];
            onChange(next, true);
          }
        };
        row.appendChild(rm);
        box.appendChild(row);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "tree-btn add";
      add.textContent = isArray ? t("treeAddItem") : t("treeAddField");
      add.onclick = () => {
        if (isArray) {
          onChange(obj.concat([""]), true);
        } else {
          let name = "field";
          let i = 1;
          while (name in obj) { name = `field_${i++}`; }
          const next = Object.assign({}, obj);
          next[name] = "";
          onChange(next, true);
        }
      };
      box.appendChild(add);

      // Bulk add: many comma-separated elements in one go.
      const bulk = document.createElement("div");
      bulk.className = "tree-bulk";
      const bulkInput = document.createElement("input");
      bulkInput.type = "text";
      bulkInput.placeholder = isArray ? t("treeBulkArr") : t("treeBulkObj");
      const bulkBtn = document.createElement("button");
      bulkBtn.type = "button";
      bulkBtn.className = "tree-btn add";
      bulkBtn.textContent = t("treeBulkAdd");
      function commitBulk() {
        const tokens = bulkInput.value
          .split(/[,，]/)
          .map(s => s.trim())
          .filter(s => s !== "");
        if (tokens.length === 0) return;
        if (isArray) {
          onChange(obj.concat(tokens.map(coerceToken)), true);
        } else {
          const next = Object.assign({}, obj);
          tokens.forEach(tok => {
            const eq = tok.indexOf("=");
            if (eq >= 0) {
              const key = tok.slice(0, eq).trim();
              if (key) next[key] = coerceToken(tok.slice(eq + 1));
            } else {
              next[tok] = "";
            }
          });
          onChange(next, true);
        }
        bulkInput.value = "";
      }
      bulkBtn.onclick = commitBulk;
      bulkInput.onkeydown = (e) => {
        if (e.key === "Enter") { e.preventDefault(); commitBulk(); }
      };
      bulk.appendChild(bulkInput);
      bulk.appendChild(bulkBtn);
      box.appendChild(bulk);
      return box;
    }

    // Mount the tree editor into `host`; persist(newRoot) stores each change.
    function renderTreeEditor(host, root, persist) {
      let current = (root && typeof root === "object" && !Array.isArray(root)) ? root : {};

      function apply(next, structural) {
        current = next;
        persist(next);
        if (structural) paint();
      }

      function paint() {
        host.innerHTML = "";
        const box = document.createElement("div");
        box.className = "tree-root";

        const toolbar = document.createElement("div");
        toolbar.className = "tree-toolbar";
        const title = document.createElement("span");
        title.className = "tree-toolbar-title";
        title.textContent = t("treeRoot") + " (object)";
        toolbar.appendChild(title);
        const clearBtn = document.createElement("button");
        clearBtn.type = "button";
        clearBtn.className = "tree-btn remove";
        clearBtn.textContent = t("clearDoc");
        clearBtn.onclick = () => apply({}, true);
        toolbar.appendChild(clearBtn);
        box.appendChild(toolbar);

        box.appendChild(buildContainerEditor(current, apply, 0, false));
        host.appendChild(box);
      }

      paint();
    }

    // Free-form text editor for arbitrary JSON/YAML. persist(parsed) stores it.
    function mountTextEditor(host, value, persist) {
      host.innerHTML = `
        <div class="doc-editor-card">
          <div class="doc-editor-toolbar">
            <span style="font-weight:600; color:var(--text);">${t("docEditor")}</span>
            <div class="doc-editor-toolbar-actions">
              <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" data-act="format">${t("formatDoc")}</button>
              <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" data-act="clear">${t("clearDoc")}</button>
            </div>
          </div>
          <textarea class="doc-editor-textarea" spellcheck="false"></textarea>
        </div>
        <div class="form-hint">${t("textHint")}</div>
        <div class="form-error"></div>
      `;
      const ta = host.querySelector("textarea");
      const err = host.querySelector(".form-error");
      try {
        ta.value = JSON.stringify(value || {}, null, 2);
      } catch (e) {
        ta.value = "{}";
      }

      let timer = null;
      ta.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
          const text = ta.value.trim();
          if (!text) {
            err.textContent = "";
            persist({});
            return;
          }
          try {
            const resp = await fetch("/api/parse", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ content: text })
            });
            const res = await resp.json();
            if (res.context) {
              err.textContent = "";
              persist(res.context);
            } else {
              err.textContent = res.error || t("textParseError");
            }
          } catch (e) {
            err.textContent = String(e);
          }
        }, 200);
      };

      host.querySelector('[data-act="format"]').onclick = () => {
        try {
          ta.value = JSON.stringify(JSON.parse(ta.value), null, 2);
          err.textContent = "";
        } catch (e) {
          err.textContent = t("textParseError");
        }
      };
      host.querySelector('[data-act="clear"]').onclick = () => {
        ta.value = "{}";
        persist({});
      };
    }

    function starterData(provider) {
      if (provider === "custom") {
        return {
          document: {
            app: {
              name: "my-app",
              enabled: true,
              port: 8080,
              tags: ["web", "api"],
              database: { host: "localhost", port: 5432, ssl: false },
              notes: "comma, 逗号, both are kept"
            }
          }
        };
      }
      if (provider === "json") {
        return { document: {} };
      }
      return {};
    }

    async function initApp() {
      try {
        const resp = await fetch("/api/providers");
        const data = await resp.json();
        const select = document.getElementById("providerSelect");
        select.innerHTML = "";
        data.providers.forEach(p => {
          const opt = document.createElement("option");
          opt.value = p;
          opt.textContent = `${t("providerLabel")}${p}`;
          select.appendChild(opt);
        });
        select.value = currentProvider;
      } catch (err) {
        console.error("Failed to load providers:", err);
      }

      await loadSchema(currentProvider);
      restoreDraft();
      if (!formData || Object.keys(formData).length === 0) {
        formData = starterData(currentProvider);
      }
      renderStep();
      triggerLivePreview();
    }

    async function loadSchema(provider) {
      const resp = await fetch(`/api/schema?provider=${provider}`);
      schemaSteps = await resp.json();
      activeStepIdx = 0;
      renderStepper();
    }

    function renderStepper() {
      const nav = document.getElementById("stepperNav");
      nav.innerHTML = "";
      schemaSteps.forEach((step, idx) => {
        const btn = document.createElement("button");
        btn.className = `step-btn ${idx === activeStepIdx ? "active" : ""}`;
        btn.innerHTML = `<span>${idx + 1}.</span> <span>${esc(loc(step, "title"))}</span>`;
        btn.onclick = () => { activeStepIdx = idx; renderStep(); };
        nav.appendChild(btn);
      });
    }

    function renderStep() {
      renderStepper();
      const step = schemaSteps[activeStepIdx];
      if (!step) return;

      document.getElementById("stepTitle").textContent = loc(step, "title");
      document.getElementById("stepDesc").textContent = loc(step, "description") || "";
      document.getElementById("btnPrev").disabled = activeStepIdx === 0;
      document.getElementById("btnNext").textContent = activeStepIdx === schemaSteps.length - 1 ? t("finish") : t("next");

      const fieldsContainer = document.getElementById("stepFields");
      fieldsContainer.innerHTML = "";

      step.fields.forEach(field => {
        const grp = document.createElement("div");
        grp.className = "form-group";
        grp.id = `grp_${field.name.replace(/\\./g, "_")}`;

        const existing = getDotted(formData, field.name, field.default);
        const fid = field.name.replace(/\\./g, "_");

        if (field.type === "boolean") {
          grp.innerHTML = `
            <label class="checkbox-label">
              <input type="checkbox" id="field_${fid}" ${existing ? "checked" : ""}>
              <span>${esc(loc(field, "title"))} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
            </label>
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
          `;
          const input = grp.querySelector("input");
          input.onchange = () => {
            setDotted(formData, field.name, input.checked);
            saveDraft();
            triggerLivePreview();
          };
        } else if (field.choices && field.choices.length > 0) {
          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(loc(field, "title"))} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
            </label>
            <select id="field_${fid}">
              ${field.choices.map(c => `<option value="${esc(c)}" ${c === existing ? "selected" : ""}>${esc(c)}</option>`).join("")}
            </select>
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
            <div class="form-error"></div>
          `;
          const sel = grp.querySelector("select");
          sel.onchange = () => {
            setDotted(formData, field.name, sel.value);
            saveDraft();
            triggerLivePreview();
          };
        } else if (field.type === "tree") {
          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(loc(field, "title"))}</span>
            </label>
            <div class="editor-mode-toggle">
              <button type="button" class="mode-btn active" id="modeTree_${fid}">${t("modeTree")}</button>
              <button type="button" class="mode-btn" id="modeText_${fid}">${t("modeText")}</button>
            </div>
            <div id="treeHost_${fid}"></div>
            <div id="textHost_${fid}" style="display:none;"></div>
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
            <div class="form-error"></div>
          `;
          const treeHost = grp.querySelector(`#treeHost_${fid}`);
          const textHost = grp.querySelector(`#textHost_${fid}`);
          const btnTree = grp.querySelector(`#modeTree_${fid}`);
          const btnText = grp.querySelector(`#modeText_${fid}`);
          let treeData = existing;
          if (!treeData || typeof treeData !== "object") {
            treeData = {};
          }
          const persistTree = (next) => {
            treeData = next;
            setDotted(formData, field.name, next);
            saveDraft();
            triggerLivePreview();
          };
          function showTreeMode() {
            btnTree.className = "mode-btn active";
            btnText.className = "mode-btn";
            treeHost.style.display = "";
            textHost.style.display = "none";
            renderTreeEditor(treeHost, treeData, persistTree);
          }
          function showTextMode() {
            btnTree.className = "mode-btn";
            btnText.className = "mode-btn active";
            treeHost.style.display = "none";
            textHost.style.display = "";
            mountTextEditor(textHost, treeData, persistTree);
          }
          btnTree.onclick = showTreeMode;
          btnText.onclick = showTextMode;
          showTreeMode();
        } else if (field.type === "document" || (currentProvider === "json" && field.name === "document")) {
          let docData = existing;
          if ((!docData || (typeof docData === "object" && Object.keys(docData).length === 0)) && currentProvider === "json") {
            const keys = Object.keys(formData).filter(k => k !== "document");
            if (keys.length > 0) docData = formData;
          }
          if (!docData) {
            docData = {
              app: {
                name: "example-app",
                port: 8080,
                environment: "development"
              }
            };
            if (currentProvider === "json") {
              formData = JSON.parse(JSON.stringify(docData));
              formData.document = JSON.parse(JSON.stringify(docData));
            } else {
              setDotted(formData, field.name, docData);
            }
          }
          let initialText = "";
          try {
            initialText = typeof docData === "string" ? docData : JSON.stringify(docData, null, 2);
          } catch (e) {
            initialText = "{}";
          }

          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(loc(field, "title"))} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
            </label>
            <div class="doc-dropzone" id="dropzone_${fid}">
              <div class="doc-dropzone-icon">📄</div>
              <div class="doc-dropzone-text">${t("uploadOrDrop")}</div>
              <div class="doc-dropzone-sub">${t("dropHint")}</div>
              <input type="file" id="dropInput_${fid}" style="display:none;" accept=".json,.yaml,.yml">
            </div>
            <div class="doc-editor-card">
              <div class="doc-editor-toolbar">
                <span style="font-weight:600; color:var(--text);">${t("docEditor")}</span>
                <div class="doc-editor-toolbar-actions">
                  <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" id="btnDocSample_${fid}">${t("sampleDoc")}</button>
                  <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" id="btnDocFormat_${fid}">${t("formatDoc")}</button>
                  <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" id="btnDocClear_${fid}">${t("clearDoc")}</button>
                </div>
              </div>
              <textarea class="doc-editor-textarea" id="docText_${fid}" spellcheck="false"></textarea>
            </div>
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
            <div class="form-error" id="docErr_${fid}"></div>
          `;

          const dropzone = grp.querySelector(`#dropzone_${fid}`);
          const dropInput = grp.querySelector(`#dropInput_${fid}`);
          const textarea = grp.querySelector(`#docText_${fid}`);
          const docErr = grp.querySelector(`#docErr_${fid}`);
          const btnSample = grp.querySelector(`#btnDocSample_${fid}`);
          const btnFormat = grp.querySelector(`#btnDocFormat_${fid}`);
          const btnClear = grp.querySelector(`#btnDocClear_${fid}`);

          textarea.value = initialText;

          function updateDocContext(parsed) {
            if (currentProvider === "json") {
              formData = parsed;
              formData.document = parsed;
            } else {
              setDotted(formData, field.name, parsed);
            }
            saveDraft();
            triggerLivePreview();
          }

          let docTimer = null;
          function parseAndApply(text) {
            clearTimeout(docTimer);
            docTimer = setTimeout(async () => {
              const trimmed = text.trim();
              if (!trimmed) {
                docErr.textContent = "";
                updateDocContext({});
                return;
              }
              try {
                const resp = await fetch("/api/parse", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ content: trimmed })
                });
                const res = await resp.json();
                if (res.context) {
                  docErr.textContent = "";
                  updateDocContext(res.context);
                } else {
                  docErr.textContent = res.error || "Format parse error";
                }
              } catch (err) {
                docErr.textContent = String(err);
              }
            }, 150);
          }

          textarea.oninput = () => {
            parseAndApply(textarea.value);
          };

          async function handleDocFile(file) {
            if (!file) return;
            try {
              const text = await file.text();
              textarea.value = text;
              const resp = await fetch("/api/parse", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: text })
              });
              const res = await resp.json();
              if (res.context) {
                docErr.textContent = "";
                updateDocContext(res.context);
                showToast(t("uploadOk")(file.name));
              } else {
                docErr.textContent = res.error || "Format parse error";
              }
            } catch (e) {
              docErr.textContent = String(e);
            }
          }

          dropzone.onclick = () => dropInput.click();
          dropInput.onchange = () => {
            if (dropInput.files[0]) handleDocFile(dropInput.files[0]);
          };
          dropzone.ondragover = (e) => {
            e.preventDefault();
            dropzone.classList.add("drag-over");
          };
          dropzone.ondragleave = () => {
            dropzone.classList.remove("drag-over");
          };
          dropzone.ondrop = (e) => {
            e.preventDefault();
            dropzone.classList.remove("drag-over");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
              handleDocFile(e.dataTransfer.files[0]);
            }
          };

          btnSample.onclick = () => {
            const sample = {
              app: {
                name: "checkout-api",
                version: "1.0.0",
                port: 8080,
                environment: "production",
                labels: { tier: "backend", team: "core" }
              }
            };
            textarea.value = JSON.stringify(sample, null, 2);
            parseAndApply(textarea.value);
          };

          btnFormat.onclick = () => {
            try {
              const val = JSON.parse(textarea.value);
              textarea.value = JSON.stringify(val, null, 2);
              docErr.textContent = "";
            } catch (e) {
              showToast("JSON 格式化需要标准 JSON 语法 / Standard JSON required");
            }
          };

          btnClear.onclick = () => {
            textarea.value = "{\\n}";
            parseAndApply(textarea.value);
          };
        } else if (field.type === "mapping") {
          const mapData = existing || {};
          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(loc(field, "title"))} (${t("keyValuePairs")})</span>
              <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" id="btnAddMap_${fid}">${t("add")}</button>
            </label>
            <div class="mapping-table" id="mapTable_${fid}"></div>
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
          `;
          const table = grp.querySelector(`#mapTable_${fid}`);
          const addBtn = grp.querySelector(`#btnAddMap_${fid}`);
          
          function renderMapRows() {
            table.innerHTML = "";
            const keys = Object.keys(mapData);
            if (keys.length === 0) {
              table.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.4rem;">${t("noEntries")}</div>`;
            }
            keys.forEach(k => {
              const row = document.createElement("div");
              row.className = "mapping-row";
              row.innerHTML = `
                <input type="text" placeholder="${t("key")}" value="${esc(k)}" class="map-k">
                <input type="text" placeholder="${t("value")}" value="${esc(mapData[k])}" class="map-v">
                <button type="button" class="mapping-remove">✕</button>
              `;
              const kInput = row.querySelector(".map-k");
              const vInput = row.querySelector(".map-v");
              row.querySelector(".mapping-remove").onclick = () => {
                delete mapData[k];
                setDotted(formData, field.name, mapData);
                renderMapRows();
                triggerLivePreview();
              };
              kInput.onchange = () => {
                const newK = kInput.value.trim();
                const oldV = mapData[k];
                delete mapData[k];
                if (newK) mapData[newK] = oldV;
                setDotted(formData, field.name, mapData);
                renderMapRows();
                triggerLivePreview();
              };
              vInput.oninput = () => {
                mapData[k] = vInput.value.trim();
                setDotted(formData, field.name, mapData);
                triggerLivePreview();
              };
              table.appendChild(row);
            });
          }
          addBtn.onclick = () => {
            const nextKey = `key_${Object.keys(mapData).length + 1}`;
            mapData[nextKey] = "value";
            setDotted(formData, field.name, mapData);
            renderMapRows();
            triggerLivePreview();
          };
          renderMapRows();
        } else {
          // string or integer
          const isNum = field.type === "integer";
          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(loc(field, "title"))} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
              ${field.minimum !== undefined && field.maximum !== undefined ? `<span class="form-hint">[${field.minimum} - ${field.maximum}]</span>` : ""}
            </label>
            <input type="${isNum ? 'number' : 'text'}" id="field_${fid}" 
                   value="${esc(existing !== null && existing !== undefined ? existing : '')}"
                   placeholder="${esc(field.default !== null && field.default !== undefined ? field.default : '')}">
            <div class="form-hint">${esc(loc(field, "description") || "")}</div>
            <div class="form-error"></div>
          `;
          const input = grp.querySelector("input");
          input.oninput = () => {
            let val = input.value;
            if (isNum && val !== "") val = parseInt(val, 10);
            setDotted(formData, field.name, val === "" ? null : val);
            saveDraft();
            triggerLivePreview();
          };
        }
        fieldsContainer.appendChild(grp);
      });
    }

    // Trigger Live Preview & Diagnostics
    function triggerLivePreview() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runPreviewAndValidate, 150);
    }

    async function runPreviewAndValidate() {
      try {
        // Validate
        const valResp = await fetch("/api/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: currentProvider, context: formData })
        });
        const valData = await valResp.json();
        
        // Clear all field errors
        document.querySelectorAll(".form-group").forEach(el => {
          el.classList.remove("has-error");
          const errEl = el.querySelector(".form-error");
          if (errEl) errEl.textContent = "";
        });

        const statusEl = document.getElementById("previewStatus");
        if (valData.valid) {
          statusEl.innerHTML = `<span class="status-ok">●</span> ${t("validConfig")}`;
        } else {
          const count = valData.diagnostics.length;
          statusEl.innerHTML = `<span class="status-err">●</span> ${t("issues")(count)}`;
          valData.diagnostics.forEach(d => {
            const grpId = `grp_${d.field.replace(/\\./g, "_")}`;
            const grp = document.getElementById(grpId);
            if (grp) {
              grp.classList.add("has-error");
              const errEl = grp.querySelector(".form-error");
              if (errEl) errEl.textContent = d.message;
            }
          });
        }

        // Generate Preview
        const genResp = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: currentProvider,
            context: formData,
            format: currentFormat
          })
        });
        const genData = await genResp.json();
        const codeEl = document.getElementById("previewCode");
        if (genData.artifacts && genData.artifacts.length > 0) {
          codeEl.textContent = genData.artifacts[0].content;
        } else if (genData.error) {
          codeEl.textContent = t("validationError") + genData.error;
        }
      } catch (err) {
        console.error("Preview failed:", err);
      }
    }

    function setFormat(fmt) {
      if (fmt === "xml") {
        showToast(t("xmlSoon"));
        return;
      }
      currentFormat = fmt;
      document.getElementById("fmtYaml").className = `format-btn ${fmt === "yaml" ? "active" : ""}`;
      document.getElementById("fmtJson").className = `format-btn ${fmt === "json" ? "active" : ""}`;
      triggerLivePreview();
    }

    // Navigation
    document.getElementById("btnPrev").onclick = () => {
      if (activeStepIdx > 0) {
        activeStepIdx--;
        renderStep();
      }
    };
    document.getElementById("btnNext").onclick = () => {
      if (activeStepIdx < schemaSteps.length - 1) {
        activeStepIdx++;
        renderStep();
      } else {
        showToast(t("allDone"));
      }
    };

    // Keyboard Shortcut (⌘ + Enter)
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        document.getElementById("btnNext").click();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        document.getElementById("btnExport").click();
      }
    });

    // Copy to clipboard
    document.getElementById("btnCopy").onclick = () => {
      const code = document.getElementById("previewCode").textContent;
      navigator.clipboard.writeText(code).then(() => {
        showToast(t("copied"));
      });
    };

    // Clear All
    document.getElementById("btnClearAll").onclick = () => {
      formData = {};
      if (currentProvider === "custom" || currentProvider === "json") {
        formData = { document: {} };
      }
      saveDraft();
      renderStep();
      triggerLivePreview();
      showToast(t("clearAllDone"));
    };

    // Preset
    document.getElementById("btnPreset").onclick = () => {
      if (currentProvider === "json") {
        formData = {
          app: {
            name: "payments-core",
            version: "1.0.0",
            port: 8080,
            environment: "production",
            replicas: 3,
            labels: { team: "payments", tier: "backend" }
          }
        };
        formData.document = JSON.parse(JSON.stringify(formData));
      } else if (currentProvider === "custom") {
        formData = {
          document: {
            app: {
              name: "my-app",
              enabled: true,
              port: 8080,
              tags: ["web", "api"],
              database: { host: "localhost", port: 5432, ssl: false },
              limits: { cpu: "500m", memory: "512Mi" }
            }
          }
        };
      } else if (currentProvider === "env") {
        formData = {
          variables: {
            database: { host: "localhost", port: 5432, name: "app_db" },
            debug: true,
            log_level: "info"
          }
        };
      } else {
        formData = {
          app: {
            name: "payments-core",
            version: "1.0.0",
            port: 8080,
            environment: "production",
            replicas: 3,
            labels: { team: "payments", tier: "backend" },
            health_check: { path: "/healthz", interval_seconds: 15, timeout_seconds: 5 }
          }
        };
      }
      saveDraft();
      renderStep();
      triggerLivePreview();
      showToast(t("presetLoaded"));
    };

    // Export to Disk
    document.getElementById("btnExport").onclick = async () => {
      const targetDir = prompt(t("enterDir"), ".");
      if (targetDir === null) return;
      try {
        const resp = await fetch("/api/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: currentProvider,
            context: formData,
            format: currentFormat,
            output_dir: targetDir
          })
        });
        const res = await resp.json();
        if (res.success) {
          showToast(t("saved")(res.saved.join(", ")));
        } else {
          alert(t("saveFail")(res.error));
        }
      } catch (err) {
        alert(t("exportErr")(err));
      }
    };

    // Upload & Reverse Parse
    const fileInput = document.getElementById("fileInput");
    document.getElementById("btnUploadConfig").onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const resp = await fetch("/api/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text })
        });
        const res = await resp.json();
        if (res.context) {
          formData = res.context;
          saveDraft();
          renderStep();
          triggerLivePreview();
          showToast(t("uploadOk")(file.name));
        } else {
          alert(t("parseFail")(res.error));
        }
      } catch (err) {
        alert(t("uploadErr")(err));
      }
    };

    // LocalStorage Draft
    function saveDraft() {
      try {
        localStorage.setItem(`devconfig_draft_${currentProvider}`, JSON.stringify(formData));
      } catch (e) {}
    }
    function restoreDraft() {
      try {
        const saved = localStorage.getItem(`devconfig_draft_${currentProvider}`);
        if (saved) formData = JSON.parse(saved);
      } catch (e) {}
    }

    // Provider Selector Change
    document.getElementById("providerSelect").onchange = async (e) => {
      currentProvider = e.target.value;
      await loadSchema(currentProvider);
      formData = {};
      restoreDraft();
      if (!formData || Object.keys(formData).length === 0) {
        formData = starterData(currentProvider);
      }
      renderStep();
      triggerLivePreview();
    };

    // ── Language Toggle ───────────────────────────────────
    document.getElementById("btnLang").onclick = () => {
      currentLang = currentLang === "zh" ? "en" : "zh";
      localStorage.setItem("dcg_lang", currentLang);
      applyLang();
      renderStep();
      triggerLivePreview();
    };

    // ── Start App ────────────────────────────────────────
    window.onload = () => { applyLang(); initApp(); };
  </script>
</body>
</html>
"""


class WebUIRequestHandler(BaseHTTPRequestHandler):
    """Serve the single-page studio and a small JSON API over the engine.

    The server is intended for local use only. ``workspace_root`` bounds where
    ``/api/export`` may write, and requests with a non-local ``Host`` header are
    rejected to mitigate DNS-rebinding attacks against the loopback listener.
    """

    registry: ProviderRegistry = default_registry
    workspace_root: Optional[Path] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Keep terminal log clean and minimal
        pass

    def _allowed_host(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):  # IPv6 literal, e.g. [::1]:8848
            host = host[1:].split("]", 1)[0]
        else:
            host = host.split(":", 1)[0]
        return host in ("", "127.0.0.1", "localhost", "::1")

    def _workspace(self) -> Path:
        if self.workspace_root is not None:
            return Path(self.workspace_root).resolve()
        return Path.cwd().resolve()

    def _safe_output_dir(self, requested: str) -> Path:
        root = self._workspace()
        candidate = Path(requested or ".")
        if not candidate.is_absolute():
            candidate = root / candidate
        target = candidate.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"output directory must stay inside the workspace root: {root}")
        return target

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"request body must be UTF-8: {exc}") from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON request body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if not self._allowed_host():
            self._send_json({"error": "forbidden host"}, status=HTTPStatus.FORBIDDEN)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html"):
                self._send_html(_HTML_PAGE)
                return

            if path == "/api/providers":
                self._send_json({"providers": list(self.registry.names())})
                return

            if path == "/api/schema":
                provider_name = query.get("provider", ["custom"])[0]
                steps = describe_provider(provider_name, registry=self.registry)
                self._send_json([s.as_dict() for s in steps])
                return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._send_json(
                {"error": f"internal error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._allowed_host():
            self._send_json({"error": "forbidden host"}, status=HTTPStatus.FORBIDDEN)
            return

        path = urllib.parse.urlparse(self.path).path
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            if path == "/api/validate":
                provider_name = payload.get("provider", "custom")
                context = payload.get("context", {})
                diagnostics = diagnose_request(
                    provider_name, context=context, registry=self.registry
                )
                self._send_json(
                    {
                        "valid": not any(d.severity == "error" for d in diagnostics),
                        "diagnostics": [d.as_dict() for d in diagnostics],
                    }
                )
                return

            if path == "/api/generate":
                provider_name = payload.get("provider", "custom")
                context = payload.get("context", {})
                fmt = payload.get("format", "yaml")
                result = generate(
                    provider_name,
                    GenerationRequest(context=context, options={"format": fmt}),
                    registry=self.registry,
                )
                artifacts_data = []
                for artifact in result.artifacts:
                    content_str = (
                        artifact.content
                        if isinstance(artifact.content, str)
                        else formats.dumps(
                            artifact.content,
                            formats.format_from_media_type(artifact.media_type),
                        )
                    )
                    artifacts_data.append(
                        {
                            "name": artifact.name,
                            "content": content_str,
                            "media_type": artifact.media_type,
                        }
                    )
                self._send_json({"artifacts": artifacts_data})
                return

            if path == "/api/export":
                provider_name = payload.get("provider", "custom")
                context = payload.get("context", {})
                fmt = payload.get("format", "yaml")
                output_dir = self._safe_output_dir(str(payload.get("output_dir", ".")))
                result = generate(
                    provider_name,
                    GenerationRequest(context=context, options={"format": fmt}),
                    registry=self.registry,
                    output_dir=str(output_dir),
                )
                saved = [str(output_dir / artifact.name) for artifact in result.artifacts]
                self._send_json({"success": True, "saved": saved})
                return

            if path == "/api/parse":
                content = payload.get("content", "")
                if not isinstance(content, str):
                    raise ValueError("content must be a string")
                parsed_ctx = formats.loads(content)
                self._send_json({"context": parsed_ctx})
                return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._send_json(
                {"error": f"internal error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND)

def run_web_ui(
    host: str = "127.0.0.1",
    port: int = 8848,
    open_browser: bool = True,
    registry: Optional[ProviderRegistry] = None,
    workspace_root: Optional[str] = None,
) -> None:
    """Start the local WebUI HTTP server and open a browser.

    ``workspace_root`` bounds the directories ``/api/export`` may write to; it
    defaults to the current working directory.
    """

    reg = registry or default_registry
    root = Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()

    class CustomHandler(WebUIRequestHandler):
        pass

    CustomHandler.registry = reg
    CustomHandler.workspace_root = root

    server = ThreadingHTTPServer((host, port), CustomHandler)
    url = f"http://{host}:{port}"

    print("=================================================================")
    print("  DevConfig-Gen Studio (本地配置工作台)                            ")
    print(f"  本地运行地址: {url}")
    print(f"  导出工作空间: {root}")
    print("  按 Ctrl+C 停止服务")
    print("=================================================================")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio server stopped. / 服务已停止。")
    finally:
        server.server_close()
