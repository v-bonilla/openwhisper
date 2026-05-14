from subprocess import CompletedProcess

import pytest

from openwhisper.output import OutputError, type_via_ydotool


def _make_run_recorder(returncode=0, stderr=""):
    calls = {}

    def fake_run(argv, input=None, text=None, capture_output=None, **kwargs):
        calls["argv"] = argv
        calls["input"] = input
        calls["text"] = text
        calls["capture_output"] = capture_output
        calls["kwargs"] = kwargs
        return CompletedProcess(args=argv, returncode=returncode, stdout="", stderr=stderr)

    return fake_run, calls


def _patch_which_found(monkeypatch, path="/usr/bin/ydotool"):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: path)


def test_happy_path(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, calls = _make_run_recorder(returncode=0)
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    type_via_ydotool("hello world\n", "ydotool", 20, 0)

    assert calls["argv"] == [
        "ydotool",
        "type",
        "--file",
        "-",
        "--escape=0",
        "--key-delay",
        "20",
    ]
    assert calls["input"] == "hello world"
    assert calls["text"] is True
    assert calls["capture_output"] is True


def test_trailing_newline_only_stripped(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, calls = _make_run_recorder(returncode=0)
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    type_via_ydotool("line1\nline2\n", "ydotool", 20, 0)

    assert calls["input"] == "line1\nline2"


def test_missing_binary_raises_and_no_subprocess(monkeypatch):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: None)
    called = {"ran": False}

    def fake_run(*args, **kwargs):
        called["ran"] = True
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    assert "ydotool not found on PATH" in str(exc.value)
    assert called["ran"] is False


def test_nonzero_return_with_stderr(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, _ = _make_run_recorder(
        returncode=1, stderr="failed to connect to socket"
    )
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    msg = str(exc.value)
    assert "ydotool type failed" in msg
    assert "failed to connect to socket" in msg


def test_nonzero_return_with_empty_stderr(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, _ = _make_run_recorder(returncode=2, stderr="")
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    msg = str(exc.value)
    assert "ydotool type failed" in msg
    assert "2" in msg


def test_focus_delay_applied(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, _ = _make_run_recorder(returncode=0)
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    sleeps: list[float] = []
    monkeypatch.setattr("openwhisper.output.time.sleep", lambda s: sleeps.append(s))

    type_via_ydotool("hi", "ydotool", 20, 300)

    assert sleeps == [0.3]


def test_focus_delay_zero_no_sleep(monkeypatch):
    _patch_which_found(monkeypatch)
    fake_run, _ = _make_run_recorder(returncode=0)
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    sleeps: list[float] = []
    monkeypatch.setattr("openwhisper.output.time.sleep", lambda s: sleeps.append(s))

    type_via_ydotool("hi", "ydotool", 20, 0)

    assert sleeps == []


def test_custom_binary_name(monkeypatch):
    which_calls: list[str] = []

    def fake_which(binary):
        which_calls.append(binary)
        return "/opt/bin/my-ydotool"

    monkeypatch.setattr("openwhisper.output.which", fake_which)
    fake_run, calls = _make_run_recorder(returncode=0)
    monkeypatch.setattr("openwhisper.output.subprocess.run", fake_run)

    type_via_ydotool("hi", "my-ydotool", 50, 0)

    assert which_calls == ["my-ydotool"]
    assert calls["argv"][0] == "my-ydotool"
    assert calls["argv"][-2:] == ["--key-delay", "50"]
