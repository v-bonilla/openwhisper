from __future__ import annotations

from pathlib import Path
import tomllib

from .constants import (
    BACKEND_WHISPER,
    DEFAULT_LLAMA_MODEL,
    DEFAULT_PARAKEET_MODEL_DIR,
    DEFAULT_WHISPER_MODEL,
    MODE_VOICE,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "openwhisper.toml"


class ConfigError(RuntimeError):
    pass


def load_config() -> dict:
    config = {
        "transcription_backend": BACKEND_WHISPER,
        "whisper_cli_path": "whisper-cli",
        "whisper_model_path": DEFAULT_WHISPER_MODEL,
        "parakeet_model_dir": DEFAULT_PARAKEET_MODEL_DIR,
        "parakeet_num_threads": 4,
        "llama_cli_path": "llama-cli",
        "llama_model_path": DEFAULT_LLAMA_MODEL,
        "default_mode": MODE_VOICE,
        "default_language": None,
        "clipboard_enabled": True,
        "clipboard_notify_enabled": True,
        "history_enabled": True,
        "history_dir": str(REPO_ROOT / "data" / "history"),
        "audio_device": None,
        "translation_target": None,
        "pronunciation_pairs_path": str(
            REPO_ROOT / "data" / "pronunciation" / "minimal_pairs.json"
        ),
        "pronunciation_paragraphs_dir": str(
            REPO_ROOT / "data" / "pronunciation" / "paragraphs"
        ),
    }
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as handle:
            parsed = tomllib.load(handle)
        config.update(parsed)
    return config


def resolve_history_dir(config: dict) -> Path:
    history_dir = Path(config.get("history_dir") or "")
    if not history_dir.is_absolute():
        history_dir = (REPO_ROOT / history_dir).resolve()
    return history_dir
