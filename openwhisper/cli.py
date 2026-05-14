from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from .audio import AudioError, start_recording, stop_recording
from .config import REPO_ROOT, load_config, resolve_history_dir
from .constants import (
    BACKEND_PARAKEET,
    BACKEND_WHISPER,
    EXERCISE_DRILL,
    EXERCISE_SHADOW,
    MODE_EMAIL,
    MODE_NOTE,
    MODE_VOICE,
    PROMPT_EMAIL,
    PROMPT_NOTE,
    PROMPT_TRANSLATION,
    SUPPORTED_BACKENDS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
)
from .history import write_history
from .llama import LlamaError, run_llama
from .output import (
    OutputError,
    abort_ydotool_typing,
    copy_to_clipboard,
    finish_ydotool_typing,
    notify_clipboard_copied,
    start_ydotool_typing,
    write_output,
)
from .parakeet import PARAKEET_FILES, ParakeetError, run_parakeet
from . import streamer
from .state import StateError, clear_state, load_state, save_state
from .whisper import WhisperError, run_whisper


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="openwhisper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES))
    start_parser.add_argument("--language", choices=sorted(SUPPORTED_LANGUAGES))
    start_parser.add_argument("--translate", choices=sorted(SUPPORTED_LANGUAGES))
    start_parser.add_argument("--backend", choices=sorted(SUPPORTED_BACKENDS))
    start_parser.add_argument("--no-clipboard", action="store_true")
    start_parser.add_argument("--no-history", action="store_true")
    start_parser.add_argument("--auto-type", action="store_true")
    start_parser.add_argument("--stream", action="store_true")
    start_parser.add_argument("--output", type=Path)

    subparsers.add_parser("stop")
    subparsers.add_parser("cancel")

    drill_parser = subparsers.add_parser("drill")
    drill_parser.add_argument("--count", type=int, default=10)
    drill_parser.add_argument("--category")
    drill_parser.add_argument("--backend", choices=sorted(SUPPORTED_BACKENDS))
    drill_parser.add_argument("--audio-file", type=Path)
    drill_parser.add_argument("--target")

    shadow_parser = subparsers.add_parser("shadow")
    shadow_parser.add_argument("paragraph_id", nargs="?")
    shadow_parser.add_argument("--file", type=Path)
    shadow_parser.add_argument("--backend", choices=sorted(SUPPORTED_BACKENDS))
    shadow_parser.add_argument("--audio-file", type=Path)

    pairs_list_parser = subparsers.add_parser("pairs-list")
    pairs_list_parser.add_argument("--category")

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


def _validate_parakeet_model_dir(value: str | None) -> None:
    if not value:
        raise ValueError("parakeet_model_dir is not set.")
    model_dir = Path(value)
    if not model_dir.is_dir():
        raise ValueError(f"parakeet_model_dir not found: {value}")
    missing = [name for name in PARAKEET_FILES if not (model_dir / name).exists()]
    if missing:
        raise ValueError(
            f"parakeet_model_dir missing files: {', '.join(missing)} in {value}"
        )


