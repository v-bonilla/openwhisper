from __future__ import annotations

from pathlib import Path

from ..constants import BACKEND_PARAKEET, BACKEND_WHISPER, SUPPORTED_BACKENDS
from ..parakeet import ParakeetError, run_parakeet
from ..whisper import WhisperError, run_whisper


class TranscribeError(RuntimeError):
    pass


def transcribe_audio(
    audio_path: Path,
    backend: str,
    config: dict,
    language: str | None = "en",
) -> tuple[str, str | None]:
    if backend not in SUPPORTED_BACKENDS:
        raise TranscribeError(f"Unsupported backend: {backend}")

    from ..cli import validate_backend_requirements

    try:
        validate_backend_requirements(backend, config)
    except ValueError as exc:
        raise TranscribeError(str(exc)) from exc

    if backend == BACKEND_PARAKEET:
        try:
            return run_parakeet(
                audio_path,
                config.get("parakeet_model_dir"),
                language,
                int(config.get("parakeet_num_threads", 4)),
            )
        except ParakeetError as exc:
            raise TranscribeError(str(exc)) from exc

    if backend == BACKEND_WHISPER:
        try:
            return run_whisper(
                audio_path,
                config.get("whisper_model_path"),
                language,
                config.get("whisper_cli_path", "whisper-cli"),
            )
        except WhisperError as exc:
            raise TranscribeError(str(exc)) from exc

    raise TranscribeError(f"Unsupported backend: {backend}")
