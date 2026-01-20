# OpenWhisper MVP Task Breakdown

## Phase 0: Repo and Project Skeleton
1) [x] Create new repo structure:
   - `openwhisper/` (Python package)
   - `bin/openwhisper` (CLI entrypoint)
   - `docs/` (usage and hotkey setup)
   - `scripts/` (dependency checks)
2) [x] Establish dev baseline with Python 3.13 and `uv`:
   - Use `uv init` or equivalent to create `pyproject.toml`
   - Pin `requires-python = ">=3.13"`
   - Document `uv` usage in `README.md`
3) [x] Add basic `README.md` with MVP goals, dependencies, and usage.

## Phase 1: Core CLI and Audio Capture
4) [x] Implement CLI argument parsing:
   - `start`, `stop`, `cancel`
   - `--mode`, `--language`, `--translate`, `--no-clipboard`, `--no-history`, `--output`
5) [x] Implement audio capture:
   - `pw-record` primary, `parec` fallback
   - Save 16kHz mono WAV to temp file
6) [x] Implement lock/recording state handling for start/stop/cancel
   - Single active recording at a time
   - Persist state to temp dir

## Phase 2: Whisper Transcription
7) [x] Integrate `whisper-cli` invocation:
   - Default model `large-v3`
   - Language flag when provided
   - Capture plain text output
8) [x] Validate detected language is in en/es/de/fr
   - Abort on unsupported language

## Phase 3: Llama Formatting and Translation
9) [x] Implement `llama-cli` invocation:
   - Default model `gpt-oss-20b`
   - Stable decoding parameters
10) [x] Add translation step:
   - Prompt template and language mapping
   - Output only translation
11) [x] Add mode formatting:
   - Email prompt
   - Note prompt
   - Skip for voice-to-text

## Phase 4: Output and History
12) [x] Clipboard output:
   - DBus via xdg-desktop-portal (`dbus-send`)
13) [x] Stdout output and optional `--output` file
14) [x] History storage:
   - Raw transcript
   - Final output
   - Metadata JSON
   - Repo-local path `./data/history/`

## Phase 5: Configuration
15) [x] Add config file loader:
   - `./config/openwhisper.toml` (repo-local)
   - CLI overrides config
16) [x] Validate config paths and required binaries

## Phase 6: Docs and Hotkey Guidance
17) [x] Write usage docs:
   - CLI examples
   - Desktop hotkey setup instructions
18) [x] Document dependencies:
   - `whisper-cli`, `llama-cli`, `pw-record`, `parec`, `dbus-send`
19) [x] Document dev requirements:
   - Python 3.13
   - `uv` for environment and workflow

## Phase 7: MVP Validation
20) [x] Manual test checklist:
   - Start/stop/cancel flow
   - Voice mode transcript only
   - Email and note formatting
   - Translation across en/es/de/fr
   - Clipboard and stdout output
21) [x] Record MVP known limitations and next steps
