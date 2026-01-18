from __future__ import annotations

from pathlib import Path
import json

from .config import REPO_ROOT

STATE_DIR = REPO_ROOT / "data" / "tmp"
STATE_PATH = STATE_DIR / "recording_state.json"


class StateError(RuntimeError):
    pass


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if not STATE_PATH.exists():
        raise StateError("No active recording state found.")
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state: dict) -> None:
    ensure_state_dir()
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def clear_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
