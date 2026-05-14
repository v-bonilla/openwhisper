from __future__ import annotations

import errno
import json
import os
import signal
import sys
import time
import wave
from pathlib import Path
from typing import Optional

from .config import REPO_ROOT

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # s16le mono
BYTES_PER_SECOND = SAMPLE_RATE * BYTES_PER_SAMPLE

TMP_DIR = REPO_ROOT / "data" / "tmp"

# Sentinel finalize / cancel commands written to control FIFO.
CMD_FINALIZE = "finalize"
CMD_CANCEL = "cancel"


def fifo_path() -> Path:
    return TMP_DIR / "stream.fifo"


def result_path() -> Path:
    return TMP_DIR / "stream-result.txt"


def log_path() -> Path:
    return TMP_DIR / "stream.log"


def ready_path() -> Path:
    return TMP_DIR / "stream-ready"


def _cleanup_paths() -> None:
    for p in (fifo_path(), result_path(), log_path(), ready_path()):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def _read_pid_start_time(pid: int) -> Optional[int]:
    """Return /proc/<pid>/stat field 22 (start_time in jiffies) or None."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
    except (FileNotFoundError, PermissionError):
        return None
    # Field 2 is "(comm)" which may contain spaces / parens; split after the
    # closing ')'.
    rparen = data.rfind(b")")
    if rparen < 0:
        return None
    fields = data[rparen + 2 :].split()
    # After comm, fields start at index 0 = state. start_time is field 22 in
    # the man page (1-indexed including pid+comm), which after our split is
    # index 19 (we dropped pid and comm).
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        return None


def _proc_alive(pid: int, start_time: Optional[int]) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours
    if start_time is None:
        return True
    return _read_pid_start_time(pid) == start_time


def spawn_streamer(
    backend: str,
    language: str,
    config: dict,
) -> dict:
    """Double-fork a detached streamer daemon. Return a dict with the
    streamer metadata to merge into the recording state file.

    Blocks up to ~3s waiting for the daemon to write its ready file. Raises
    RuntimeError if the daemon fails to come up.
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_paths()

    fifo = fifo_path()
    os.mkfifo(fifo, 0o600)

    # First fork.
    pid = os.fork()
    if pid > 0:
        # Original parent: wait on intermediate child (which exits after the
        # second fork), then poll for the ready file.
        os.waitpid(pid, 0)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if ready_path().exists():
                ready_data = json.loads(ready_path().read_text())
                return ready_data
            time.sleep(0.05)
        raise RuntimeError("Streamer daemon failed to come up within 3s.")

    # Intermediate child: setsid then second fork.
    try:
        os.setsid()
    except OSError:
        os._exit(1)
    pid2 = os.fork()
    if pid2 > 0:
        os._exit(0)

    # Daemon (grandchild).
    try:
        _daemon_main(backend, language, dict(config))
    except SystemExit:
        raise
    except BaseException as exc:  # pragma: no cover - last-resort log
        try:
            with log_path().open("a") as f:
                f.write(f"daemon fatal: {type(exc).__name__}: {exc}\n")
        except Exception:
            pass
        os._exit(1)
    os._exit(0)


