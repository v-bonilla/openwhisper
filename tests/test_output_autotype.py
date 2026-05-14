import io
import subprocess

import pytest

from openwhisper.output import (
    OutputError,
    abort_ydotool_typing,
    finish_ydotool_typing,
    start_ydotool_typing,
    type_via_ydotool,
)


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
        self.stderr_buf = ""
        self.stderr = io.StringIO()
        self.returncode = 0
        self.communicate_input = None
        self.killed = False
        self._alive = True

    # The real Popen has stdin/stderr as real file objects; StringIO mimics
    # enough for our tests.
    def communicate(self, input=None, timeout=None):
        self.communicate_input = input
        self._alive = False
        return ("", self.stderr_buf)

    def wait(self, timeout=None):
        self._alive = False
        return self.returncode

    def poll(self):
        return None if self._alive else self.returncode

    def kill(self):
        self.killed = True
        self._alive = False


def _patch_popen(monkeypatch, *, returncode=0, stderr="", raise_on_communicate=None):
    created: dict = {}

    def fake_popen(argv, **kwargs):
        proc = FakePopen(argv, **kwargs)
        proc.returncode = returncode
        proc.stderr_buf = stderr
        if raise_on_communicate is not None:
            def communicate(input=None, timeout=None):
                proc.communicate_input = input
                proc._alive = False
                raise raise_on_communicate

            proc.communicate = communicate  # type: ignore[method-assign]
            # also let proc.stderr.read() return the stderr_buf after BrokenPipe
            proc.stderr = io.StringIO(stderr)
        created["proc"] = proc
        return proc

    monkeypatch.setattr("openwhisper.output.subprocess.Popen", fake_popen)
    return created


def _patch_which_found(monkeypatch, path="/usr/bin/ydotool"):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: path)


def test_happy_path(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(monkeypatch, returncode=0)

    type_via_ydotool("hello world\n", "ydotool", 0, 0, 0)

    proc = created["proc"]
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
    assert proc.communicate_input == "hello world"
    assert proc.kwargs["text"] is True
    assert proc.kwargs["stdin"] is subprocess.PIPE
    assert proc.kwargs["stdout"] is subprocess.DEVNULL
    assert proc.kwargs["stderr"] is subprocess.PIPE


def test_trailing_newline_only_stripped(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(monkeypatch, returncode=0)

    type_via_ydotool("line1\nline2\n", "ydotool", 20, 0)

    assert created["proc"].communicate_input == "line1\nline2"


def test_missing_binary_raises_and_no_popen(monkeypatch):
    monkeypatch.setattr("openwhisper.output.which", lambda binary: None)
    popen_calls: list = []

    def fake_popen(*args, **kwargs):
        popen_calls.append(args)
        raise AssertionError("Popen should not be called")

    monkeypatch.setattr("openwhisper.output.subprocess.Popen", fake_popen)

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    assert "ydotool not found on PATH" in str(exc.value)
    assert popen_calls == []


def test_nonzero_return_with_stderr(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=1, stderr="failed to connect to socket")

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    msg = str(exc.value)
    assert "ydotool type failed" in msg
    assert "failed to connect to socket" in msg


def test_nonzero_return_with_empty_stderr(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=2, stderr="")

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    msg = str(exc.value)
    assert "ydotool type failed" in msg
    assert "2" in msg


def test_broken_pipe_during_write_raises_output_error(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(
        monkeypatch,
        returncode=3,
        stderr="daemon gone",
        raise_on_communicate=BrokenPipeError(),
    )

    with pytest.raises(OutputError) as exc:
        type_via_ydotool("hi", "ydotool", 20, 0)

    msg = str(exc.value)
    assert "ydotool type failed" in msg
    assert "daemon gone" in msg
    assert created["proc"].communicate_input == "hi"


def test_focus_delay_applied(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=0)

    sleeps: list[float] = []
    monkeypatch.setattr("openwhisper.output.time.sleep", lambda s: sleeps.append(s))

    type_via_ydotool("hi", "ydotool", 20, 300)

    assert sleeps == [0.3]


def test_focus_delay_zero_no_sleep(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=0)

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
    created = _patch_popen(monkeypatch, returncode=0)

    type_via_ydotool("hi", "my-ydotool", 50, 0, 7)

    assert which_calls == ["my-ydotool"]
    argv = created["proc"].argv
    assert argv[0] == "my-ydotool"
    assert argv[argv.index("--key-delay") + 1] == "50"
    assert argv[argv.index("--key-hold") + 1] == "7"


def test_start_returns_running_process_without_writing(monkeypatch):
    _patch_which_found(monkeypatch)
    created = _patch_popen(monkeypatch, returncode=0)

    proc = start_ydotool_typing("ydotool", 0, 0)

    assert created["proc"] is proc
    # No input was written: communicate() was never called.
    assert proc.communicate_input is None
    assert proc.argv[:2] == ["ydotool", "type"]


def test_abort_kills_running_process_without_writing(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=0)

    proc = start_ydotool_typing("ydotool", 0, 0)
    abort_ydotool_typing(proc)

    assert proc.killed is True
    assert proc.communicate_input is None


def test_abort_is_safe_when_process_already_exited(monkeypatch):
    _patch_which_found(monkeypatch)
    _patch_popen(monkeypatch, returncode=0)

    proc = start_ydotool_typing("ydotool", 0, 0)
    # Drain via communicate so poll() returns the returncode.
    finish_ydotool_typing(proc, "hi", 0)

    # Should be a no-op (no kill of an already-exited process).
    abort_ydotool_typing(proc)
    assert proc.killed is False
