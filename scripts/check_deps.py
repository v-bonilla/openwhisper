from __future__ import annotations

import shutil
import sys

REQUIRED = ["whisper-cli", "llama-cli"]
AUDIO_PRIMARY = ["pw-record"]
AUDIO_FALLBACK = ["parec"]
AUDIO_CONVERTERS = ["sox", "ffmpeg"]
CLIPBOARD = ["wl-copy", "xclip"]


def _missing(cmds: list[str]) -> list[str]:
    return [cmd for cmd in cmds if shutil.which(cmd) is None]


def main() -> int:
    missing = []
    missing.extend(_missing(REQUIRED))

    if _missing(AUDIO_PRIMARY) and _missing(AUDIO_FALLBACK):
        missing.append("pw-record or parec")
    if not _missing(AUDIO_FALLBACK) and _missing(AUDIO_CONVERTERS):
        missing.append("sox or ffmpeg (required for parec)")

    if len(_missing(CLIPBOARD)) == len(CLIPBOARD):
        missing.append("wl-copy or xclip")

    if missing:
        print("Missing dependencies:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("All required dependencies appear to be installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
