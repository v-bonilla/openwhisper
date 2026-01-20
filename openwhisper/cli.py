from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from .audio import AudioError, start_recording, stop_recording
from .config import REPO_ROOT, load_config, resolve_history_dir
from .constants import (
    MODE_EMAIL,
    MODE_NOTE,
    MODE_VOICE,
    PROMPT_EMAIL,
    PROMPT_NOTE,
    PROMPT_TRANSLATION,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
)
from .history import write_history
from .llama import LlamaError, run_llama
from .output import OutputError, copy_to_clipboard, notify_clipboard_copied, write_output
from .state import StateError, clear_state, load_state, save_state
from .whisper import WhisperError, run_whisper


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="openwhisper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES))
    start_parser.add_argument("--language", choices=sorted(SUPPORTED_LANGUAGES))
    start_parser.add_argument("--translate", choices=sorted(SUPPORTED_LANGUAGES))
    start_parser.add_argument("--no-clipboard", action="store_true")
    start_parser.add_argument("--no-history", action="store_true")
    start_parser.add_argument("--output", type=Path)

    subparsers.add_parser("stop")
    subparsers.add_parser("cancel")

    return parser.parse_args()


def _is_path_like(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith((".bin", ".gguf", ".ggml"))


def _validate_model_path(value: str | None, label: str) -> None:
    if not value:
        raise ValueError(f"{label} is not set.")
    if _is_path_like(value) and not Path(value).exists():
        raise ValueError(f"{label} path not found: {value}")


def _validate_binary_path(value: str | None, label: str) -> None:
    if not value:
        raise ValueError(f"{label} is not set.")
    if _is_path_like(value):
        if not Path(value).exists():
            raise ValueError(f"{label} path not found: {value}")
    else:
        from shutil import which

        if which(value) is None:
            raise ValueError(f"{label} not found on PATH: {value}")


def _validate_language_pair(language: str | None, translate: str | None) -> None:
    if language and language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    if translate and translate not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported translation target: {translate}")


def _format_prompt(mode: str, transcript: str) -> str:
    if mode == MODE_EMAIL:
        return PROMPT_EMAIL.format(TRANSCRIPT=transcript)
    if mode == MODE_NOTE:
        return PROMPT_NOTE.format(TRANSCRIPT=transcript)
    return transcript


def _run_translation(text: str, target_lang: str, model_path: str, cli_path: str) -> str:
    target_name = SUPPORTED_LANGUAGES[target_lang]
    prompt = PROMPT_TRANSLATION.format(TARGET_LANGUAGE=target_name, TEXT=text)
    return run_llama(prompt, model_path, cli_path)


def _run_formatting(mode: str, text: str, model_path: str, cli_path: str) -> str:
    if mode == MODE_VOICE:
        return text
    prompt = _format_prompt(mode, text)
    return run_llama(prompt, model_path, cli_path)


def _start_command(args: argparse.Namespace, config: dict) -> int:
    try:
        load_state()
        print("Recording already in progress.", file=sys.stderr)
        return 1
    except StateError:
        pass

    mode = args.mode or config.get("default_mode")
    if mode not in SUPPORTED_MODES:
        print(f"Unsupported mode: {mode}", file=sys.stderr)
        return 1

    language = args.language or config.get("default_language")
    translate = args.translate or config.get("translation_target")
    try:
        _validate_language_pair(language, translate)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    audio_path = REPO_ROOT / "data" / "tmp" / f"recording-{timestamp}.wav"

    try:
        recording = start_recording(audio_path, config.get("audio_device"))
    except AudioError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    state = {
        "audio_path": str(audio_path),
        "pids": recording.pids,
        "method": recording.method,
        "mode": mode,
        "language": language,
        "translate": translate,
        "clipboard_enabled": config.get("clipboard_enabled", True) and not args.no_clipboard,
        "history_enabled": config.get("history_enabled", True) and not args.no_history,
        "output_path": str(args.output) if args.output else None,
        "started_at": timestamp,
    }
    save_state(state)
    print(f"Recording started ({recording.method}).")
    return 0


def _stop_command(config: dict) -> int:
    try:
        state = load_state()
    except StateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    audio_path = Path(state["audio_path"])
    stop_recording(state["pids"])

    transcript = ""
    detected = None
    text = ""
    translate_target = state.get("translate")
    llama_cli_path = config.get("llama_cli_path", "llama-cli")

    try:
        try:
            _validate_binary_path(config.get("whisper_cli_path"), "whisper_cli_path")
            _validate_model_path(config.get("whisper_model_path"), "whisper_model_path")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        try:
            transcript, detected = run_whisper(
                audio_path,
                config.get("whisper_model_path"),
                state.get("language"),
                config.get("whisper_cli_path", "whisper-cli"),
            )
        except WhisperError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        text = transcript
        llama_available = True
        needs_llama = translate_target or state.get("mode") != MODE_VOICE
        if needs_llama:
            try:
                _validate_binary_path(config.get("llama_cli_path"), "llama_cli_path")
                _validate_model_path(config.get("llama_model_path"), "llama_model_path")
            except ValueError as exc:
                print(f"LLM unavailable, skipping translation/formatting: {exc}", file=sys.stderr)
                llama_available = False

        if translate_target and llama_available:
            try:
                text = _run_translation(text, translate_target, config.get("llama_model_path"), llama_cli_path)
            except LlamaError as exc:
                print(f"Translation failed, using transcript: {exc}", file=sys.stderr)
                text = transcript

        if state.get("mode") != MODE_VOICE and llama_available:
            try:
                text = _run_formatting(state["mode"], text, config.get("llama_model_path"), llama_cli_path)
            except LlamaError as exc:
                print(f"Formatting failed, using transcript: {exc}", file=sys.stderr)
                text = transcript

        output_path = Path(state["output_path"]) if state.get("output_path") else None
        write_output(text, output_path)

        if state.get("clipboard_enabled"):
            try:
                copy_to_clipboard(text)
                if config.get("clipboard_notify_enabled", True):
                    notify_clipboard_copied()
            except OutputError as exc:
                print(f"Clipboard copy failed: {exc}", file=sys.stderr)

        if state.get("history_enabled"):
            history_dir = resolve_history_dir(config)
            metadata = {
                "mode": state["mode"],
                "language": state.get("language") or detected,
                "translate": translate_target,
                "audio_path": str(audio_path),
            }
            try:
                write_history(history_dir, transcript, text, metadata)
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"History write failed: {exc}", file=sys.stderr)
    finally:
        if audio_path.exists():
            audio_path.unlink()
        clear_state()

    return 0


def _cancel_command() -> int:
    try:
        state = load_state()
    except StateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    stop_recording(state["pids"])
    audio_path = Path(state["audio_path"])
    if audio_path.exists():
        audio_path.unlink()
    clear_state()
    print("Recording cancelled.")
    return 0


def main() -> int:
    config = load_config()
    args = _parse_args()

    if args.command == "start":
        return _start_command(args, config)
    if args.command == "stop":
        return _stop_command(config)
    if args.command == "cancel":
        return _cancel_command()

    print("Unknown command.", file=sys.stderr)
    return 1
