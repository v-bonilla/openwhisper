from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openwhisper.config import load_config  # noqa: E402

AUDIO_PRIMARY = ["pw-record"]
AUDIO_FALLBACK = ["parec"]
AUDIO_CONVERTERS = ["sox", "ffmpeg"]
CLIPBOARD = ["dbus-send"]


def _missing(cmds: list[str]) -> list[str]:
    return [cmd for cmd in cmds if shutil.which(cmd) is None]


def _is_path_like(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith((".bin", ".gguf", ".ggml"))


def _check_binary(value: str | None, label: str) -> str | None:
    """Return a missing-dep string, or None if found.

    If `value` looks like a filesystem path (as configured via config),
    check the file exists. Otherwise fall back to PATH lookup.
    """
    if not value:
        return f"{label} (not configured)"
    if _is_path_like(value):
        if not Path(value).exists():
            return f"{label} at {value} (path does not exist)"
        return None
    if shutil.which(value) is None:
        return f"{value} (not on PATH)"
    return None


def _check_sherpa_onnx() -> str | None:
    try:
        import sherpa_onnx  # noqa: F401
    except ImportError:
        return "sherpa-onnx (pip install: uv sync --extra parakeet)"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check openwhisper dependencies.")
    parser.add_argument(
        "--backend",
        choices=["whisper", "parakeet"],
        default="whisper",
        help="Transcription backend to verify (default: whisper).",
    )
    args = parser.parse_args()

    config = load_config()

    missing: list[str] = []
    if args.backend == "parakeet":
        problem = _check_sherpa_onnx()
        if problem:
            missing.append(problem)
    else:
        problem = _check_binary(config.get("whisper_cli_path"), "whisper_cli_path")
        if problem:
            missing.append(problem)

    problem = _check_binary(config.get("llama_cli_path"), "llama_cli_path")
    if problem:
        missing.append(problem)

    if _missing(AUDIO_PRIMARY) and _missing(AUDIO_FALLBACK):
        missing.append("pw-record or parec")
    if not _missing(AUDIO_FALLBACK) and _missing(AUDIO_CONVERTERS):
        missing.append("sox or ffmpeg (required for parec)")

    if _missing(CLIPBOARD):
        missing.append("dbus-send")

    if missing:
        print(f"Missing dependencies for backend '{args.backend}':")
        for item in missing:
            print(f"- {item}")
        return 1

    print(f"All required dependencies for backend '{args.backend}' appear to be installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