def validate_backend_requirements(backend: str, config: dict) -> None:
    """Validate CLI paths / model files for the given backend.

    Raises ValueError with the same messages previously asserted inline in
    _stop_command. Shared by dictation and pronunciation transcription.
    """
    if backend == BACKEND_PARAKEET:
        _validate_parakeet_model_dir(config.get("parakeet_model_dir"))
        return
    if backend == BACKEND_WHISPER:
        _validate_binary_path(config.get("whisper_cli_path"), "whisper_cli_path")
        _validate_model_path(config.get("whisper_model_path"), "whisper_model_path")
        return
    raise ValueError(f"Unsupported backend: {backend}")


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

    backend = args.backend or config.get("transcription_backend", BACKEND_WHISPER)
    if backend not in SUPPORTED_BACKENDS:
        print(f"Unsupported backend: {backend}", file=sys.stderr)
        return 1

    language = args.language or config.get("default_language")
    translate = args.translate or config.get("translation_target")
    try:
        _validate_language_pair(language, translate)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    auto_type_enabled = args.auto_type or config.get("auto_type_enabled", False)
    stream_enabled = args.stream or config.get("auto_type_stream_enabled", False)

    if stream_enabled and not auto_type_enabled:
        print("--stream requires --auto-type.", file=sys.stderr)
        return 1

    if auto_type_enabled:
        try:
            _validate_binary_path(config.get("auto_type_binary"), "auto_type_binary")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if stream_enabled:
        if mode != MODE_VOICE:
            print(
                "--stream requires voice mode; email/note formatting needs the full transcript.",
                file=sys.stderr,
            )
            return 1
        if translate:
            print(
                "--stream is incompatible with --translate; translation needs the full transcript.",
                file=sys.stderr,
            )
            return 1
        if not language:
            print(
                "--stream requires an explicit --language (or default_language in config); "
                "per-chunk auto-detect is unreliable.",
                file=sys.stderr,
            )
            return 1
        try:
            validate_backend_requirements(backend, config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    audio_path = REPO_ROOT / "data" / "tmp" / f"recording-{timestamp}.wav"

    if stream_enabled:
        try:
            streamer_info = streamer.spawn_streamer(backend, language, config)
        except Exception as exc:
            print(f"Failed to start streamer: {exc}", file=sys.stderr)
            return 1
        state = {
            "streaming": True,
            "mode": mode,
            "backend": backend,
            "language": language,
            "translate": None,
            "clipboard_enabled": False,
            "auto_type_enabled": True,
            "history_enabled": config.get("history_enabled", True) and not args.no_history,
            "output_path": str(args.output) if args.output else None,
            "started_at": timestamp,
            "streamer_pid": streamer_info["streamer_pid"],
            "streamer_start_time": streamer_info["streamer_start_time"],
            "fifo_path": streamer_info["fifo_path"],
            "result_path": streamer_info["result_path"],
            "log_path": streamer_info["log_path"],
        }
        save_state(state)
        print(f"Streaming auto-type started (pid {streamer_info['streamer_pid']}).")
        return 0

    try:
        recording = start_recording(audio_path, config.get("audio_device"))
    except AudioError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    clipboard_enabled = config.get("clipboard_enabled", True) and not args.no_clipboard
    if auto_type_enabled:
        clipboard_enabled = False

    state = {
        "streaming": False,
        "audio_path": str(audio_path),
        "pids": recording.pids,
        "method": recording.method,
        "mode": mode,
        "backend": backend,
        "language": language,
        "translate": translate,
        "clipboard_enabled": clipboard_enabled,
        "auto_type_enabled": auto_type_enabled,
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

    if state.get("streaming"):
        return _stop_streaming(state, config)

    audio_path = Path(state["audio_path"])
    stop_recording(state["pids"])

    transcript = ""
    detected = None
    text = ""
    translate_target = state.get("translate")
    llama_cli_path = config.get("llama_cli_path", "llama-cli")

    backend = state.get("backend", BACKEND_WHISPER)
    exit_code = 0
    ydotool_proc = None
    if state.get("auto_type_enabled"):
        try:
            ydotool_proc = start_ydotool_typing(
                config.get("auto_type_binary", "ydotool"),
                int(config.get("auto_type_key_delay_ms", 0)),
                int(config.get("auto_type_key_hold_ms", 0)),
            )
        except OutputError as exc:
            print(str(exc), file=sys.stderr)
            exit_code = 1
    try:
        try:
            validate_backend_requirements(backend, config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if backend == BACKEND_PARAKEET:
            try:
                transcript, detected = run_parakeet(
                    audio_path,
                    config.get("parakeet_model_dir"),
                    state.get("language"),
                    int(config.get("parakeet_num_threads", 4)),
                )
            except ParakeetError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        else:
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

        if ydotool_proc is not None:
            try:
                finish_ydotool_typing(
                    ydotool_proc,
                    text,
                    int(config.get("auto_type_focus_delay_ms", 0)),
                )
            except OutputError as exc:
                print(str(exc), file=sys.stderr)
                exit_code = 1
            finally:
                ydotool_proc = None
        elif state.get("clipboard_enabled"):
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
                "backend": backend,
                "language": state.get("language") or detected,
                "translate": translate_target,
                "audio_path": str(audio_path),
            }
            try:
                write_history(history_dir, transcript, text, metadata)
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"History write failed: {exc}", file=sys.stderr)
    finally:
        if ydotool_proc is not None:
            abort_ydotool_typing(ydotool_proc)
        if audio_path.exists():
            audio_path.unlink()
        clear_state()

    return exit_code


def _stop_streaming(state: dict, config: dict) -> int:
    pid = int(state.get("streamer_pid", 0))
    start_time = state.get("streamer_start_time")
    timeout_s = float(config.get("auto_type_finalize_timeout_s", 15.0))
    transcript = streamer.signal_finalize(pid, start_time, timeout_s=timeout_s)

    output_path = Path(state["output_path"]) if state.get("output_path") else None
    if transcript:
        write_output(transcript, output_path)
    else:
        print("Streamer produced no transcript.", file=sys.stderr)

    if transcript and state.get("history_enabled"):
        history_dir = resolve_history_dir(config)
        metadata = {
            "mode": state["mode"],
            "backend": state.get("backend"),
            "language": state.get("language"),
            "translate": None,
            "streaming": True,
        }
        try:
            write_history(history_dir, transcript, transcript, metadata)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"History write failed: {exc}", file=sys.stderr)

    streamer.cleanup_artifacts()
    clear_state()
    return 0 if transcript else 1


