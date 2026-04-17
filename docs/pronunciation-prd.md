# Pronunciation Training PRD

## Purpose
Add an English pronunciation trainer to OpenWhisper. Two exercises:
- **Minimal-pair drill**: user says a target word; Whisper/Parakeet's
  transcription reveals whether the pronunciation was phonetically
  distinguishable from its confusable partner (e.g. `ship` vs `sheep`).
- **Shadow-read**: user reads a target sentence or paragraph aloud; the
  transcription is aligned against the target and mispronounced / missed
  words are highlighted.

The feature reuses OpenWhisper's existing audio capture, transcription
backends, config, and history — no parallel project.

## Scope and Constraints
- Language: English only (MVP).
- Platform: Linux only, same as OpenWhisper.
- Interface: CLI, no GUI, no daemon.
- Backends: both `whisper` and `parakeet`; selection follows existing
  `--backend` / `transcription_backend` conventions.
- Local-only inference; no network calls.
- No new external binaries.
- Development: Python 3.13, `uv`.

## Goals
- One-command drill session with clear per-attempt and summary feedback.
- One-command shadow-read with a highlighted word-level diff.
- Zero changes to the existing `start` / `stop` / `cancel` dictation flow.
- Dev/CI path that runs the full pipeline without a microphone.

## Non-Goals
- Phoneme-level forced alignment or IPA diffing.
- Acoustic scoring beyond what transcription already provides.
- Multi-user profiles or cloud sync.
- Languages other than English.
- Packaging changes.

## User Experience Summary
- User runs `openwhisper drill` (or `shadow`) in a terminal.
- CLI prints the target and prompts for Enter to start recording, Enter to stop.
- Transcription runs via the configured backend; result is classified and printed.
- At session end, a summary is printed and persisted to history.
- A `--audio-file` flag bypasses the mic and runs the pipeline against a WAV.

## CLI Overview
New flat subcommands alongside existing `start` / `stop` / `cancel`.

### Commands
- `openwhisper drill`
- `openwhisper shadow`
- `openwhisper pairs-list`

### Drill Flags
- `--count N` — number of targets in a session (default: 10)
- `--category NAME` — restrict to one category (e.g. `r-l`, `th-s`, `i-ii`)
- `--backend {whisper,parakeet}` — override configured backend
- `--audio-file WAV --target WORD` — dev/test mode; one-shot, no mic

### Shadow Flags
- `<paragraph-id>` positional, or `--file PATH` — source paragraph
- `--backend {whisper,parakeet}`
- `--audio-file WAV` — dev/test mode; skip mic, use WAV for the read

### Pairs-List Flags
- `--category NAME`

CLI flags override config. Unknown combinations abort with clear errors
(same convention as existing subcommands).

## Pair-Drill Exercise

### Round flow
1. Load pairs from `pronunciation_pairs_path`; filter by `--category` if set.
2. Sample `--count` targets without replacement (fall back to replacement
   if the pool is smaller than `count`).
3. For each target:
   - Print `Say: SHEEP  (not SHIP)`.
   - Start recording (reuses `openwhisper.audio.start_recording`).
   - Wait for Enter; stop recording (`stop_recording`).
   - Transcribe the WAV via the configured backend.
   - Normalize transcript and classify.
4. Print session summary grouped by category and write history.

### Classification
Given normalized transcript tokens `T`, target `w`, partner `p`:
- `PASS` — `w ∈ T` and `p ∉ T`.
- `CONFUSED` — `p ∈ T` and `w ∉ T`.
- `UNCLEAR` — neither, or empty transcript.

If both appear (rare, multi-word utterance), prefer `PASS` when the
transcript's first content token matches `w`, else `UNCLEAR`.

### Output
Per attempt: `PASS` / `CONFUSED → heard "ship"` / `UNCLEAR → heard "uh"`.
Summary: totals per outcome, plus worst-performing categories.

## Shadow-Read Exercise

### Round flow
1. Load paragraph by id from `pronunciation_paragraphs_dir` or from `--file`.
2. Print the paragraph.
3. Start recording; wait for Enter; stop.
4. Transcribe via the configured backend.
5. Normalize + tokenize both target and transcript.
6. Run word-level Levenshtein alignment; emit per-token ops
   (match / substitute / insert / delete).
