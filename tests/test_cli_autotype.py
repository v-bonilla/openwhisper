import sys

from openwhisper.cli import _parse_args


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