def _daemon_main(backend: str, language: str, config: dict) -> None:
    # Detach from terminal: redirect std fds.
    os.chdir("/")
    devnull = os.open(os.devnull, os.O_RDWR)
    logf = os.open(str(log_path()), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.dup2(devnull, 0)
    os.dup2(logf, 1)
    os.dup2(logf, 2)
    if devnull > 2:
        os.close(devnull)
    if logf > 2:
        os.close(logf)

    def log(msg: str) -> None:
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        sys.stderr.flush()

    # Imports deferred until inside the daemon (faster parent startup, and
    # avoids loading heavy modules in the failure path).
    import selectors
    import subprocess
    from .audio import start_raw_pcm_capture
    from .constants import BACKEND_PARAKEET, BACKEND_WHISPER
    from .diff import compute_suffix
    from .output import start_ydotool_typing
    from .parakeet import ParakeetError, run_parakeet
    from .whisper import WhisperError, run_whisper

    daemon_pid = os.getpid()
    start_time = _read_pid_start_time(daemon_pid)
    log(f"daemon pid={daemon_pid} start_time={start_time}")

    chunk_seconds = float(config.get("auto_type_chunk_seconds", 4.0))
    overlap_seconds = float(config.get("auto_type_overlap_seconds", 0.8))
    chunk_bytes = int(chunk_seconds * BYTES_PER_SECOND) & ~1
    overlap_bytes = int(overlap_seconds * BYTES_PER_SECOND) & ~1
    advance_bytes = chunk_bytes - overlap_bytes
    if advance_bytes <= 0:
        log("invalid chunk/overlap config; using defaults")
        chunk_bytes = int(4.0 * BYTES_PER_SECOND)
        overlap_bytes = int(0.8 * BYTES_PER_SECOND)
        advance_bytes = chunk_bytes - overlap_bytes

    # Start audio capture.
    try:
        audio_proc = start_raw_pcm_capture(config.get("audio_device"))
    except Exception as exc:
        log(f"audio capture failed: {exc}")
        return

    # Start ydotool with stdin open.
    try:
        ydotool_proc = start_ydotool_typing(
            config.get("auto_type_binary", "ydotool"),
            int(config.get("auto_type_key_delay_ms", 0)),
            int(config.get("auto_type_key_hold_ms", 0)),
        )
    except Exception as exc:
        log(f"ydotool start failed: {exc}")
        _terminate_proc(audio_proc)
        return

    # Open control FIFO non-blocking. We must open the read end AFTER mkfifo.
    fifo_fd = os.open(str(fifo_path()), os.O_RDONLY | os.O_NONBLOCK)

    # Write the ready file so the parent unblocks.
    ready_payload = {
        "streamer_pid": daemon_pid,
        "streamer_start_time": start_time,
        "fifo_path": str(fifo_path()),
        "result_path": str(result_path()),
        "log_path": str(log_path()),
    }
    ready_tmp = ready_path().with_suffix(".tmp")
    ready_tmp.write_text(json.dumps(ready_payload))
    os.replace(ready_tmp, ready_path())

    selector = selectors.DefaultSelector()
    selector.register(audio_proc.stdout, selectors.EVENT_READ, "audio")
    selector.register(fifo_fd, selectors.EVENT_READ, "fifo")

    pcm = bytearray()
    chunk_start = 0
    committed = ""
    fifo_buf = b""
    cmd = None  # set to "finalize" or "cancel"
    ydotool_dead = False

    audio_eof = False
    log(f"loop starting; chunk={chunk_bytes}B overlap={overlap_bytes}B advance={advance_bytes}B")

    while True:
        events = selector.select(timeout=0.2)
        for key, _mask in events:
            tag = key.data
            if tag == "audio":
                try:
                    data = os.read(key.fd, 65536)
                except BlockingIOError:
                    data = b""
                if not data:
                    audio_eof = True
                    try:
                        selector.unregister(audio_proc.stdout)
                    except Exception:
                        pass
                else:
                    pcm.extend(data)
            elif tag == "fifo":
                try:
                    data = os.read(fifo_fd, 4096)
                except BlockingIOError:
                    data = b""
                if data:
                    fifo_buf += data
                    if b"\n" in fifo_buf:
                        line = fifo_buf.split(b"\n", 1)[0].decode(errors="replace").strip()
                        log(f"fifo cmd: {line!r}")
                        if line == CMD_FINALIZE:
                            cmd = CMD_FINALIZE
                        elif line == CMD_CANCEL:
                            cmd = CMD_CANCEL
                        else:
                            log(f"unknown fifo cmd: {line!r}")

        # Transcribe new chunks while we have enough buffered audio.
        while not cmd and (len(pcm) - chunk_start) >= chunk_bytes:
            end = chunk_start + chunk_bytes
            wav_path = TMP_DIR / f"stream-chunk-{daemon_pid}-{chunk_start}.wav"
            try:
                _write_wav(wav_path, bytes(pcm[chunk_start:end]))
            except Exception as exc:
                log(f"write chunk wav failed: {exc}")
                chunk_start += advance_bytes
                continue

            text = _transcribe(
                wav_path, backend, language, config,
                BACKEND_PARAKEET, BACKEND_WHISPER,
                run_parakeet, run_whisper,
                ParakeetError, WhisperError, log,
            )
            try:
                wav_path.unlink()
            except FileNotFoundError:
                pass

            if text:
                suffix = compute_suffix(committed, text)
                if suffix:
                    committed = (committed + suffix).rstrip() if committed else suffix.lstrip()
                    if not ydotool_dead:
                        try:
                            ydotool_proc.stdin.write(suffix)
                            ydotool_proc.stdin.flush()
                        except (BrokenPipeError, OSError) as exc:
                            log(f"ydotool write failed: {exc}; continuing capture")
                            ydotool_dead = True
            chunk_start += advance_bytes

        # Exit conditions.
        if cmd == CMD_CANCEL:
            log("cancel: aborting")
            _terminate_proc(audio_proc)
            try:
                if ydotool_proc.stdin and not ydotool_proc.stdin.closed:
                    ydotool_proc.stdin.close()
            except Exception:
                pass
            try:
                ydotool_proc.kill()
            except Exception:
                pass
            break

        if cmd == CMD_FINALIZE or audio_eof:
            log("finalize: draining audio")
            _terminate_proc(audio_proc)
            # Drain any remaining buffered bytes from the pipe.
            if not audio_eof:
                try:
                    while True:
                        data = audio_proc.stdout.read1(65536) if audio_proc.stdout else b""
                        if not data:
                            break
                        pcm.extend(data)
                except Exception:
                    pass
            # Transcribe the tail chunk (whatever's left after chunk_start).
            tail = bytes(pcm[chunk_start:])
            if len(tail) >= int(0.3 * BYTES_PER_SECOND):
                wav_path = TMP_DIR / f"stream-chunk-{daemon_pid}-tail.wav"
                try:
                    _write_wav(wav_path, tail)
                    text = _transcribe(
                        wav_path, backend, language, config,
                        BACKEND_PARAKEET, BACKEND_WHISPER,
                        run_parakeet, run_whisper,
                        ParakeetError, WhisperError, log,
                    )
                    wav_path.unlink(missing_ok=True)
                    if text:
                        suffix = compute_suffix(committed, text)
                        if suffix:
                            committed = (committed + suffix).rstrip() if committed else suffix.lstrip()
                            if not ydotool_dead:
                                try:
                                    ydotool_proc.stdin.write(suffix)
                                    ydotool_proc.stdin.flush()
                                except (BrokenPipeError, OSError) as exc:
                                    log(f"ydotool tail write failed: {exc}")
                                    ydotool_dead = True
                except Exception as exc:
                    log(f"tail transcribe failed: {exc}")
            # Close ydotool stdin and let it drain.
            try:
                if ydotool_proc.stdin and not ydotool_proc.stdin.closed:
                    ydotool_proc.stdin.close()
            except Exception:
                pass
            try:
                ydotool_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log("ydotool wait timed out; killing")
                ydotool_proc.kill()
            # Write the result file for the stop command.
            try:
                result_path().write_text(committed, encoding="utf-8")
            except Exception as exc:
                log(f"result write failed: {exc}")
            break

    log("daemon exiting")


def _write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(BYTES_PER_SAMPLE)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def _transcribe(
    wav_path: Path,
    backend: str,
    language: str,
    config: dict,
    BACKEND_PARAKEET: str,
    BACKEND_WHISPER: str,
    run_parakeet,
    run_whisper,
    ParakeetError,
    WhisperError,
    log,
) -> str:
    t0 = time.monotonic()
    try:
        if backend == BACKEND_PARAKEET:
            text, _ = run_parakeet(
                wav_path,
                config.get("parakeet_model_dir"),
                language,
                int(config.get("parakeet_num_threads", 4)),
            )
        else:
            text, _ = run_whisper(
                wav_path,
                config.get("whisper_model_path"),
                language,
                config.get("whisper_cli_path", "whisper-cli"),
            )
    except (ParakeetError, WhisperError) as exc:
        log(f"chunk transcribe failed: {exc}")
        return ""
    except Exception as exc:  # pragma: no cover - defensive
        log(f"chunk unexpected error: {type(exc).__name__}: {exc}")
        return ""
    dt = time.monotonic() - t0
    log(f"chunk {wav_path.name} -> {len(text)} chars in {dt:.2f}s")
    return text


def _terminate_proc(proc) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=0.5)
        return
    except Exception:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def signal_finalize(pid: int, start_time: Optional[int], timeout_s: float = 15.0) -> str:
    """Send 'finalize' to the daemon, wait up to ``timeout_s`` for it to
    exit, and return the typed transcript from the result file. Returns
    empty string if the daemon is gone or produced no result.
    """
    return _signal_and_wait(pid, start_time, CMD_FINALIZE, timeout_s, read_result=True)


