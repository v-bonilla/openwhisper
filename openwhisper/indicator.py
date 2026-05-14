"""Floating recording indicator — spawn/kill of the GTK4 layer-shell subprocess.

The GUI code lives in ``indicator_app``; this module is pure-Python so the CLI
can import it without dragging in PyGObject.

The indicator subprocess runs under the **system** Python interpreter
(``/usr/bin/python3``), not the uv venv interpreter. PyGObject + the
``Gtk4LayerShell`` typelib are installed via Debian packages, and uv venvs are
isolated from system site-packages by default; running the indicator under the
system Python is the cleanest way to give it access to ``gi`` without bleeding
system packages into the venv (which would risk shadowing pinned deps).

Lifecycle anchors in the child: explicit SIGTERM (handled via
``GLib.unix_signal_add``) and ``GLib.FileMonitor`` on the state file
(quits on DELETED/MOVED).

Public API:
    spawn_indicator(config) -> dict | None
    kill_indicator(pid, start_time) -> None
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .state import STATE_PATH

INDICATOR_APP_PATH = Path(__file__).resolve().parent / "indicator_app.py"
SYSTEM_PYTHON = "/usr/bin/python3"


def _read_pid_start_time(pid: int) -> Optional[int]:
    """Return /proc/<pid>/stat field 22 (start_time in jiffies) or None."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
    except (FileNotFoundError, PermissionError):
        return None
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


def spawn_indicator(config: dict) -> Optional[dict]:
    """Spawn the indicator subprocess. Return PID+start_time on success.

    Returns ``None`` (and logs a one-line stderr warning when relevant) if:
      - ``indicator_enabled`` is False in config
      - ``WAYLAND_DISPLAY`` is unset (layer-shell is Wayland-only)
      - ``/usr/bin/python3`` is missing
      - Popen raises
    Never raises — recording must continue regardless.
    """
    if not config.get("indicator_enabled", True):
        return None
    if not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "openwhisper: indicator skipped (WAYLAND_DISPLAY unset; "
            "layer-shell requires Wayland).",
            file=sys.stderr,
        )
        return None
    if not Path(SYSTEM_PYTHON).exists():
        print(
            f"openwhisper: indicator skipped ({SYSTEM_PYTHON} not found; "
            "system Python is needed for python3-gi).",
            file=sys.stderr,
        )
        return None

    env = os.environ.copy()
    env["OPENWHISPER_INDICATOR_TEXT"] = str(
        config.get("indicator_text", "● REC  openwhisper")
    )
    env["OPENWHISPER_STATE_PATH"] = str(STATE_PATH)
    argv = [SYSTEM_PYTHON, str(INDICATOR_APP_PATH)]
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=env,
        )
    except (OSError, ValueError) as exc:
        print(f"openwhisper: indicator spawn failed: {exc}", file=sys.stderr)
        return None

    return {
        "indicator_pid": proc.pid,
        "indicator_start_time": _read_pid_start_time(proc.pid),
    }


def kill_indicator(pid: Optional[int], start_time: Optional[int]) -> None:
    """SIGTERM the indicator. No-op on missing/dead PID. Never raises.

    Uses the ``/proc/<pid>/stat`` start_time check to defend against PID
    reuse: if the process at ``pid`` has a different start_time than recorded
    in state, we don't signal it.
    """
    if not pid or pid <= 0:
        return
    if start_time is not None:
        observed = _read_pid_start_time(pid)
        if observed is None or observed != start_time:
            return
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