def _resolve_backend(args_backend: str | None, config: dict) -> tuple[str | None, str | None]:
    backend = args_backend or config.get("transcription_backend", BACKEND_WHISPER)
    if backend not in SUPPORTED_BACKENDS:
        return None, f"Unsupported backend: {backend}"
    return backend, None


def _drill_command(args: argparse.Namespace, config: dict) -> int:
    from .pronunciation.drill import (
        AttemptResult,
        classify,
        format_attempt,
        format_summary,
        sample_targets,
    )
    from .pronunciation.pairs import (
        PairsError,
        filter_pairs,
        find_pair_by_word,
        load_pairs,
    )
    from .pronunciation.record import RecordError, record_until_enter
    from .pronunciation.transcribe import TranscribeError, transcribe_audio

    backend, err = _resolve_backend(args.backend, config)
    if err:
        print(err, file=sys.stderr)
        return 1

    pairs_path = Path(config.get("pronunciation_pairs_path") or "")
    try:
        all_pairs = load_pairs(pairs_path)
    except PairsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    filtered = filter_pairs(all_pairs, args.category)
    if not filtered:
        msg = (
            f"No pairs in category: {args.category}"
            if args.category
            else "No pairs loaded."
        )
        print(msg, file=sys.stderr)
        return 1

    if args.audio_file:
        if not args.target:
            print("--audio-file requires --target.", file=sys.stderr)
            return 1
        pair = find_pair_by_word(filtered, args.target)
        if pair is None:
            print(
                f"Target word not found in pairs: {args.target}",
                file=sys.stderr,
            )
            return 1
        audio_path = args.audio_file
        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}", file=sys.stderr)
            return 1
        try:
            transcript, _ = transcribe_audio(audio_path, backend, config)
        except TranscribeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        outcome, heard = classify(transcript, pair.word, pair.partner)
        result = AttemptResult(
            word=pair.word,
            partner=pair.partner,
            category=pair.category,
            transcript=transcript,
            outcome=outcome,
            heard=heard,
        )
        print(format_attempt(result))
        if config.get("history_enabled", True):
            _write_drill_history(config, [result], backend)
        return 0

    if args.target:
        print("--target is only valid with --audio-file.", file=sys.stderr)
        return 1

    if not sys.stdin.isatty():
        print(
            "Interactive drill requires a TTY; use --audio-file for non-interactive runs.",
            file=sys.stderr,
        )
        return 1

    device = config.get("audio_device")
    targets = sample_targets(filtered, args.count)
    results: list[AttemptResult] = []
    exit_code = 0
    try:
        for pair in targets:
            before = f"Say: {pair.word.upper()}  (not {pair.partner.upper()})"
            try:
                audio_path = record_until_enter(
                    before_prompt=before, device=device
                )
            except RecordError as exc:
                print(str(exc), file=sys.stderr)
                exit_code = 1
                break
            try:
                try:
                    transcript, _ = transcribe_audio(audio_path, backend, config)
                except TranscribeError as exc:
                    print(str(exc), file=sys.stderr)
                    exit_code = 1
                    break
            finally:
                if audio_path.exists():
                    audio_path.unlink()
            outcome, heard = classify(transcript, pair.word, pair.partner)
            result = AttemptResult(
                word=pair.word,
                partner=pair.partner,
                category=pair.category,
                transcript=transcript,
                outcome=outcome,
                heard=heard,
            )
            print(format_attempt(result))
            results.append(result)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        exit_code = 1

    if results:
        print()
        print(format_summary(results))
        if config.get("history_enabled", True):
            _write_drill_history(config, results, backend)
    return exit_code


