from __future__ import annotations

from pathlib import Path
import re
import subprocess

from .constants import SUPPORTED_LANGUAGES


class WhisperError(RuntimeError):
    pass


def _parse_detected_language(output: str) -> str | None:
    match = re.search(r"Detected language:\s*([a-z]{2})", output, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def run_whisper(
    audio_path: Path,
    model_path: str,
    language: str | None,
    cli_path: str = "whisper-cli",
) -> tuple[str, str | None]:
    output_prefix = audio_path.with_suffix("")
    cmd = [
        cli_path,
        "-m",
        model_path,
        "-f",
        str(audio_path),
        "-otxt",
        "-of",
        str(output_prefix),
        "-nt",
    ]
    if language:
        cmd.extend(["-l", language])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise WhisperError("whisper-cli is not available on PATH.") from exc
    combined = (result.stdout or "") + (result.stderr or "")
    detected = _parse_detected_language(combined)

    if result.returncode != 0:
        raise WhisperError(f"whisper-cli failed: {combined.strip()}")

    txt_path = output_prefix.with_suffix(".txt")
    if not txt_path.exists():
        raise WhisperError("whisper-cli did not produce output text.")

    transcript = txt_path.read_text(encoding="utf-8").strip()
    try:
        txt_path.unlink()
    except OSError:
        pass
    if not transcript:
        raise WhisperError("whisper-cli returned empty transcript.")

    if language is None:
        if detected is None:
            raise WhisperError("Unable to detect language; use --language.")
        if detected not in SUPPORTED_LANGUAGES:
            raise WhisperError(f"Detected language '{detected}' is not supported.")

    return transcript, detected
