from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which


class OutputError(RuntimeError):
    pass


def copy_to_clipboard(text: str) -> None:
    if which("wl-copy"):
        proc = subprocess.run(["wl-copy"], input=text, text=True)
    elif which("xclip"):
        proc = subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True)
    else:
        raise OutputError("Missing clipboard tool: wl-copy or xclip.")

    if proc.returncode != 0:
        raise OutputError("Clipboard command failed.")


def write_output(text: str, output_path: Path | None) -> None:
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text)
