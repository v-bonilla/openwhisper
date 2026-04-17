# OpenWhisper (Linux CLI)

OpenWhisper is a Linux-only CLI dictation tool. It records audio, transcribes via `whisper-cli` or Parakeet-TDT (`sherpa-onnx`), and optionally formats output via `llama-cli`. Output is printed to stdout and copied to the clipboard.

## MVP Goals
- Voice-to-text, email, and note modes
- Optional translation between en/es/de/fr
- Local-only inference (no network calls)
- CLI driven hotkey workflows

## Transcription Backends
- `whisper` (default): `whisper-cli` from [whisper.cpp](https://github.com/ggerganov/whisper.cpp). Default model `large-v3`. Full 99-language coverage.
- `parakeet`: NVIDIA Parakeet-TDT-0.6B v3 via [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). Lower WER than Whisper large-v3 on the 25 EU languages it supports, and much faster on CPU.

Pick a backend via `--backend {whisper,parakeet}` or `transcription_backend` in `config/openwhisper.toml`.

## Install

**Requirements:** Linux, Python 3.13, [uv](https://docs.astral.sh/uv/).

1. Install system dependencies:
   - `llama-cli` ([llama.cpp](https://github.com/ggerganov/llama.cpp))
   - Audio: `pw-record` (PipeWire) or `parec` + `sox`/`ffmpeg`
   - Clipboard: `dbus-send` (via xdg-desktop-portal)
   - For `whisper` backend: `whisper-cli` ([whisper.cpp](https://github.com/ggerganov/whisper.cpp))
   - For `parakeet` backend: nothing extra — `sherpa-onnx` is pulled in via the `parakeet` extra.

2. Install the package:
   ```bash
   # Whisper backend only
   uv sync

   # With Parakeet backend enabled
   uv sync --extra parakeet
   ```

3. Download the Parakeet model (only if using `parakeet`):
   ```bash
   mkdir -p models && cd models
   curl -L -o parakeet.tar.bz2 \
     https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
   tar -xjf parakeet.tar.bz2 && rm parakeet.tar.bz2
   ```
   Then set `parakeet_model_dir` in `config/openwhisper.toml` to the extracted directory.

4. Verify:
   ```bash
   python scripts/check_deps.py --backend whisper
   python scripts/check_deps.py --backend parakeet
   ```

## Run
```bash
# Default (whisper)
uv run openwhisper start --mode voice-to-text
uv run openwhisper stop

# Parakeet backend
uv run openwhisper start --mode voice-to-text --backend parakeet
uv run openwhisper stop
```

## Usage
See `docs/usage.md` for CLI examples and hotkey setup.
See `docs/mvp-validation.md` for the manual test checklist and limitations.
