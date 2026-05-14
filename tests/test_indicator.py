import subprocess

import pytest

from openwhisper import indicator


def _config(**overrides):
    cfg = {"indicator_enabled": True, "indicator_text": "● REC"}
    cfg.update(overrides)
    return cfg


def test_spawn_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    called = {"popen": False}

    def fake_popen(*a, **kw):
        called["popen"] = True
        raise AssertionError("Popen must not be called when disabled.")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    assert indicator.spawn_indicator(_config(indicator_enabled=False)) is None
    assert called["popen"] is False


def test_spawn_skips_without_wayland_display(monkeypatch, capsys):
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")

    def fake_popen(*a, **kw):
        raise AssertionError("Popen must not be called without WAYLAND_DISPLAY.")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    assert indicator.spawn_indicator(_config()) is None
    err = capsys.readouterr().err
    assert "WAYLAND_DISPLAY" in err


def test_spawn_returns_none_on_popen_failure(monkeypatch, capsys):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    def boom(*a, **kw):
        raise OSError("no exec")

    monkeypatch.setattr(subprocess, "Popen", boom)
    assert indicator.spawn_indicator(_config()) is None
    err = capsys.readouterr().err
    assert "indicator spawn failed" in err


def test_spawn_returns_pid_on_success(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    class FakeProc:
        pid = 999_999

    captured: dict = {}

    def fake_popen(argv, **kw):
        captured["argv"] = argv
        captured["env"] = kw.get("env")
        captured["start_new_session"] = kw.get("start_new_session")
        captured["close_fds"] = kw.get("close_fds")
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(indicator, "_read_pid_start_time", lambda pid: 12345)

    info = indicator.spawn_indicator(_config(indicator_text="hello"))
    assert info == {"indicator_pid": 999_999, "indicator_start_time": 12345}
    assert captured["argv"][0] == indicator.SYSTEM_PYTHON
    assert captured["argv"][1].endswith("indicator_app.py")
    assert captured["start_new_session"] is True
    assert captured["close_fds"] is True
    assert captured["env"]["OPENWHISPER_INDICATOR_TEXT"] == "hello"
    assert captured["env"]["OPENWHISPER_STATE_PATH"] == str(indicator.STATE_PATH)


def test_kill_indicator_none_is_noop(monkeypatch):
    def fail_kill(*a, **kw):
        raise AssertionError("os.kill must not be called for None pid.")

    monkeypatch.setattr("os.kill", fail_kill)
    indicator.kill_indicator(None, None)
    indicator.kill_indicator(0, None)
    indicator.kill_indicator(-1, 42)


def test_kill_indicator_swallows_missing_pid(monkeypatch):
    monkeypatch.setattr(indicator, "_read_pid_start_time", lambda pid: 42)

    def raise_lookup(*a, **kw):
        raise ProcessLookupError()

    monkeypatch.setattr("os.kill", raise_lookup)
    indicator.kill_indicator(12345, 42)  # must not raise


def test_kill_indicator_skips_on_start_time_mismatch(monkeypatch):
    monkeypatch.setattr(indicator, "_read_pid_start_time", lambda pid: 999)
    called = {"kill": False}

    def record_kill(*a, **kw):
        called["kill"] = True

    monkeypatch.setattr("os.kill", record_kill)
    indicator.kill_indicator(12345, 42)
    assert called["kill"] is False


def test_kill_indicator_signals_on_start_time_match(monkeypatch):
    monkeypatch.setattr(indicator, "_read_pid_start_time", lambda pid: 42)
    received: dict = {}

    def record_kill(pid, sig):
        received["pid"] = pid
        received["sig"] = sig

    monkeypatch.setattr("os.kill", record_kill)
    indicator.kill_indicator(12345, 42)
    assert received["pid"] == 12345


def test_kill_indicator_signals_when_start_time_unknown(monkeypatch):
    received: dict = {}

    def record_kill(pid, sig):
        received["pid"] = pid

    monkeypatch.setattr("os.kill", record_kill)
    indicator.kill_indicator(12345, None)
    assert received["pid"] == 12345
