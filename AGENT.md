# OpenWhisper Agent Notes

## Purpose
OpenWhisper is a Linux-only CLI dictation tool. It records audio, transcribes via `whisper-cli`, optionally translates or formats output via `llama-cli`, and writes to stdout/clipboard/history.

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
- `whisper-cli` (whisper.cpp)
- `llama-cli` (llama.cpp)
- Audio: `pw-record` or `parec` + `sox`/`ffmpeg`
- Clipboard: `wl-copy` or `xclip`

## Dev
- Python 3.13
- `uv` for environment (`uv venv`, `uv pip install -e .`)