7. Render aligned diff to stdout with ANSI colors:
   - match: default
   - substitute: strike-through on target, red on heard
   - delete (missed): dim target
   - insert (extra): red heard
8. Print accuracy = `matches / len(target_tokens)`.
9. Write history.

### Works for sentences too
A one-sentence file is valid input; no separate command needed.

## Data

### Minimal pairs
- Path: `data/pronunciation/minimal_pairs.json`
- Schema: `[{"word": str, "partner": str, "category": str}, ...]`
- Seed contents: ~50 pairs across categories common to L2 English speakers
  (`th-s`, `v-b`, `r-l`, `i-ii`, `ae-uh`, `ship-sheep`-style vowel length, etc.).
- Invariants: unique `(word, partner)` ordered pair; every entry has a category.

### Paragraphs
- Path: `data/pronunciation/paragraphs/<id>.txt`
- UTF-8 plain text, one paragraph per file, short (≤ 4 sentences for MVP).
- A few seed paragraphs ship with the repo.

## Package and Module Layout

New subpackage `openwhisper/pronunciation/`:
- `__init__.py`
- `pairs.py` — load + filter pairs; `PairsError`
- `paragraphs.py` — load by id or path; `ParagraphError`
- `normalize.py` — lowercase, strip punctuation, tokenize
- `score.py` — word-level Levenshtein alignment, ops, accuracy
- `drill.py` — drill session orchestration and classification
- `shadow.py` — shadow-read orchestration and rendered diff
- `transcribe.py` — single dispatcher around `run_whisper` / `run_parakeet`,
  sharing the model/binary validation currently inline in `cli._stop_command`
- `record.py` — synchronous press-Enter-to-stop wrapper around
  `openwhisper.audio.start_recording` / `stop_recording` (no state file;
  drill/shadow are foreground, single-process)

Updates to existing files:
- `openwhisper/cli.py` — new subparsers wired in; backend validation lifted
  into a shared helper and reused by `_stop_command` (only non-additive change).
- `openwhisper/constants.py` — add `EXERCISE_DRILL`, `EXERCISE_SHADOW`,
  `SUPPORTED_EXERCISES`.
- `openwhisper/config.py` — add new defaults (see Configuration).

No changes to `audio.py`, `whisper.py`, `parakeet.py`, `history.py`,
`output.py`, `state.py`, `llama.py`.

## Configuration
Extend `config/openwhisper.toml.example` with documented keys. Defaults
merged in `openwhisper/config.py`:

- `pronunciation_pairs_path` — default
  `./data/pronunciation/minimal_pairs.json`
- `pronunciation_paragraphs_dir` — default
  `./data/pronunciation/paragraphs`

No changes to existing keys.

## History
Reuse existing `write_history(transcript, final_text, metadata)`:
- `transcript` — raw transcription across the session (concatenated for drill).
- `final_text` — rendered summary (drill) or highlighted diff (shadow).
- `metadata` — existing keys plus:
  - `type`: `"drill"` or `"shadow"`
  - `results`: per-attempt array (drill) or `{accuracy, ops}` blob (shadow)
  - `backend`, `language` already captured by existing flow

No schema change required in `history.py`.

## Error Handling
- Missing binary / model — same error messages as `stop` (shared helper).
- Missing pairs JSON or paragraph file — clear message, non-zero exit.
- Empty transcript — counted as `UNCLEAR` (drill) or treated as all-deleted (shadow).
- Non-TTY stdin with no `--audio-file` — abort with instructions to use `--audio-file`.
- Keyboard interrupt mid-session — cancel current recording, clean up temp WAV,
  print partial summary if any attempts completed.

## Integration Notes
- `start` / `stop` / `cancel` behavior unchanged; backend validation helper
  is extracted but its semantics preserved (covered by a regression test).
- Recording in drill/shadow uses the same `data/tmp/` directory for temp
  WAVs as dictation; files are deleted after each attempt.
