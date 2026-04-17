# OpenWhisper Usage

## CLI Commands
Start recording with a mode:
```bash
openwhisper start --mode voice-to-text
openwhisper start --mode email
openwhisper start --mode note
```

Stop recording and process audio:
```bash
openwhisper stop
```

Cancel recording without processing:
```bash
openwhisper cancel
```

## Optional Flags
- `--language {en,es,de,fr}`: set source language explicitly
- `--translate {en,es,de,fr}`: translate output to target language
- `--backend {whisper,parakeet}`: pick transcription backend (default from config; falls back to `whisper`)
- `--no-clipboard`: disable clipboard output
- `--no-history`: disable history output
- `--output FILE`: write output to a file path in addition to stdout

## Transcription Backends
- `whisper`: whisper.cpp `whisper-cli` with `large-v3` by default. Full language coverage; auto language detection validated against en/es/de/fr.
- `parakeet`: Parakeet-TDT-0.6B v3 via sherpa-onnx (CPU, int8). Supports 25 EU languages. Does not surface the detected language; pass `--language` if you need it recorded in history metadata.

## Hotkey Setup (GNOME/KDE)
Bind your desktop shortcuts to the CLI commands below:
- Start voice: `openwhisper start --mode voice-to-text`
- Start email: `openwhisper start --mode email`
- Start note: `openwhisper start --mode note`
- Stop: `openwhisper stop`
- Cancel: `openwhisper cancel`

## History Output
When history is enabled, outputs are stored under `./data/history/YYYYMMDD-HHMMSS/`:
- `transcript.txt`
- `output.txt`
- `metadata.json`
