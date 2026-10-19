import argparse

import pytest

from openwhisper import cli, streamer
from openwhisper.audio import AudioError
from openwhisper.config import REPO_ROOT, load_config, resolve_recordings_dir
from openwhisper.constants import MODE_VOICE
from openwhisper.state import StateError
from openwhisper.whisper import WhisperError


def _start_args(**overrides):
    return argparse.Namespace(
        command="start",
        mode=MODE_VOICE,
        language="en",
        translate=None,
        backend="whisper",
        no_clipboard=False,
        no_history=False,
        auto_type=overrides.get("auto_type", False),
        stream=overrides.get("stream", False),
        no_indicator=True,
        output=None,
        verbose=False,
    )


def _config(tmp_path, **overrides):
    cfg = {
        "default_mode": MODE_VOICE,
        "transcription_backend": "whisper",
        "whisper_cli_path": "/usr/bin/true",
        "whisper_model_path": "memory",
        "auto_type_binary": "/usr/bin/true",
        "history_enabled": False,
        "clipboard_enabled": False,
        "recordings_enabled": True,
        "recordings_dir": str(tmp_path / "recordings"),
    }
    cfg.update(overrides)
    return cfg


class FakeRecording:
    pids = [12345]
    method = "fake"


@pytest.fixture
def start_stubs(monkeypatch):
    calls: dict = {}

    def fake_load_state():
        raise StateError("no state")

    def fake_start_recording(path, device):
        calls["path"] = path
        return FakeRecording()

    saved: dict = {}
    monkeypatch.setattr(cli, "load_state", fake_load_state)
    monkeypatch.setattr(cli, "start_recording", fake_start_recording)
    monkeypatch.setattr(cli, "save_state", lambda s: saved.update(s))
    return calls, saved


def _stop_stubs(monkeypatch, state, run_whisper):
    calls: dict = {"cleared": False, "history": []}
    monkeypatch.setattr(cli, "load_state", lambda: dict(state))
    monkeypatch.setattr(cli, "stop_recording", lambda pids: None)
    monkeypatch.setattr(cli, "kill_indicator", lambda pid, st: None)
    monkeypatch.setattr(cli, "run_whisper", run_whisper)
    monkeypatch.setattr(cli, "write_output", lambda text, path, verbose=False: None)
    monkeypatch.setattr(
        cli, "write_history", lambda d, t, x, m: calls["history"].append(m)
    )
    monkeypatch.setattr(cli, "clear_state", lambda: calls.__setitem__("cleared", True))
    return calls


def _batch_state(audio_path, save_recording, history_enabled=False):
    return {
        "streaming": False,
        "audio_path": str(audio_path),
        "pids": [12345],
        "mode": MODE_VOICE,
        "backend": "whisper",
        "language": "en",
        "translate": None,
        "clipboard_enabled": False,
        "auto_type_enabled": False,
        "history_enabled": history_enabled,
        "output_path": None,
        "save_recording": save_recording,
    }


def test_load_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr("openwhisper.config.CONFIG_PATH", tmp_path / "missing.toml")
    config = load_config()
    assert config["recordings_enabled"] is False
    assert config["recordings_dir"] == str(REPO_ROOT / "data" / "recordings")


def test_resolve_recordings_dir_relative_and_absolute(tmp_path):
    rel = resolve_recordings_dir({"recordings_dir": "./data/recordings"})
    assert rel == (REPO_ROOT / "data" / "recordings").resolve()
    assert resolve_recordings_dir({"recordings_dir": str(tmp_path)}) == tmp_path


def test_batch_start_flag_on_records_into_recordings_dir(start_stubs, tmp_path):
    calls, saved = start_stubs
    rc = cli._start_command(_start_args(), _config(tmp_path))
    assert rc == 0
    recordings_dir = tmp_path / "recordings"
    assert calls["path"].parent == recordings_dir
    assert recordings_dir.is_dir()
    assert (recordings_dir.stat().st_mode & 0o777) == 0o700
    assert saved["save_recording"] is True
    assert saved["audio_path"] == str(calls["path"])


