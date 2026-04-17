# OpenWhisper Agent Notes

## Purpose
OpenWhisper is a Linux-only CLI dictation tool. It records audio, transcribes via either `whisper-cli` (whisper.cpp) or Parakeet-TDT via `sherpa-onnx`, optionally translates or formats output via `llama-cli`, and writes to stdout/clipboard/history.

## Entry Points
- CLI: `openwhisper start|stop|cancel`
- Python entry: `openwhisper/cli.py`
- Script entry: `bin/openwhisper`

## Key Paths
- Config: `config/openwhisper.toml`
- History: `data/history/`
- Temp audio/state: `data/tmp/`
- Docs: `docs/usage.md`, `docs/mvp-validation.md`

## Workflow
- `start`: begin recording and write state to `data/tmp/recording_state.json`.
- `stop`: stop recording, run whisper, optionally run llama, then write output/clipboard/history.
- `cancel`: stop recording and delete temp audio without processing.

## Dependencies
- `whisper-cli` (whisper.cpp) — required for `whisper` backend
- `sherpa-onnx` + Parakeet-TDT v3 int8 model — required for `parakeet` backend (`uv sync --extra parakeet`)
- `llama-cli` (llama.cpp)
- Audio: `pw-record` or `parec` + `sox`/`ffmpeg`
- Clipboard: DBus via xdg-desktop-portal (`dbus-send`)

## Transcription Backends
- Selected via `transcription_backend` config key or `--backend {whisper,parakeet}` CLI flag; persisted in `data/tmp/recording_state.json` so `stop` matches `start`.
- Whisper path: `openwhisper/whisper.py` shells out to `whisper-cli`.
- Parakeet path: `openwhisper/parakeet.py` uses the `sherpa_onnx.OfflineRecognizer` Python API with int8 NeMo transducer weights.

## Dev
- Python 3.13
- `uv` for environment (`uv venv`, `uv pip install -e .`)
