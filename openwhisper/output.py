from __future__ import annotations

import subprocess
import time
from pathlib import Path
from shutil import which


class OutputError(RuntimeError):
    pass


def copy_to_clipboard(text: str) -> None:
    if which("dbus-send") is None:
        raise OutputError("Missing dbus-send.")

    args = [
        "dbus-send",
        "--type=method_call",
        "--dest=org.kde.klipper",
        "/klipper",
        "org.kde.klipper.klipper.setClipboardContents",
        f"string:{text}",
    ]
    proc = subprocess.run(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if proc.returncode != 0:
        raise OutputError("Clipboard command failed.")


def copy_to_clipboard_wl(text: str) -> None:
    if which("wl-copy"):
        proc = subprocess.run(["wl-copy"], input=text, text=True)
    elif which("xclip"):
        proc = subprocess.run(
            ["xclip", "-selection", "clipboard"], input=text, text=True
        )
    else:
        raise OutputError("Missing clipboard tool: wl-copy or xclip.")

    if proc.returncode != 0:
        raise OutputError("Clipboard command failed.")


def notify_clipboard_copied() -> None:
    if which("dbus-send") is None:
        return

    args = [
        "dbus-send",
        "--session",
        "--dest=org.freedesktop.Notifications",
        "--type=method_call",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications.Notify",
        'string:"OpenWhisper"',
        "uint32:0",
        'string:""',
        'string:"OpenWhisper"',
        'string:"Copied to clipboard."',
        "array:string:",
        "dict:string:variant:",
        "int32:5000",
    ]
    subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_output(text: str, output_path: Path | None) -> None:
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text)


def type_via_ydotool(text: str, binary: str, key_delay_ms: int, focus_delay_ms: int) -> None:
    if which(binary) is None:
        raise OutputError(f"ydotool not found on PATH: {binary}")

    if focus_delay_ms > 0:
        time.sleep(focus_delay_ms / 1000)

    proc = subprocess.run(
        [binary, "type", "--file", "-", "--escape=0", "--key-delay", str(key_delay_ms)],
        input=text.rstrip("\n"),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if not err:
            err = f"returncode {proc.returncode}"
        raise OutputError(f"ydotool type failed: {err}")