def _write_drill_history(config: dict, results: list, backend: str) -> None:
    from .pronunciation.drill import format_summary, results_to_json

    try:
        history_dir = resolve_history_dir(config)
        transcripts = "\n".join(r.transcript for r in results)
        final_text = format_summary(results)
        metadata = {
            "type": EXERCISE_DRILL,
            "backend": backend,
            "language": "en",
            "results": results_to_json(results),
        }
        write_history(history_dir, transcripts, final_text, metadata)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"History write failed: {exc}", file=sys.stderr)


def _shadow_command(args: argparse.Namespace, config: dict) -> int:
    from .pronunciation.paragraphs import (
        ParagraphError,
        load_paragraph_by_id,
        load_paragraph_from_file,
    )
    from .pronunciation.record import RecordError, record_until_enter
    from .pronunciation.shadow import (
        compute_shadow,
        format_accuracy,
        ops_to_json,
        render_diff,
    )
    from .pronunciation.transcribe import TranscribeError, transcribe_audio

    backend, err = _resolve_backend(args.backend, config)
    if err:
        print(err, file=sys.stderr)
        return 1

    try:
        if args.file:
            target_text = load_paragraph_from_file(args.file)
        elif args.paragraph_id:
            paragraphs_dir = Path(config.get("pronunciation_paragraphs_dir") or "")
            target_text = load_paragraph_by_id(paragraphs_dir, args.paragraph_id)
        else:
            print(
                "Provide a paragraph id or --file.",
                file=sys.stderr,
            )
            return 1
    except ParagraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cleanup = False
    if args.audio_file:
        audio_path = args.audio_file
        if not audio_path.exists():
            print(f"Audio file not found: {audio_path}", file=sys.stderr)
            return 1
    else:
        if not sys.stdin.isatty():
            print(
                "Interactive shadow requires a TTY; use --audio-file for non-interactive runs.",
                file=sys.stderr,
            )
            return 1
        print(target_text)
        print()
        try:
            audio_path = record_until_enter(
                before_prompt=None,
                device=config.get("audio_device"),
            )
        except RecordError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        cleanup = True

    try:
        transcript, _ = transcribe_audio(audio_path, backend, config)
    except TranscribeError as exc:
        print(str(exc), file=sys.stderr)
        if cleanup and audio_path.exists():
            audio_path.unlink()
        return 1
    finally:
        if cleanup and audio_path.exists():
            audio_path.unlink()

    result = compute_shadow(target_text, transcript)
    color = sys.stdout.isatty()
    print(render_diff(result.ops, color=color))
    print(format_accuracy(result.accuracy))

    if config.get("history_enabled", True):
        try:
            history_dir = resolve_history_dir(config)
            final_text = render_diff(result.ops, color=False)
            metadata = {
                "type": EXERCISE_SHADOW,
                "backend": backend,
                "language": "en",
                "target_text": target_text,
                "results": {
                    "accuracy": result.accuracy,
                    "ops": ops_to_json(result.ops),
                },
            }
            write_history(history_dir, transcript, final_text, metadata)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"History write failed: {exc}", file=sys.stderr)
    return 0


def _pairs_list_command(args: argparse.Namespace, config: dict) -> int:
    from .pronunciation.pairs import PairsError, filter_pairs, load_pairs

    pairs_path = Path(config.get("pronunciation_pairs_path") or "")
    try:
        all_pairs = load_pairs(pairs_path)
    except PairsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    filtered = filter_pairs(all_pairs, args.category)
    if not filtered:
        msg = (
            f"No pairs in category: {args.category}"
            if args.category
            else "No pairs loaded."
        )
        print(msg, file=sys.stderr)
        return 1
    by_category: dict[str, list] = {}
    for pair in filtered:
        by_category.setdefault(pair.category, []).append(pair)
    for category in sorted(by_category):
        print(f"{category}:")
        for pair in by_category[category]:
            print(f"  {pair.word} / {pair.partner}")
    return 0


def _cancel_command() -> int:
    try:
        state = load_state()
    except StateError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if state.get("streaming"):
        pid = int(state.get("streamer_pid", 0))
        start_time = state.get("streamer_start_time")
        streamer.signal_cancel(pid, start_time)
        streamer.cleanup_artifacts()
        clear_state()
        print("Streaming cancelled.")
        return 0

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
    if args.command == "drill":
        return _drill_command(args, config)
    if args.command == "shadow":
        return _shadow_command(args, config)
    if args.command == "pairs-list":
        return _pairs_list_command(args, config)

    print("Unknown command.", file=sys.stderr)
    return 1
