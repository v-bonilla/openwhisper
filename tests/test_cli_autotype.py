import sys


from openwhisper.cli import _parse_args, _start_command
from openwhisper.constants import MODE_VOICE


def test_start_auto_type_flag_parses_true(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["openwhisper", "start", "--auto-type"])
    args = _parse_args()
    assert args.command == "start"
    assert args.auto_type is True


def test_start_without_auto_type_defaults_false(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["openwhisper", "start"])
    args = _parse_args()
    assert args.command == "start"
    assert args.auto_type is False


def _autotype_args(**overrides):
    """Return a namespace with the args _start_command reads."""
    import argparse
    ns = argparse.Namespace(
        command="start",
        mode=overrides.get("mode", MODE_VOICE),
        language=overrides.get("language", "en"),
        translate=overrides.get("translate"),
        backend=overrides.get("backend", "whisper"),
        no_clipboard=False,
        no_history=False,
        auto_type=True,
        output=None,
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


def test_auto_type_rejects_non_voice_mode(monkeypatch, capsys):
    # load_state raises StateError -> _start_command proceeds.
    args = _autotype_args(mode="email")
    config = _base_config()
    rc = _start_command(args, config)
    err = capsys.readouterr().err
    assert rc == 1
    assert "voice mode" in err


def test_auto_type_rejects_translate(capsys):
    args = _autotype_args(translate="es")
    config = _base_config()
    rc = _start_command(args, config)
    err = capsys.readouterr().err
    assert rc == 1
    assert "translate" in err.lower()


def test_auto_type_rejects_missing_language(capsys):
    args = _autotype_args(language=None)
    config = _base_config()
    rc = _start_command(args, config)
    err = capsys.readouterr().err
    assert rc == 1
    assert "language" in err.lower()
