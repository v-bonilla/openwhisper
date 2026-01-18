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
- `--no-clipboard`: disable clipboard output
- `--no-history`: disable history output
- `--output FILE`: write output to a file path in addition to stdout

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
