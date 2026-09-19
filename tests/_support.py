"""Shared helpers for subprocess-based CLI tests."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"


def run_cli(*args):
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "devconfig_gen.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
