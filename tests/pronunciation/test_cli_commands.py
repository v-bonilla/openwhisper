"""Unit tests for the drill/shadow/pairs-list command dispatchers.

These avoid real audio/backends by monkeypatching the transcribe dispatcher
and skipping the record step via --audio-file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openwhisper import cli
from openwhisper.pronunciation import transcribe as transcribe_mod


@pytest.fixture
def pairs_file(tmp_path: Path) -> Path:
    path = tmp_path / "pairs.json"
    path.write_text(
        '[{"word":"sheep","partner":"ship","category":"i-ii"},'
        '{"word":"think","partner":"sink","category":"th-s"}]',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def paragraphs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "paragraphs"
    directory.mkdir()
    (directory / "p1.txt").write_text(
        "The sun rose over the quiet town.", encoding="utf-8"
    )
    return directory


@pytest.fixture
def audio_wav(tmp_path: Path) -> Path:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF\x00")
    return wav


@pytest.fixture
def stub_transcribe(monkeypatch):
    def install(result: str):
        def fake(audio_path, backend, config, language="en"):
            return result, "en"

        monkeypatch.setattr(
            transcribe_mod, "transcribe_audio", fake
        )
        # Also patch the import in cli.py's lazy import scope. Lazy imports
        # re-resolve against the module, so overriding the attribute works.
        import importlib

        mod = importlib.import_module("openwhisper.pronunciation.transcribe")
        monkeypatch.setattr(mod, "transcribe_audio", fake)

    return install


def _config(pairs_file: Path, paragraphs_dir: Path, history_dir: Path) -> dict:
    return {
        "transcription_backend": "whisper",
        "pronunciation_pairs_path": str(pairs_file),
        "pronunciation_paragraphs_dir": str(paragraphs_dir),
        "history_enabled": True,
        "history_dir": str(history_dir),
    }


def test_drill_audio_file_pass(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, stub_transcribe, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    stub_transcribe("sheep")

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "category": None,
            "count": 1,
            "audio_file": audio_wav,
            "target": "sheep",
        },
    )()
    code = cli._drill_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS" in out


def test_drill_audio_file_confused(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, stub_transcribe, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    stub_transcribe("ship")

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "category": None,
            "count": 1,
            "audio_file": audio_wav,
            "target": "sheep",
        },
    )()
    code = cli._drill_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "CONFUSED" in out
    assert '"ship"' in out


def test_drill_audio_file_missing_target_word(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, stub_transcribe, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    stub_transcribe("whatever")

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "category": None,
            "count": 1,
            "audio_file": audio_wav,
            "target": "elephant",
        },
    )()
    code = cli._drill_command(args, config)
    err = capsys.readouterr().err
    assert code == 1
    assert "not found" in err


def test_drill_audio_file_requires_target(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "category": None,
            "count": 1,
            "audio_file": audio_wav,
            "target": None,
        },
    )()
    code = cli._drill_command(args, config)
    err = capsys.readouterr().err
    assert code == 1
    assert "--target" in err


def test_shadow_audio_file_with_file(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, stub_transcribe, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)

    paragraph_file = tmp_path / "para.txt"
    paragraph_file.write_text("hello brave world", encoding="utf-8")
    stub_transcribe("hello world")

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "paragraph_id": None,
            "file": paragraph_file,
            "audio_file": audio_wav,
        },
    )()
    code = cli._shadow_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "Accuracy:" in out
    assert "brave" in out


def test_shadow_audio_file_with_id(
    tmp_path, pairs_file, paragraphs_dir, audio_wav, stub_transcribe, capsys
):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    stub_transcribe("the sun rose over the quiet town")

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "paragraph_id": "p1",
            "file": None,
            "audio_file": audio_wav,
        },
    )()
    code = cli._shadow_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "Accuracy:" in out


def test_shadow_requires_source(tmp_path, pairs_file, paragraphs_dir, audio_wav, capsys):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)

    args = type(
        "Args",
        (),
        {
            "backend": None,
            "paragraph_id": None,
            "file": None,
            "audio_file": audio_wav,
        },
    )()
    code = cli._shadow_command(args, config)
    err = capsys.readouterr().err
    assert code == 1
    assert "paragraph id" in err or "file" in err


def test_pairs_list(tmp_path, pairs_file, paragraphs_dir, capsys):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    args = type("Args", (), {"category": None})()
    code = cli._pairs_list_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "sheep" in out
    assert "ship" in out
    assert "i-ii:" in out


def test_pairs_list_category_filter(tmp_path, pairs_file, paragraphs_dir, capsys):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    args = type("Args", (), {"category": "i-ii"})()
    code = cli._pairs_list_command(args, config)
    out = capsys.readouterr().out
    assert code == 0
    assert "sheep" in out
    assert "think" not in out


def test_pairs_list_missing_category(tmp_path, pairs_file, paragraphs_dir, capsys):
    history_dir = tmp_path / "history"
    config = _config(pairs_file, paragraphs_dir, history_dir)
    args = type("Args", (), {"category": "zz"})()
    code = cli._pairs_list_command(args, config)
    err = capsys.readouterr().err
    assert code == 1
    assert "zz" in err
