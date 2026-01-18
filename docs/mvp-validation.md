# MVP Validation

## Manual Test Checklist
- Start/stop/cancel flow
- Voice mode transcript only
- Email formatting
- Note formatting
- Translation across en/es/de/fr
- Clipboard output and stdout output

## Known Limitations
- No daemon; hotkeys must call CLI commands directly.
- `whisper-cli` and `llama-cli` must be installed and available on PATH.
- Recording relies on PipeWire (`pw-record`) or PulseAudio (`parec` + `sox`/`ffmpeg`).
- Language detection depends on `whisper-cli` output; if unavailable, use `--language`.

## Next Steps
- Add packaging and installation scripts.
- Add richer error handling and retries for model failures.
- Add automated tests for CLI parsing and state handling.
