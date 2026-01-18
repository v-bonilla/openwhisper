from __future__ import annotations

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
    try:
        result = subprocess.run(cmd, input=prompt, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise LlamaError("llama-cli is not available on PATH.") from exc
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        raise LlamaError(f"llama-cli failed: {combined.strip()}")
    output = result.stdout.strip()
    if not output:
        raise LlamaError("llama-cli returned empty output.")
    return output