def signal_cancel(pid: int, start_time: Optional[int], timeout_s: float = 5.0) -> None:
    _signal_and_wait(pid, start_time, CMD_CANCEL, timeout_s, read_result=False)


def _signal_and_wait(
    pid: int,
    start_time: Optional[int],
    cmd: str,
    timeout_s: float,
    read_result: bool,
) -> str:
    if not _proc_alive(pid, start_time):
        # Daemon already gone; honor result file if present.
        if read_result and result_path().exists():
            return result_path().read_text(encoding="utf-8")
        return ""

    # Open FIFO non-blocking for write, fall back to SIGTERM on ENXIO.
    fifo = fifo_path()
    wrote = False
    if fifo.exists():
        try:
            fd = os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, f"{cmd}\n".encode())
                wrote = True
            finally:
                os.close(fd)
        except OSError as exc:
            if exc.errno != errno.ENXIO:
                # ENXIO would mean no reader on the FIFO; any other errno
                # means something else is wrong but we'll still try signals.
                pass

    if not wrote:
        sig = signal.SIGTERM if cmd == CMD_FINALIZE else signal.SIGINT
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    # Poll for exit.
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _proc_alive(pid, start_time):
            break
        time.sleep(0.1)
    else:
        # Forceful termination.
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    if read_result:
        try:
            return result_path().read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
    return ""


def cleanup_artifacts() -> None:
    _cleanup_paths()
