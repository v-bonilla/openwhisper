# OpenWhisper MVP (Linux CLI)

OpenWhisper is a Linux-only CLI dictation tool inspired by Superwhisper. It records audio, transcribes via `whisper-cli`, and optionally formats output via `llama-cli`. Output is printed to stdout and copied to the clipboard.

## MVP Goals
- Voice-to-text, email, and note modes
- Optional translation between en/es/de/fr
- Local-only inference (no network calls)
- CLI driven hotkey workflows

## Dependencies
- `whisper-cli` (whisper.cpp)
- `llama-cli` (llama.cpp)
- Audio capture: `pw-record` (PipeWire) or `parec` + `sox`/`ffmpeg`
- Clipboard: `wl-copy` (Wayland) or `xclip` (X11)

Run dependency checks:
```bash
python scripts/check_deps.py
```

## Development (Python 3.13 + uv)
```bash
uv venv
uv pip install -e .
```

Run the CLI:
```bash
uv run openwhisper start --mode voice-to-text
uv run openwhisper stop
```

## Usage
See `docs/usage.md` for CLI examples and hotkey setup.
See `docs/mvp-validation.md` for the manual test checklist and limitations.
