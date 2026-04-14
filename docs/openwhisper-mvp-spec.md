# OpenWhisper MVP Spec (Linux CLI)

## Purpose
OpenWhisper is a Linux-only CLI dictation tool. It turns speech into text and optionally formats it for specific use cases (email, note). The MVP is a simple Python CLI that shells out to `whisper-cli` (whisper.cpp) and `llama-cli` (llama.cpp). It is launched via desktop hotkeys and outputs text to clipboard (via DBus) and stdout.

## Scope and Constraints
- Name: `openwhisper`
- Platform: Linux only
- Interface: CLI only, no GUI and no daemon
- Hotkeys: managed by the desktop environment (GNOME/KDE/etc.)
- Models:
  - Whisper default: `large-v3`
  - Llama default: `gpt-oss-20b`
- Supported languages: English, Spanish, German, French
- Modes (MVP): `voice-to-text`, `email`, `note`
- Translation between supported languages
- Local-only inference; no network calls
- No packaging for MVP
- Development requirements:
  - Python 3.13
  - Use `uv` for environment, dependencies, and running scripts

## User Experience Summary
- User binds hotkeys to CLI commands (start/stop/cancel) for each mode.
- The CLI records mic audio, transcribes it, optionally translates, then formats output by mode.
- Output is printed to stdout and copied to the clipboard (via DBus).
- Optional history files stored locally.

## CLI Overview
Single Python entrypoint: `openwhisper`.

### Primary Commands
- `openwhisper start --mode voice-to-text`
- `openwhisper start --mode email`
- `openwhisper start --mode note`
- `openwhisper stop`
- `openwhisper cancel`

### Optional Flags (MVP)
- `--language {en,es,de,fr}`: set source language explicitly (default: auto-detect, but restricted)
- `--translate {en,es,de,fr}`: translate output to target language
- `--no-clipboard`: do not copy to clipboard
- `--no-history`: do not write history files
- `--output FILE`: write output to a file path (in addition to stdout)

## Audio Capture
- Record from default microphone using PipeWire (`pw-record`) with PulseAudio fallback (`parec` + `sox`/`ffmpeg`).
- Audio is saved to a temporary WAV file (16kHz mono) for whisper.cpp input.
- The CLI should report errors clearly when audio capture fails or required tools are missing.

## Processing Pipeline
1) Record audio until `stop` command is invoked.
2) Transcribe audio with `whisper-cli` using the `large-v3` model.
3) If `--translate` is provided, translate text via `llama-cli`.
4) If mode is `email` or `note`, apply LLM formatting prompt via `llama-cli`.
5) Output final text to stdout and clipboard (via DBus), optionally write history.

## Supported Languages and Validation
- Only en/es/de/fr are supported.
- If auto-detection yields unsupported language, abort and return a clear error.
- Translation must be between the supported languages only.

## Mode Definitions
### Voice to Text
- Transcription-only; no LLM formatting.
- Basic punctuation from Whisper output is preserved.

### Email
- LLM formats transcription into a polished email.
- Must add greeting/closing, fix grammar, preserve tone.
- Highlight action items if present.

### Note
- LLM formats transcription into structured notes.
- Use headings or bullets; highlight key points and action items.

## LLM Prompting
All prompts must be deterministic and concise. Output should contain only the final text (no preamble).

### Email Prompt (template)
"""
You are formatting a dictation into a clear email. Keep the speaker's tone.
Requirements:
- Add a natural greeting and closing.
- Fix grammar and punctuation.
- Highlight action items if present (bullet list or inline).
Output only the email.

Dictation:
{TRANSCRIPT}
"""

### Note Prompt (template)
"""
You are formatting a dictation into structured notes.
Requirements:
- Improve clarity and readability.
- Use headings or bullets when helpful.
- Highlight key points and action items.
Output only the notes.

Dictation:
{TRANSCRIPT}
"""

### Translation Prompt (template)
"""
Translate the following text to {TARGET_LANGUAGE}.
- Preserve meaning and tone.
- Output only the translation.

Text:
{TEXT}
"""

## Model Invocation
### Whisper (whisper.cpp)
- Binary: `whisper-cli`
- Default model: `large-v3`
- Use explicit `--language` when user sets it.
- Set output to plain text (no timestamps) unless needed for debugging.

### Llama (llama.cpp)
- Binary: `llama-cli`
- Default model: `gpt-oss-20b`
- Run with a fixed temperature and top-p for stable outputs.
- Ensure prompts are passed via stdin or a temp file to avoid shell-escaping issues.

## Configuration
Config file: `./config/openwhisper.toml` (repo-local)

Suggested keys:
- `whisper_model_path`
- `llama_model_path`
- `default_mode`
- `default_language`
- `clipboard_enabled`
- `clipboard_notify_enabled`
- `history_enabled`
- `history_dir` (default: `./data/history`)
- `audio_device`
- `translation_target`

Config is optional; CLI flags override config.

## Output and History
- Always print final output to stdout.
- Copy output to clipboard via DBus (xdg-desktop-portal).
- If history enabled, save:
  - raw transcript
  - final output
  - metadata (mode, language, timestamps)
  in `./data/history/YYYYMMDD-HHMMSS/` (repo-local).

## Error Handling
- Missing dependencies: show actionable error messages.
- Audio capture failure: stop and return non-zero exit code.
- Whisper/LLM failure: return raw transcript with warning, unless transcription failed.
- Unsupported language: abort with a clear message.

## Security and Privacy
- All processing is local.
- No network usage.
- Temporary audio files are stored under `./data/tmp/` and deleted after processing.

## Desktop Hotkey Integration (User Setup)
- Provide documentation for setting hotkeys in GNOME/KDE to run CLI commands.
- Example hotkeys:
  - Start voice: `openwhisper start --mode voice-to-text`
  - Start email: `openwhisper start --mode email`
  - Start note: `openwhisper start --mode note`
  - Stop: `openwhisper stop`
  - Cancel: `openwhisper cancel`

## MVP Acceptance Criteria
- Transcription works from CLI with `whisper-cli` using `large-v3`.
- Email and Note modes format text via `llama-cli` using `gpt-oss-20b`.
- Translation between en/es/de/fr works.
- Output is sent to stdout and clipboard (via DBus).
- Hotkeys can be configured through the desktop environment.
