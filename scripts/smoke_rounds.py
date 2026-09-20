#!/usr/bin/env python3
"""Repeatable smoke harness for DevConfig-Gen_SingBox.

Each round verifies three independent things:

  1. the full unittest suite (fresh interpreter);
  2. end-to-end business parity across the Python API, the CLI, and the WebUI
     HTTP API for every built-in provider x format (byte-for-byte);
  3. the embedded WebUI JavaScript executes under a DOM stub (node), including
     the widget registry and the default widgets.

Usage:
    python3 scripts/smoke_rounds.py [rounds]   # default: 8

Exit code is 0 only if every round passes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(SRC))

from devconfig_gen import generate, load_file  # noqa: E402
from devconfig_gen.models import GenerationRequest  # noqa: E402
from devconfig_gen.web_ui import WebUIRequestHandler, _HTML_PAGE  # noqa: E402

CASES = [
    ("custom", EXAMPLES / "custom.yaml"),
    ("json", EXAMPLES / "custom.json"),
    ("env", EXAMPLES / "vars.yaml"),
]
SINGBOX_EXAMPLE = EXAMPLES / "singbox.yaml"
FORMATS = ["yaml", "json"]

DOM_STUB = r"""
function el(tag) {
  const e = {
    tagName: tag || "div", className: "", id: "", style: {}, value: "",
    checked: false, files: [], children: [], _innerHTML: "", textContent: "",
    placeholder: "", title: "", type: "",
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    appendChild(c){ this.children.push(c); return c; },
    removeChild(){}, querySelector(){ return el("div"); }, querySelectorAll(){ return []; },
    addEventListener(){}, click(){}, setAttribute(){}, getAttribute(){ return null; }, focus(){},
  };
  Object.defineProperty(e, "innerHTML", { get(){ return this._innerHTML; }, set(v){ this._innerHTML = String(v); } });
  return e;
}
global.document = {
  getElementById(){ return el("div"); }, createElement(t){ return el(t); },
  querySelectorAll(){ return []; }, querySelector(){ return el("div"); },
  documentElement: el("html"), title: "", body: el("body"),
};
global.window = { addEventListener(){} };
global.localStorage = { getItem(){ return null; }, setItem(){}, removeItem(){} };
global.navigator = { clipboard: { writeText(){ return Promise.resolve(); } } };
global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
global.prompt = () => null;
global.alert = () => {};
"""

FRONTEND_CHECK = r"""
;(function () {
  const types = WidgetRegistry.types().sort();
  const expected = ["boolean","document","integer","mapping","string","tree"];
  if (JSON.stringify(types) !== JSON.stringify(expected)) { console.error("REGISTRY MISMATCH", types); process.exit(2); }
  const fields = [
    {name:"a.string", type:"string", default:"x", description:"", required:false},
    {name:"a.integer", type:"integer", default:1, description:"", required:false},
    {name:"a.boolean", type:"boolean", default:false, description:"", required:false},
    {name:"a.mapping", type:"mapping", default:{}, description:"", required:false},
    {name:"a.document", type:"document", default:{}, description:"", required:false},
    {name:"a.tree", type:"tree", default:{}, description:"", required:false},
    {name:"a.choice", type:"string", choices:["x","y"], default:"x", description:"", required:false},
  ];
  fields.forEach(f => {
    const grp = document.createElement("div");
    const ctx = makeFieldContext(f, grp);
    const factory = resolveWidget(f);
    if (typeof factory !== "function") { console.error("no widget for", f.type); process.exit(3); }
    factory(ctx);
    if (!grp.innerHTML) { console.error("empty render for", f.name); process.exit(5); }
  });
  const fn = (new Function('"use strict"; return (' + "(ctx) => document.createElement('div')" + ');'))();
  WidgetRegistry.register("node-editor", fn);
  if (!WidgetRegistry.has("node-editor")) { console.error("inject failed"); process.exit(4); }
  console.log("FRONTEND OK");
})();
"""


def run_suite() -> tuple[bool, int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    out = proc.stderr + proc.stdout
    m = re.search(r"Ran (\d+) tests", out)
    return proc.returncode == 0, (int(m.group(1)) if m else -1), out


def _dumps(data, fmt):
    from devconfig_gen import formats
    return formats.dumps(data, fmt)


def api_artifact(provider, context, fmt):
    result = generate(provider, GenerationRequest(context=context, options={"format": fmt}))
    art = result.artifacts[0]
    return art.content if isinstance(art.content, str) else _dumps(art.content, fmt)


def cli_artifact(provider, path, fmt, workdir):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    outdir = Path(workdir) / f"{provider}_{fmt}"
    proc = subprocess.run(
        [sys.executable, "-m", "devconfig_gen.cli", "generate",
         "--provider", provider, "--input", str(path),
         "--output-dir", str(outdir), "--format", fmt],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"CLI failed for {provider}/{fmt}: {proc.stderr}")
    files = sorted(p for p in outdir.iterdir() if p.is_file())
    return files[0].read_text(encoding="utf-8")


class _Handler(WebUIRequestHandler):
    workspace_root = ROOT


def webui_artifact(port, provider, context, fmt):
    payload = json.dumps({"provider": provider, "context": context, "format": fmt}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["artifacts"][0]["content"]


def webui_artifacts(port, provider, context, fmt):
    payload = json.dumps({"provider": provider, "context": context, "format": fmt}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        artifacts = json.loads(resp.read().decode("utf-8"))["artifacts"]
    return {item["name"]: item["content"] for item in artifacts}


def singbox_parity(port, work):
    """Multi-artifact parity for the sing-box provider (API == CLI == WebUI)."""

    context = load_file(SINGBOX_EXAMPLE)
    checks = []
    for fmt in FORMATS:
        result = generate("singbox", GenerationRequest(context=context, options={"format": fmt}))
        api = {
            artifact.name: (
                artifact.content if isinstance(artifact.content, str) else _dumps(artifact.content, fmt)
            )
            for artifact in result.artifacts
        }
        cli_dir = Path(work) / f"singbox_{fmt}"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        proc = subprocess.run(
            [sys.executable, "-m", "devconfig_gen.cli", "generate",
             "--provider", "singbox", "--input", str(SINGBOX_EXAMPLE),
             "--output-dir", str(cli_dir), "--format", fmt],
            capture_output=True, text=True, cwd=str(ROOT), env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"CLI failed for singbox/{fmt}: {proc.stderr}")
        cli = {path.name: path.read_text(encoding="utf-8") for path in cli_dir.iterdir()}
        web = webui_artifacts(port, "singbox", context, fmt)
        checks.append((f"singbox/{fmt}", api == cli == web))
    return checks


def parity_round():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks = []
    try:
        with tempfile.TemporaryDirectory() as work:
            for provider, path in CASES:
                context = load_file(path)
                for fmt in FORMATS:
                    api = api_artifact(provider, context, fmt)
                    cli = cli_artifact(provider, path, fmt, work)
                    web = webui_artifact(server.server_port, provider, context, fmt)
                    checks.append((f"{provider}/{fmt}", api == cli == web))
            checks.extend(singbox_parity(server.server_port, work))
    finally:
        server.shutdown()
        server.server_close()
    return checks


def frontend_smoke():
    if shutil.which("node") is None:
        return True, "node not found (skipped)"
    js = re.search(r"<script>(.*?)</script>", _HTML_PAGE, re.S).group(1)
    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp) / "frontend_smoke.js"
        harness.write_text(DOM_STUB + "\n" + js + "\n" + FRONTEND_CHECK, encoding="utf-8")
        proc = subprocess.run(["node", str(harness)], capture_output=True, text=True)
    return proc.returncode == 0 and "FRONTEND OK" in proc.stdout, proc.stdout + proc.stderr


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    all_ok = True
    for r in range(1, rounds + 1):
        suite_ok, count, out = run_suite()
        try:
            checks = parity_round()
            parity_ok = all(name_ok[1] for name_ok in checks)
        except Exception as exc:  # noqa: BLE001
            checks, parity_ok = [], False
            print(f"round {r}: parity error: {exc}")
        front_ok, front_out = frontend_smoke()
        status = "OK" if (suite_ok and parity_ok and front_ok) else "FAIL"
        all_ok = all_ok and suite_ok and parity_ok and front_ok
        detail = " ".join(f"{name}{'' if ok else '!'}" for name, ok in checks)
        print(f"round {r}: {status}  suite={count}  parity=[{detail}]  frontend={'OK' if front_ok else 'FAIL'}")
        if not suite_ok:
            print(out)
        if not front_ok:
            print(front_out)
    print("=" * 60)
    print("SMOKE", "PASS" if all_ok else "FAIL", f"({rounds} rounds)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