def test_batch_start_flag_off_records_into_tmp(start_stubs, tmp_path):
    calls, saved = start_stubs
    rc = cli._start_command(_start_args(), _config(tmp_path, recordings_enabled=False))
    assert rc == 0
    assert calls["path"].parent == REPO_ROOT / "data" / "tmp"
    assert saved["save_recording"] is False
    assert not (tmp_path / "recordings").exists()


def test_batch_stop_whisper_error_keeps_file(monkeypatch, tmp_path):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF")

    def failing_whisper(*a, **k):
        raise WhisperError("boom")

    calls = _stop_stubs(monkeypatch, _batch_state(wav, True), failing_whisper)
    rc = cli._stop_command(argparse.Namespace(verbose=False), _config(tmp_path))
    assert rc == 1
    assert wav.exists()
    assert calls["cleared"] is True


def test_batch_stop_flag_off_deletes_file(monkeypatch, tmp_path):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF")
    calls = _stop_stubs(monkeypatch, _batch_state(wav, False), lambda *a, **k: ("hi", "en"))
    rc = cli._stop_command(argparse.Namespace(verbose=False), _config(tmp_path))
    assert rc == 0
    assert not wav.exists()
    assert calls["cleared"] is True


@pytest.mark.parametrize("save_recording", [True, False])
def test_history_metadata_audio_path(monkeypatch, tmp_path, capsys, save_recording):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF")
    calls = _stop_stubs(
        monkeypatch,
        _batch_state(wav, save_recording, history_enabled=True),
        lambda *a, **k: ("hi", "en"),
    )
    rc = cli._stop_command(argparse.Namespace(verbose=True), _config(tmp_path))
    assert rc == 0
    [metadata] = calls["history"]
    out = capsys.readouterr().out
    if save_recording:
        assert metadata["audio_path"] == str(wav)
        assert f"Recording saved: {wav}" in out
    else:
        assert "audio_path" not in metadata
        assert "Recording saved" not in out


def test_batch_cancel_flag_on_deletes_file(monkeypatch, tmp_path):
    wav = tmp_path / "recordings" / "recording.wav"
    wav.parent.mkdir()
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(cli, "load_state", lambda: _batch_state(wav, True))
    monkeypatch.setattr(cli, "stop_recording", lambda pids: None)
    monkeypatch.setattr(cli, "kill_indicator", lambda pid, st: None)
    monkeypatch.setattr(cli, "clear_state", lambda: None)
    assert cli._cancel_command() == 0
    assert not wav.exists()


def test_streaming_start_passes_recording_path(start_stubs, monkeypatch, tmp_path):
    _calls, saved = start_stubs
    spawn: dict = {}

    def fake_spawn(backend, language, config, recording_path=None):
        spawn["recording_path"] = recording_path
        return {"streamer_pid": 1, "streamer_start_time": 2}

    monkeypatch.setattr(cli.streamer, "spawn_streamer", fake_spawn)
    rc = cli._start_command(_start_args(auto_type=True, stream=True), _config(tmp_path))
    assert rc == 0
    path = spawn["recording_path"]
    assert path.is_absolute()
    assert path.parent == tmp_path / "recordings"
    assert saved["audio_path"] == str(path)
    assert saved["save_recording"] is True


def test_collision_appends_suffix(start_stubs, monkeypatch, tmp_path):
    calls, _saved = start_stubs

    class FixedDatetime:
        @staticmethod
        def now(tz=None):
            class Stamp:
                def strftime(self, fmt):
                    return "20260101-000000"
            return Stamp()

    monkeypatch.setattr(cli, "datetime", FixedDatetime)
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    (recordings_dir / "recording-20260101-000000.wav").write_bytes(b"RIFF")
    rc = cli._start_command(_start_args(), _config(tmp_path))
    assert rc == 0
    assert calls["path"] == recordings_dir / "recording-20260101-000000-1.wav"


def _streaming_state(audio_path, save_recording=True):
    return {
        "streaming": True,
        "mode": MODE_VOICE,
        "backend": "whisper",
        "language": "en",
        "history_enabled": True,
        "output_path": None,
        "audio_path": str(audio_path) if audio_path else None,
        "save_recording": save_recording,
        "streamer_pid": 1,
        "streamer_start_time": 2,
    }


