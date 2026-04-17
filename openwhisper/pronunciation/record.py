from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from ..audio import AudioError, start_recording, stop_recording
from ..config import REPO_ROOT


class RecordError(RuntimeError):
    pass


def _make_audio_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return REPO_ROOT / "data" / "tmp" / f"pronunciation-{timestamp}.wav"


def record_until_enter(
    *,
    before_prompt: str | None = None,
    stop_prompt: str = "Recording... press Enter when done.",
    device: str | None = None,
) -> Path:
    """Record until the user presses Enter. Returns the WAV path.

    Requires a TTY on stdin; callers handle non-TTY cases via --audio-file.
    """
    if not sys.stdin.isatty():
        raise RecordError(
            "Recording requires a TTY; use --audio-file for non-interactive runs."
        )

    if before_prompt:
        print(before_prompt, flush=True)

    audio_path = _make_audio_path()
    try:
        recording = start_recording(audio_path, device)
    except AudioError as exc:
        raise RecordError(str(exc)) from exc

    print(stop_prompt, flush=True)
    try:
        input()
    finally:
        stop_recording(recording.pids)

    return audio_path
