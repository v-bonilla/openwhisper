from __future__ import annotations

import argparse
import shutil

WHISPER_REQUIRED = ["whisper-cli"]
LLAMA_REQUIRED = ["llama-cli"]
AUDIO_PRIMARY = ["pw-record"]
AUDIO_FALLBACK = ["parec"]
AUDIO_CONVERTERS = ["sox", "ffmpeg"]
CLIPBOARD = ["dbus-send"]


def _missing(cmds: list[str]) -> list[str]:
    return [cmd for cmd in cmds if shutil.which(cmd) is None]


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

    missing: list[str] = []
    if args.backend == "parakeet":
        problem = _check_sherpa_onnx()
        if problem:
            missing.append(problem)
    else:
        missing.extend(_missing(WHISPER_REQUIRED))

    missing.extend(_missing(LLAMA_REQUIRED))

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