- History writes go to the existing `history_dir`; entries are
  distinguished by `metadata.type`.

## Acceptance Criteria
- `openwhisper drill --audio-file <sheep.wav> --target sheep` exits 0, prints `PASS`.
- `openwhisper drill --audio-file <ship.wav> --target sheep` exits 0, prints `CONFUSED`.
- `openwhisper shadow --audio-file <para.wav> --file <para.txt>` prints a
  colored diff and an accuracy score in `[0, 1]`.
- `openwhisper drill --count 3` (interactive) runs three rounds and writes
  one history entry.
- `openwhisper shadow sample-1` (interactive) loads a seeded paragraph,
  records, and prints the diff.
- `openwhisper start/stop/cancel` continues to pass the existing
  `docs/mvp-validation.md` checklist.
- All unit tests green; lint clean with `uv run ruff check`.

## Verification Plan

### Unit tests (no audio, no binaries)
- `test_normalize.py` — idempotence, punctuation/case, tokenization edges.
- `test_score.py` — golden alignments for match/substitute/insert/delete
  and composite cases; accuracy math.
- `test_pairs.py` — JSON schema; no duplicates; all entries categorized.
- `test_drill.py` — fake `transcribe` callable:
  target → `PASS`, partner → `CONFUSED`, `"um"` → `UNCLEAR`; aggregation
  totals match.
- `test_shadow.py` — fake transcribe + golden diff string for a canned paragraph.
- `test_transcribe_dispatch.py` — both backends monkeypatched; assert
  dispatch and that the same validation errors surface as in `_stop_command`.
- `test_cli_backend_helper.py` — regression on the lifted validation helper,
  covering each error case formerly asserted inline in `_stop_command`.

### Integration tests (pytest markers, skipped if backend unavailable)
- Fixtures checked in under `tests/pronunciation/fixtures/`:
  tiny `ship.wav`, `sheep.wav`, single-sentence paragraph `para.wav` + `para.txt`.
- Markers `@pytest.mark.whisper` and `@pytest.mark.parakeet`.
- Cases:
  - drill `--audio-file sheep.wav --target sheep` → `PASS`
  - drill `--audio-file ship.wav --target sheep` → `CONFUSED`
  - shadow `--audio-file para.wav --file para.txt` → score ∈ `[0, 1]`,
    diff matches a relaxed golden assertion.

### Regression
- Full pass through `docs/mvp-validation.md` once before merge to confirm
  dictation flow unchanged.

### Manual mic smoke (logged into `docs/pronunciation-validation.md`)
- drill three-round session: correct utterance, deliberate partner flip,
  silence → expect `PASS`, `CONFUSED`, `UNCLEAR`.
- shadow clean read, then re-read with one deliberately substituted word
  → expect that word highlighted in the diff.
- Record results in the validation doc.

### Lint
- `uv run ruff check` clean on all new files.

### Dev loop
- `--audio-file` flags on both exercises make iteration and CI possible
  without a microphone; pre-recorded fixtures double as golden inputs.

## Risks and Open Questions
- **Whisper latency**: `large-v3` on CPU is slow per utterance; drill will
  feel sluggish. Accepted for MVP — drill inherits the existing
  `transcription_backend` default (`whisper`); no per-exercise override.
  Users can switch with `--backend parakeet` per invocation if they need
  faster turnaround.
- **Orthographic collapse**: Whisper normalizes to "the right spelling",
  which can mask near-misses. Accepted tradeoff; documented in the
  "Non-Goals" (no phoneme-level analysis for MVP).
- **Non-TTY stdin**: Enter-to-stop requires a TTY. `--audio-file` covers
  non-interactive use. No background daemon needed.
- **Pair curation quality**: MVP seed list will be small and opinionated;
  quality depends on source selection. Out of scope to hand-tune beyond
  common L2 English confusions.

## Out of Scope / Future Work
- Phoneme-level feedback (IPA diff, forced alignment).
- LLM-generated coaching via `llama-cli`.
- Spaced-repetition scheduling of struggling pairs.
- Additional languages.
- GUI or TUI front-end.
- Streaming / incremental transcription.
