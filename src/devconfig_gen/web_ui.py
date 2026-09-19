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
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevConfig-Gen — Configuration Studio</title>
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
    }
    .format-btn.active {
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
      <span class="brand-tag">Studio</span>
    </div>
    <div class="header-controls">
      <select id="providerSelect" style="width: auto; padding: 0.4rem 0.8rem;">
        <option value="service">Provider: service</option>
      </select>
      <button class="btn btn-secondary" id="btnUploadConfig">⬆️ Import File</button>
      <input type="file" id="fileInput" style="display: none;" accept=".json,.yaml,.yml">
      <button class="btn btn-secondary" id="btnPreset">✨ Load Preset</button>
      <button class="btn btn-primary" id="btnExport">💾 Save to Disk</button>
    </div>
  </header>

  <div class="container">
    <div class="wizard-panel">
      <div class="stepper-nav" id="stepperNav"></div>
      
      <div class="card" id="stepCard">
        <h2 class="card-title" id="stepTitle">Step Title</h2>
        <p class="card-desc" id="stepDesc">Step description goes here.</p>
        
        <div id="stepFields"></div>

        <div class="wizard-actions">
          <button class="btn btn-secondary" id="btnPrev" disabled>← Previous</button>
          <div style="font-size: 0.8rem; color: var(--text-muted); align-self: center;">
            Shortcut: <kbd>⌘</kbd> + <kbd>Enter</kbd>
          </div>
          <button class="btn btn-primary" id="btnNext">Next →</button>
        </div>
      </div>
    </div>

    <div class="preview-panel">
      <div class="preview-header">
        <span class="preview-title">Live Generated Configuration</span>
        <div class="preview-toolbar">
          <div class="format-toggle">
            <button class="format-btn active" id="fmtYaml" onclick="setFormat('yaml')">YAML</button>
            <button class="format-btn" id="fmtJson" onclick="setFormat('json')">JSON</button>
          </div>
          <button class="btn btn-secondary" id="btnCopy" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;">📋 Copy</button>
        </div>
      </div>
      <div class="preview-body" id="previewCode"># Generating preview...</div>
      <div class="preview-status" id="previewStatus">
        <span class="status-ok">●</span> Valid configuration
      </div>
    </div>
  </div>

  <div class="toast" id="toast">Notice message</div>

  <script>
    let currentProvider = "service";
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

    // Fetch Providers & Schema
    async function initApp() {
      try {
        const resp = await fetch("/api/providers");
        const data = await resp.json();
        const select = document.getElementById("providerSelect");
        select.innerHTML = "";
        data.providers.forEach(p => {
          const opt = document.createElement("option");
          opt.value = p;
          opt.textContent = `Provider: ${p}`;
          select.appendChild(opt);
        });
        select.value = currentProvider;
      } catch (err) {
        console.error("Failed to load providers:", err);
      }

      await loadSchema(currentProvider);
      restoreDraft();
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
        btn.innerHTML = `<span>${idx + 1}.</span> <span>${step.title}</span>`;
        btn.onclick = () => { activeStepIdx = idx; renderStep(); };
        nav.appendChild(btn);
      });
    }

    function renderStep() {
      renderStepper();
      const step = schemaSteps[activeStepIdx];
      if (!step) return;

      document.getElementById("stepTitle").textContent = step.title;
      document.getElementById("stepDesc").textContent = step.description || "";
      document.getElementById("btnPrev").disabled = activeStepIdx === 0;
      document.getElementById("btnNext").textContent = activeStepIdx === schemaSteps.length - 1 ? "Finish ✓" : "Next →";

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
              <span>${esc(field.name)} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
            </label>
            <div class="form-hint">${esc(field.description || "")}</div>
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
              <span>${esc(field.name)} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
            </label>
            <select id="field_${fid}">
              ${field.choices.map(c => `<option value="${esc(c)}" ${c === existing ? "selected" : ""}>${esc(c)}</option>`).join("")}
            </select>
            <div class="form-hint">${esc(field.description || "")}</div>
            <div class="form-error"></div>
          `;
          const sel = grp.querySelector("select");
          sel.onchange = () => {
            setDotted(formData, field.name, sel.value);
            saveDraft();
            triggerLivePreview();
          };
        } else if (field.type === "mapping") {
          const mapData = existing || {};
          grp.innerHTML = `
            <label class="form-label">
              <span>${esc(field.name)} (Key-Value pairs)</span>
              <button type="button" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" id="btnAddMap_${fid}">+ Add</button>
            </label>
            <div class="mapping-table" id="mapTable_${fid}"></div>
            <div class="form-hint">${esc(field.description || "")}</div>
          `;
          const table = grp.querySelector(`#mapTable_${fid}`);
          const addBtn = grp.querySelector(`#btnAddMap_${fid}`);
          
          function renderMapRows() {
            table.innerHTML = "";
            const keys = Object.keys(mapData);
            if (keys.length === 0) {
              table.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.4rem;">No entries defined</div>`;
            }
            keys.forEach(k => {
              const row = document.createElement("div");
              row.className = "mapping-row";
              row.innerHTML = `
                <input type="text" placeholder="Key" value="${esc(k)}" class="map-k">
                <input type="text" placeholder="Value" value="${esc(mapData[k])}" class="map-v">
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
              <span>${esc(field.name)} ${field.required ? '<span style="color:var(--danger)">*</span>' : ''}</span>
              ${field.minimum !== undefined && field.maximum !== undefined ? `<span class="form-hint">[${field.minimum} - ${field.maximum}]</span>` : ""}
            </label>
            <input type="${isNum ? 'number' : 'text'}" id="field_${fid}" 
                   value="${esc(existing !== null && existing !== undefined ? existing : '')}"
                   placeholder="${esc(field.default !== null && field.default !== undefined ? field.default : '')}">
            <div class="form-hint">${esc(field.description || "")}</div>
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
          statusEl.innerHTML = `<span class="status-ok">●</span> Valid configuration`;
        } else {
          const count = valData.diagnostics.length;
          statusEl.innerHTML = `<span class="status-err">●</span> ${count} validation ${count === 1 ? 'issue' : 'issues'}`;
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
          codeEl.textContent = `# Validation Error:\\n# ${genData.error}`;
        }
      } catch (err) {
        console.error("Preview failed:", err);
      }
    }

    function setFormat(fmt) {
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
        showToast("✓ All steps completed! Ready to save or copy.");
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
        showToast("📋 Copied configuration to clipboard!");
      });
    };

    // Preset
    document.getElementById("btnPreset").onclick = () => {
      formData = {
        service: {
          name: "payments-core",
          version: "1.0.0",
          port: 8080,
          environment: "production",
          replicas: 3,
          labels: { team: "payments", tier: "backend" },
          health_check: { path: "/healthz", interval_seconds: 15, timeout_seconds: 5 }
        }
      };
      saveDraft();
      renderStep();
      triggerLivePreview();
      showToast("✨ Loaded production service preset!");
    };

    // Export to Disk
    document.getElementById("btnExport").onclick = async () => {
      const targetDir = prompt("Enter target directory to save configuration:", ".");
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
          showToast(`💾 Saved: ${res.saved.join(", ")}`);
        } else {
          alert(`Save failed: ${res.error}`);
        }
      } catch (err) {
        alert(`Export error: ${err}`);
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
          showToast(`⬆️ Successfully backfilled from ${file.name}!`);
        } else {
          alert(`Parse failed: ${res.error}`);
        }
      } catch (err) {
        alert(`Upload failed: ${err}`);
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
      renderStep();
      triggerLivePreview();
    };

    // Start App
    window.onload = initApp;
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
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
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
                provider_name = query.get("provider", ["service"])[0]
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
                provider_name = payload.get("provider", "service")
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
                provider_name = payload.get("provider", "service")
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
                provider_name = payload.get("provider", "service")
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
    print("  DevConfig-Gen Studio (local configuration studio)              ")
    print(f"  Running locally at: {url}")
    print(f"  Export workspace root: {root}")
    print("  Press Ctrl+C to terminate.")
    print("=================================================================")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio server stopped.")
    finally:
        server.server_close()
