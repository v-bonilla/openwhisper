# Plan: Keep WAV Recordings

## Goal
A config flag that keeps each dictation's WAV file instead of deleting it at `stop`.

```toml
# recordings_enabled = false
# recordings_dir = "./data/recordings"
```

Default off. Behavior is unchanged when the flag is off.

## Current Behavior
- `start` records to `data/tmp/recording-<UTC ts>.wav` (`cli.py`, `_start_command`).
- `stop` transcribes, then deletes the file in its `finally` block, so the audio is lost even when transcription fails.
- `cancel` deletes the file.
- Streaming (`--stream`) never writes a full WAV. The daemon holds PCM in a bytearray that is trimmed past 1 MB and writes short-lived per-chunk WAVs (`streamer.py`).
- History metadata stores `audio_path` pointing at the deleted temp file, so the field is always a dangling path.

## Decisions
| Code | Decision | Choice | Why |
|---|---|---|---|
| D1 | Where recordings live | Own directory, `recordings_dir`, separate from history | Works with `--no-history`. Audio is about 1.9 MB/min, so users may want it on another disk or pruned on a different schedule. History metadata links to the file. |
| D2 | How the file gets there | `start` records straight into `recordings_dir`; `stop` skips the delete | No move step, no cross-filesystem copy, and the history `audio_path` becomes correct with no extra code. |
| D3 | `cancel` | Deletes the recording | Cancel means discard. |
| D4 | Streaming mode | In scope: the daemon writes the full PCM stream to a WAV | Otherwise the flag silently does nothing under `--stream`. |
| D5 | CLI override | None | The request is a config flag. Adding a `--save-recording` flag later is cheap. |
| D6 | Pronunciation `drill` / `shadow` | Out of scope | They have their own record path (`pronunciation/record.py`). Possible follow-up. |

The flag is read at `start` and saved in the state file, like `history_enabled`, so a config edit made mid-recording does not change what `stop` does.

## Steps

**S1. Config** (`config.py`)
- Add defaults `"recordings_enabled": False` and `"recordings_dir": str(REPO_ROOT / "data" / "recordings")`.
- Factor the body of `resolve_history_dir` into a private `_resolve_repo_path(value)` helper and add `resolve_recordings_dir(config)` on top of it.

**S2. Audio dir creation** (`audio.py`)
- `start_recording` creates `path.parent` (`mkdir(parents=True, exist_ok=True)`) in place of `_ensure_audio_dir()`, so any target directory works.

**S3. Batch start** (`cli.py`, `_start_command`)
- `save_recording = bool(config.get("recordings_enabled", False))`.
- If set: create `recordings_dir` with mode `0o700` and set `audio_path = recordings_dir / f"recording-{timestamp}.wav"`. Otherwise keep the `data/tmp` path.
- Avoid same-second collisions: if the path exists, append `-1`, `-2`, and so on. Without this, start/stop/start inside one UTC second overwrites a kept recording.
- Add `"save_recording": save_recording` to the state.
- If `spawn_streamer` fails, delete the partial WAV so `recordings_dir` only holds real sessions. The `AudioError` path from `start_recording` gets the same unlink as a guard, since it currently raises before any file exists.

**S4. Batch stop** (`cli.py`, `_stop_command`)
- In the `finally` block, delete the file only when `not state.get("save_recording")`.
- History metadata: include `audio_path` only when the recording is kept and the file exists. This fixes the dangling path.
- With `-v`, print `Recording saved: <path>`.
- Result: a failed transcription keeps its audio, ready for a retry.

**S5. Streaming** (`streamer.py`, `cli.py`)
- `spawn_streamer(backend, language, config, recording_path=None)`. The path must be absolute because the daemon runs `chdir("/")`; `resolve_recordings_dir` already returns an absolute path.
- In `_daemon_main`, when `recording_path` is set, open a `wave` writer (mono, 16-bit, 16 kHz) and call `writeframes(data)` on every audio read, including the finalize drain.
- Close the writer right after the drain, before tail transcription and the ydotool drain, so the file is final as soon as capture ends. `writeframes` rewrites the WAV header after each write, so the file stays playable even if `signal_finalize` SIGKILLs the daemon on timeout.
- A recording failure never stops dictation. If the writer fails to open or a write raises, the daemon logs it, drops the writer, and keeps transcribing and typing.
- On cancel, the daemon closes the writer. `_cancel_command` deletes the file.
- Streaming state gains `audio_path` (or `None`) and `save_recording`. `_stop_streaming` adds `audio_path` to history metadata only when the file exists.

**S6. Cancel** (`cli.py`, `_cancel_command`)
- Batch: the existing delete already covers the new path.
- Streaming: after `signal_cancel`, delete `state["audio_path"]` if it is set.

**S7. Repo hygiene and docs**
- `.gitignore`: add `data/recordings`.
- `config/openwhisper.toml.example`: new "Recordings" block with both keys, the size figure, and a line saying there is no automatic pruning.
- `docs/usage.md`: "Recordings" section next to "History Output".
- `AGENT.md`: add `data/recordings/` to Key Paths.

**S8. Tests** (`tests/test_recordings.py`, same stubbing style as `test_cli_autotype.py`)
| Code | Case |
|---|---|
| T1 | `load_config` defaults: flag off, dir under `data/recordings` |
| T2 | `resolve_recordings_dir`: a relative path resolves against `REPO_ROOT`, an absolute path is unchanged |
| T3 | Batch start with the flag on: `start_recording` gets a path in `recordings_dir`, and state has `save_recording=True` |
| T4 | Batch start with the flag off: path in `data/tmp`, `save_recording=False` |
| T5 | Batch stop, flag on, `run_whisper` raises `WhisperError`: file still exists and state is cleared |
| T6 | Batch stop, flag off: file deleted (regression guard) |
| T7 | History metadata has `audio_path` when the file is kept and no `audio_path` key otherwise |
| T8 | Batch cancel with the flag on: file deleted |
| T9 | Streaming start passes `recording_path` to a stubbed `spawn_streamer` |
| T10 | Collision: an existing path gets the `-1` suffix |

The daemon's write-to-file logic forks, so it gets manual checks (M3, M4), not unit tests.

## Manual Validation
| Code | Check |
|---|---|
| M1 | Flag on, batch `start` then `stop`: the WAV is in `data/recordings`, `soxi` duration matches the speech, and history `metadata.json` points at it |
| M2 | Flag on, broken `whisper_model_path`: `stop` fails and the WAV is kept |
| M3 | Flag on, `--auto-type --stream`: the WAV covers the whole session, not only the last 1 MB, and plays cleanly |
| M4 | Streaming `cancel`: no WAV left behind |
| M5 | Flag off: `data/recordings` is never created, and `data/tmp` is empty after `stop` |

## Risks
| Code | Risk | Mitigation |
|---|---|---|
| R1 | Unbounded disk use: 32 KB/s, about 115 MB per hour of dictation | Default off, size documented in the example config. Pruning (`recordings_max_age_days` or similar) is a follow-up. |
| R2 | Voice audio stored in plaintext | Dir created `0o700`, gitignored, opt-in |
| R3 | A crash or reboot before `stop` leaves a WAV with a stale header in `recordings_dir` | Same failure already happens in `data/tmp` today. Most tools (`sox`, `ffmpeg`) still read such files. |
| R4 | Recording into a slow or network `recordings_dir` could drop samples | Documented. The default stays on the local repo disk. |

## Non-goals
- Pruning or retention policy.
- Compression (FLAC/Opus).
- Saving audio from pronunciation exercises (D6).
- A CLI flag (D5).
