from pathlib import Path

import pytest

from openwhisper.pronunciation import transcribe as transcribe_mod
from openwhisper.pronunciation.transcribe import TranscribeError, transcribe_audio


@pytest.fixture
def whisper_config(tmp_path):
    cli = tmp_path / "whisper-cli"
    cli.write_text("#!/bin/sh\n")
    cli.chmod(0o755)
    model = tmp_path / "model.bin"
    model.write_bytes(b"")
    return {
        "whisper_cli_path": str(cli),
        "whisper_model_path": str(model),
    }


@pytest.fixture
def parakeet_config(tmp_path):
    model_dir = tmp_path / "parakeet"
    model_dir.mkdir()
    for name in (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ):
        (model_dir / name).write_bytes(b"")
    return {
        "parakeet_model_dir": str(model_dir),
        "parakeet_num_threads": 2,
    }


def test_dispatch_whisper(monkeypatch, whisper_config, tmp_path):
    called = {}

    def fake_run_whisper(audio_path, model, language, cli_path):
        called["backend"] = "whisper"
        called["language"] = language
        called["cli_path"] = cli_path
        return "hello world", "en"

    monkeypatch.setattr(transcribe_mod, "run_whisper", fake_run_whisper)
    transcript, detected = transcribe_audio(
        tmp_path / "a.wav", "whisper", whisper_config
    )
    assert transcript == "hello world"
    assert detected == "en"
    assert called["backend"] == "whisper"
    assert called["language"] == "en"


def test_dispatch_parakeet(monkeypatch, parakeet_config, tmp_path):
    called = {}

    def fake_run_parakeet(audio_path, model_dir, language, num_threads):
        called["backend"] = "parakeet"
        called["num_threads"] = num_threads
        return "bonjour", None

    monkeypatch.setattr(transcribe_mod, "run_parakeet", fake_run_parakeet)
    transcript, detected = transcribe_audio(
        tmp_path / "a.wav", "parakeet", parakeet_config
    )
    assert transcript == "bonjour"
    assert detected is None
    assert called["backend"] == "parakeet"
    assert called["num_threads"] == 2


def test_dispatch_unsupported_backend():
    with pytest.raises(TranscribeError):
        transcribe_audio(Path("/tmp/a.wav"), "foo", {})


def test_dispatch_missing_whisper_model_surfaces_as_transcribe_error(tmp_path):
    cli = tmp_path / "whisper-cli"
    cli.write_text("")
    cli.chmod(0o755)
    config = {
        "whisper_cli_path": str(cli),
        "whisper_model_path": str(tmp_path / "missing-model.bin"),
    }
    with pytest.raises(TranscribeError) as exc:
        transcribe_audio(tmp_path / "a.wav", "whisper", config)
    assert "whisper_model_path" in str(exc.value)


def test_dispatch_missing_parakeet_files_surfaces_as_transcribe_error(tmp_path):
    model_dir = tmp_path / "parakeet"
    model_dir.mkdir()
    config = {"parakeet_model_dir": str(model_dir)}
    with pytest.raises(TranscribeError) as exc:
        transcribe_audio(tmp_path / "a.wav", "parakeet", config)
    assert "encoder.int8.onnx" in str(exc.value)
