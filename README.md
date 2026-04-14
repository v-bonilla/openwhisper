# OpenWhisper (Linux CLI)

OpenWhisper is a Linux-only CLI dictation tool. It records audio, transcribes via `whisper-cli`, and optionally formats output via `llama-cli`. Output is printed to stdout and copied to the clipboard.

## MVP Goals
- Voice-to-text, email, and note modes
- Optional translation between en/es/de/fr
- Local-only inference (no network calls)
- CLI driven hotkey workflows

## Install

**Requirements:** Linux, Python 3.13, [uv](https://docs.astral.sh/uv/).

1. Install system dependencies:
   - `whisper-cli` ([whisper.cpp](https://github.com/ggerganov/whisper.cpp))
   - `llama-cli` ([llama.cpp](https://github.com/ggerganov/llama.cpp))
   - Audio: `pw-record` (PipeWire) or `parec` + `sox`/`ffmpeg`
   - Clipboard: `dbus-send` (via xdg-desktop-portal)

2. Install the package:
   ```bash
   uv sync
   ```

3. Verify:
   ```bash
   python scripts/check_deps.py
   ```

## Run
```bash
uv run openwhisper start --mode voice-to-text
uv run openwhisper stop
```

## Usage
See `docs/usage.md` for CLI examples and hotkey setup.
See `docs/mvp-validation.md` for the manual test checklist and limitations.
