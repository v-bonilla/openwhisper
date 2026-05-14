import argparse
import sys

from openwhisper.cli import _parse_args, _start_command
from openwhisper.constants import MODE_VOICE


def test_start_auto_type_flag_parses_true(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["openwhisper", "start", "--auto-type"])
    args = _parse_args()
    assert args.command == "start"
    assert args.auto_type is True
    assert args.stream is False


def test_start_without_auto_type_defaults_false(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["openwhisper", "start"])
    args = _parse_args()
    assert args.command == "start"
    assert args.auto_type is False
    assert args.stream is False


def test_start_stream_flag_parses(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["openwhisper", "start", "--auto-type", "--stream"])
    args = _parse_args()
    assert args.auto_type is True
    assert args.stream is True


def _start_args(**overrides):
    """Return a namespace with the args _start_command reads."""
    ns = argparse.Namespace(
        command="start",
        mode=overrides.get("mode", MODE_VOICE),
        language=overrides.get("language", "en"),
        translate=overrides.get("translate"),
        backend=overrides.get("backend", "whisper"),
        no_clipboard=False,
        no_history=False,
        auto_type=overrides.get("auto_type", True),
        stream=overrides.get("stream", True),
        output=None,
        verbose=overrides.get("verbose", False),
    )
    return ns


def _base_config(**overrides):
    cfg = {
        "default_mode": MODE_VOICE,
        "default_language": None,
        "transcription_backend": "whisper",
        "whisper_cli_path": "/usr/bin/true",
        "whisper_model_path": "memory",
        "auto_type_binary": "/usr/bin/true",
        "history_enabled": False,
        "clipboard_enabled": False,
    }
    cfg.update(overrides)
    return cfg


def test_stream_without_auto_type_is_rejected(capsys):
    args = _start_args(auto_type=False, stream=True)
    rc = _start_command(args, _base_config())
    err = capsys.readouterr().err
    assert rc == 1
    assert "--stream requires --auto-type" in err


def test_stream_rejects_non_voice_mode(capsys):
    args = _start_args(mode="email")
    rc = _start_command(args, _base_config())
    err = capsys.readouterr().err
    assert rc == 1
    assert "voice mode" in err


def test_stream_rejects_translate(capsys):
    args = _start_args(translate="es")
    rc = _start_command(args, _base_config())
    err = capsys.readouterr().err
    assert rc == 1
    assert "translate" in err.lower()


def test_stream_rejects_missing_language(capsys):
    args = _start_args(language=None)
    rc = _start_command(args, _base_config())
    err = capsys.readouterr().err
    assert rc == 1
    assert "language" in err.lower()


def test_auto_type_without_stream_allows_non_voice_mode(monkeypatch):
    """Batch auto-type should NOT inherit the stream validation rules."""
    # Stub out start_recording so we don't actually launch processes.
    calls: dict = {}

    class FakeRecording:
        pids = [12345]
        method = "fake"

    def fake_start_recording(path, device):
        calls["path"] = path
        return FakeRecording()

    monkeypatch.setattr("openwhisper.cli.start_recording", fake_start_recording)

    saved_state: dict = {}
    monkeypatch.setattr("openwhisper.cli.save_state", lambda s: saved_state.update(s))

    args = _start_args(auto_type=True, stream=False, mode="email", translate="es", language=None)
    config = _base_config()
    rc = _start_command(args, config)
    assert rc == 0
    assert saved_state["streaming"] is False
    assert saved_state["auto_type_enabled"] is True
    assert saved_state["mode"] == "email"
    assert saved_state["translate"] == "es"
