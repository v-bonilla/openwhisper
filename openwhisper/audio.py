from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import which

from .config import REPO_ROOT

AUDIO_DIR = REPO_ROOT / "data" / "tmp"


class AudioError(RuntimeError):
    pass


@dataclass
class RecordingProcess:
    pids: list[int]
    method: str


def _ensure_audio_dir() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _pw_record_command(path: Path, device: str | None) -> list[str]:
    cmd = [
        "pw-record",
        "--rate",
        "16000",
        "--channels",
        "1",
        "--format",
        "s16",
        str(path),
    ]
    if device:
        cmd.extend(["--target", device])
    return cmd


def _parec_sox_commands(path: Path) -> tuple[list[str], list[str]]:
    parec_cmd = ["parec"]
    sox_cmd = [
        "sox",
        "-t",
        "raw",
        "-r",
        "16000",
        "-e",
        "signed",
        "-b",
        "16",
        "-c",
        "1",
        "-",
        "-t",
        "wav",
        str(path),
    ]
    return parec_cmd, sox_cmd


def _parec_ffmpeg_commands(path: Path) -> tuple[list[str], list[str]]:
    parec_cmd = ["parec"]
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-i",
        "-",
        "-y",
        str(path),
    ]
    return parec_cmd, ffmpeg_cmd


def start_recording(path: Path, device: str | None) -> RecordingProcess:
    _ensure_audio_dir()
    if which("pw-record"):
        cmd = _pw_record_command(path, device)
        proc = subprocess.Popen(cmd, start_new_session=True)
        return RecordingProcess(pids=[proc.pid], method="pw-record")

    if which("parec"):
        if which("sox"):
            parec_cmd, sox_cmd = _parec_sox_commands(path)
        elif which("ffmpeg"):
            parec_cmd, sox_cmd = _parec_ffmpeg_commands(path)
        else:
            raise AudioError("parec is available but sox/ffmpeg is missing.")

        parec_proc = subprocess.Popen(
            parec_cmd,
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        sox_proc = subprocess.Popen(
            sox_cmd,
            stdin=parec_proc.stdout,
            start_new_session=True,
        )
        if parec_proc.stdout:
            parec_proc.stdout.close()
        return RecordingProcess(pids=[parec_proc.pid, sox_proc.pid], method="parec")

    raise AudioError("Missing audio capture tools: pw-record or parec.")


def start_raw_pcm_capture(device: str | None) -> subprocess.Popen:
    """Spawn an audio capture producing raw s16le 16kHz mono on stdout.

    Returns the Popen handle. Caller owns lifecycle and is responsible for
    terminating the process group (use ``os.killpg`` with ``proc.pid``).
    """
    _ensure_audio_dir()
    if which("pw-record"):
        cmd = [
            "pw-record",
            "--rate", "16000",
            "--channels", "1",
            "--format", "s16",
            "--raw",
            "-",
        ]
        if device:
            cmd.extend(["--target", device])
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    if which("parec"):
        cmd = [
            "parec",
            "--rate=16000",
            "--channels=1",
            "--format=s16le",
            "--raw",
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    raise AudioError("Missing audio capture tools: pw-record or parec.")


def stop_recording(pids: list[int]) -> None:
    for pid in pids:
        try:
            os.killpg(pid, signal.SIGINT)
        except ProcessLookupError:
            continue
    time.sleep(0.3)
    for pid in pids:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
