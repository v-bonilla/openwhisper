import io
import subprocess

import pytest

from openwhisper.output import OutputError, start_ydotool_typing


class FakePopen:
    def __init__(self, argv, *, stdin=None, stdout=None, stderr=None, text=None, **kwargs):
        self.argv = argv
        self.kwargs = {
            "stdin": stdin,
            "stdout": stdout,
            "stderr": stderr,
            "text": text,
            **kwargs,
        }
        self.stdin = io.StringIO()
        self.stderr = io.StringIO()
        self.returncode = 0


def _patch_popen(monkeypatch):
    created: dict = {}

    def fake_popen(argv, **kwargs):
        proc = FakePopen(argv, **kwargs)
        created["proc"] = proc
        return proc

    monkeypatch.setattr("openwhisper.output.subprocess.Popen", fake_popen)
    return created


def _patch_which_found(monkeypatch, path="/usr/bin/ydotool"):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: path)


def test_start_invokes_popen_with_expected_args(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(monkeypatch)

    proc = start_ydotool_typing("ydotool", 0, 0)

    assert created["proc"] is proc
    assert proc.argv == [
        "ydotool",
        "type",
        "--file",
        "-",
        "--escape=0",
        "--key-delay",
        "0",
        "--key-hold",
        "0",
    ]
    assert proc.kwargs["stdin"] is subprocess.PIPE
    assert proc.kwargs["stdout"] is subprocess.DEVNULL
    assert proc.kwargs["stderr"] is subprocess.PIPE
    assert proc.kwargs["text"] is True


def test_start_forwards_key_delay_and_hold(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(monkeypatch)

    start_ydotool_typing("ydotool", 50, 7)

    argv = created["proc"].argv
    assert argv[argv.index("--key-delay") + 1] == "50"
    assert argv[argv.index("--key-hold") + 1] == "7"


def test_start_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: None)

    with pytest.raises(OutputError) as exc:
        start_ydotool_typing("ydotool", 0, 0)
    assert "ydotool not found" in str(exc.value)


def test_start_accepts_custom_binary(monkeypatch):
    which_calls: list[str] = []

    def fake_which(binary):
        which_calls.append(binary)
        return "/opt/bin/my-ydotool"

    monkeypatch.setattr("openwhisper.output.which", fake_which)
    created = _patch_popen(monkeypatch)

    start_ydotool_typing("my-ydotool", 0, 0)

    assert which_calls == ["my-ydotool"]
    assert created["proc"].argv[0] == "my-ydotool"
