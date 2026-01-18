from __future__ import annotations

import os
from pathlib import Path
import subprocess


class LlamaError(RuntimeError):
    pass


def run_llama(prompt: str, model_path: str, cli_path: str = "llama-cli") -> str:
    cmd = [
        cli_path,
        "-m",
        model_path,
        "--temp",
        "0.2",
        "--top-p",
        "0.9",
    ]
    env = None
    cli_dir = Path(cli_path).parent if Path(cli_path).is_absolute() else None
    if cli_dir and cli_dir != Path("."):
        env = os.environ.copy()
        current = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{cli_dir}{os.pathsep}{current}" if current else str(cli_dir)
    try:
        result = subprocess.run(cmd, input=prompt, text=True, capture_output=True, env=env)
    except FileNotFoundError as exc:
        raise LlamaError("llama-cli is not available on PATH.") from exc
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        raise LlamaError(f"llama-cli failed: {combined.strip()}")
    output = result.stdout.strip()
    if not output:
        raise LlamaError("llama-cli returned empty output.")
    return output
