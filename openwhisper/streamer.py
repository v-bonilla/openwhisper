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

CMD_FINALIZE = "finalize"
CMD_CANCEL = "cancel"

MIN_TAIL_SECONDS = 0.3
PCM_TRIM_THRESHOLD_BYTES = 1_000_000


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
    # comm (field 2) may contain spaces or parens; split after the closing ')'.
    rparen = data.rfind(b")")
    if rparen < 0:
        return None
    fields = data[rparen + 2 :].split()
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
    """Double-fork a detached streamer daemon. Return the streamer metadata
    to merge into the recording state file.

    Blocks up to ~3s waiting for the daemon to write its ready file. Raises
    RuntimeError if the daemon fails to come up.
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_paths()

    fifo = fifo_path()
    os.mkfifo(fifo, 0o600)

    pid = os.fork()
    if pid > 0:
        os.waitpid(pid, 0)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if ready_path().exists():
                return json.loads(ready_path().read_text())
            time.sleep(0.05)
        raise RuntimeError("Streamer daemon failed to come up within 3s.")

    try:
        os.setsid()
    except OSError:
        os._exit(1)
    pid2 = os.fork()
    if pid2 > 0:
        os._exit(0)

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

    # Imports deferred until inside the daemon: keeps parent startup snappy
    # and avoids loading heavy modules on the failure path.
    import selectors
    import subprocess
    from .audio import start_raw_pcm_capture
    from .diff import compute_suffix
    from .output import start_ydotool_typing

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

    try:
        audio_proc = start_raw_pcm_capture(config.get("audio_device"))
    except Exception as exc:
        log(f"audio capture failed: {exc}")
        return

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

    fifo_fd = os.open(str(fifo_path()), os.O_RDONLY | os.O_NONBLOCK)

    ready_payload = {
        "streamer_pid": daemon_pid,
        "streamer_start_time": start_time,
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
    cmd = None  # set to CMD_FINALIZE or CMD_CANCEL
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
                    while b"\n" in fifo_buf:
                        line, fifo_buf = fifo_buf.split(b"\n", 1)
                        decoded = line.decode(errors="replace").strip()
                        log(f"fifo cmd: {decoded!r}")
                        if decoded == CMD_FINALIZE:
                            cmd = CMD_FINALIZE
                        elif decoded == CMD_CANCEL:
                            cmd = CMD_CANCEL
                        else:
                            log(f"unknown fifo cmd: {decoded!r}")

        while not cmd and (len(pcm) - chunk_start) >= chunk_bytes:
            end = chunk_start + chunk_bytes
            chunk_pcm = bytes(pcm[chunk_start:end])
            committed, ydotool_dead = _emit_suffix(
                chunk_pcm,
                f"stream-chunk-{daemon_pid}-{chunk_start}.wav",
                backend, language, config,
                committed, ydotool_proc, ydotool_dead,
                compute_suffix, log,
            )
            chunk_start += advance_bytes
            if chunk_start > PCM_TRIM_THRESHOLD_BYTES:
                del pcm[:chunk_start]
                chunk_start = 0

        if cmd == CMD_CANCEL:
            log("cancel: aborting")
            _terminate_proc(audio_proc)
            _shutdown_ydotool(ydotool_proc, drain=False, timeout=0, subprocess=subprocess)
            break

        if cmd == CMD_FINALIZE or audio_eof:
            log("finalize: draining audio")
            _terminate_proc(audio_proc)
            if not audio_eof:
                try:
                    while True:
                        data = audio_proc.stdout.read1(65536) if audio_proc.stdout else b""
                        if not data:
                            break
                        pcm.extend(data)
                except Exception:
                    pass
            tail = bytes(pcm[chunk_start:])
            if len(tail) >= int(MIN_TAIL_SECONDS * BYTES_PER_SECOND):
                try:
                    committed, ydotool_dead = _emit_suffix(
                        tail,
                        f"stream-chunk-{daemon_pid}-tail.wav",
                        backend, language, config,
                        committed, ydotool_proc, ydotool_dead,
                        compute_suffix, log,
                    )
                except Exception as exc:
                    log(f"tail transcribe failed: {exc}")
            _shutdown_ydotool(ydotool_proc, drain=True, timeout=10, subprocess=subprocess, log=log)
            try:
                result_path().write_text(committed, encoding="utf-8")
            except Exception as exc:
                log(f"result write failed: {exc}")
            break

    log("daemon exiting")


def _emit_suffix(
    chunk_pcm: bytes,
    wav_name: str,
    backend: str,
    language: str,
    config: dict,
    committed: str,
    ydotool_proc,
    ydotool_dead: bool,
    compute_suffix,
    log,
) -> tuple[str, bool]:
    """Transcribe one PCM chunk, compute the new suffix, and type it.
    Returns updated (committed, ydotool_dead).
    """
    wav_path = TMP_DIR / wav_name
    try:
        _write_wav(wav_path, chunk_pcm)
    except Exception as exc:
        log(f"write chunk wav failed: {exc}")
        return committed, ydotool_dead

    text = _transcribe(wav_path, backend, language, config, log)
    try:
        wav_path.unlink()
    except FileNotFoundError:
        pass

    if not text:
        return committed, ydotool_dead

    suffix = compute_suffix(committed, text)
    if not suffix:
        return committed, ydotool_dead

    committed = (committed + suffix).rstrip() if committed else suffix.lstrip()
    if ydotool_dead:
        return committed, ydotool_dead
    try:
        ydotool_proc.stdin.write(suffix)
        ydotool_proc.stdin.flush()
    except (BrokenPipeError, OSError) as exc:
        log(f"ydotool write failed: {exc}; continuing capture")
        ydotool_dead = True
    return committed, ydotool_dead


def _shutdown_ydotool(proc, *, drain: bool, timeout: float, subprocess, log=None) -> None:
    """Close ydotool stdin and reap the process. ``drain=True`` waits up to
    ``timeout`` seconds for ydotool to flush queued keystrokes; otherwise
    kill immediately.
    """
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    except Exception:
        pass
    if not drain:
        try:
            proc.kill()
        except Exception:
            pass
        return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if log:
            log("ydotool wait timed out; killing")
        proc.kill()


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
    log,
) -> str:
    from .constants import BACKEND_PARAKEET, BACKEND_WHISPER
    from .parakeet import ParakeetError, run_parakeet
    from .whisper import WhisperError, run_whisper

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
        if read_result and result_path().exists():
            return result_path().read_text(encoding="utf-8")
        return ""

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
                pass

    if not wrote:
        sig = signal.SIGTERM if cmd == CMD_FINALIZE else signal.SIGINT
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _proc_alive(pid, start_time):
            break
        time.sleep(0.1)
    else:
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