def test_streaming_cancel_deletes_recording(monkeypatch, tmp_path):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(cli, "load_state", lambda: _streaming_state(wav))
    monkeypatch.setattr(cli, "kill_indicator", lambda pid, st: None)
    monkeypatch.setattr(cli, "clear_state", lambda: None)
    monkeypatch.setattr(cli.streamer, "signal_cancel", lambda pid, st: None)
    monkeypatch.setattr(cli.streamer, "cleanup_artifacts", lambda: None)
    assert cli._cancel_command() == 0
    assert not wav.exists()


@pytest.mark.parametrize("exists", [True, False])
def test_stop_streaming_history_audio_path(monkeypatch, tmp_path, exists):
    wav = tmp_path / "recording.wav"
    if exists:
        wav.write_bytes(b"RIFF")
    history: list = []
    monkeypatch.setattr(cli, "kill_indicator", lambda pid, st: None)
    monkeypatch.setattr(cli, "clear_state", lambda: None)
    monkeypatch.setattr(cli, "write_output", lambda text, path, verbose=False: None)
    monkeypatch.setattr(cli, "write_history", lambda d, t, x, m: history.append(m))
    monkeypatch.setattr(cli.streamer, "signal_finalize", lambda pid, st, timeout_s: "hi")
    monkeypatch.setattr(cli.streamer, "cleanup_artifacts", lambda: None)
    rc = cli._stop_streaming(_streaming_state(wav), _config(tmp_path), False)
    assert rc == 0
    [metadata] = history
    if exists:
        assert metadata["audio_path"] == str(wav)
    else:
        assert "audio_path" not in metadata


def test_streaming_start_flag_off_passes_no_recording_path(start_stubs, monkeypatch, tmp_path):
    _calls, saved = start_stubs
    spawn: dict = {}

    def fake_spawn(backend, language, config, recording_path=None):
        spawn["recording_path"] = recording_path
        return {"streamer_pid": 1, "streamer_start_time": 2}

    monkeypatch.setattr(cli.streamer, "spawn_streamer", fake_spawn)
    rc = cli._start_command(
        _start_args(auto_type=True, stream=True), _config(tmp_path, recordings_enabled=False)
    )
    assert rc == 0
    assert spawn["recording_path"] is None
    assert saved["audio_path"] is None
    assert saved["save_recording"] is False


def test_legacy_state_without_save_recording_deletes_file(monkeypatch, tmp_path):
    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"RIFF")
    state = _batch_state(wav, False)
    del state["save_recording"]
    _stop_stubs(monkeypatch, state, lambda *a, **k: ("hi", "en"))
    rc = cli._stop_command(argparse.Namespace(verbose=False), _config(tmp_path))
    assert rc == 0
    assert not wav.exists()


def test_start_recording_failure_leaves_no_file(start_stubs, monkeypatch, tmp_path):
    def failing_start(path, device):
        path.write_bytes(b"RIFF")
        raise AudioError("no mic")

    monkeypatch.setattr(cli, "start_recording", failing_start)
    rc = cli._start_command(_start_args(), _config(tmp_path))
    assert rc == 1
    assert list((tmp_path / "recordings").iterdir()) == []


def test_spawn_streamer_failure_leaves_no_file(start_stubs, monkeypatch, tmp_path):
    def failing_spawn(backend, language, config, recording_path=None):
        recording_path.write_bytes(b"RIFF")
        raise RuntimeError("daemon down")

    monkeypatch.setattr(cli.streamer, "spawn_streamer", failing_spawn)
    rc = cli._start_command(_start_args(auto_type=True, stream=True), _config(tmp_path))
    assert rc == 1
    assert list((tmp_path / "recordings").iterdir()) == []


class _FakeWriter:
    def __init__(self, fail=False):
        self.fail = fail
        self.frames = b""
        self.closed = False

    def writeframes(self, data):
        if self.fail:
            raise OSError("disk full")
        self.frames += data

    def close(self):
        self.closed = True


def test_record_frames_writes_and_disables_on_error():
    logs: list = []
    ok = _FakeWriter()
    assert streamer._record_frames(ok, b"ab", logs.append) is ok
    assert ok.frames == b"ab"
    bad = _FakeWriter(fail=True)
    assert streamer._record_frames(bad, b"ab", logs.append) is None
    assert bad.closed is True
    assert len(logs) == 1
    assert streamer._record_frames(None, b"ab", logs.append) is None
