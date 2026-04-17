import pytest

from openwhisper.cli import validate_backend_requirements


def _make_whisper_config(tmp_path, *, cli_exists=True, model_exists=True):
    cli = tmp_path / "whisper-cli"
    if cli_exists:
        cli.write_text("#!/bin/sh\n")
        cli.chmod(0o755)
    model = tmp_path / "model.bin"
    if model_exists:
        model.write_bytes(b"")
    return {
        "whisper_cli_path": str(cli),
        "whisper_model_path": str(model),
    }


def _make_parakeet_config(tmp_path, *, missing=()):
    model_dir = tmp_path / "parakeet"
    model_dir.mkdir()
    for name in (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ):
        if name in missing:
            continue
        (model_dir / name).write_bytes(b"")
    return {"parakeet_model_dir": str(model_dir)}


def test_whisper_happy_path(tmp_path):
    validate_backend_requirements("whisper", _make_whisper_config(tmp_path))


def test_whisper_missing_cli(tmp_path):
    config = _make_whisper_config(tmp_path, cli_exists=False)
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements("whisper", config)
    assert "whisper_cli_path" in str(exc.value)


def test_whisper_missing_model(tmp_path):
    config = _make_whisper_config(tmp_path, model_exists=False)
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements("whisper", config)
    assert "whisper_model_path" in str(exc.value)


def test_whisper_unset_paths():
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements(
            "whisper", {"whisper_cli_path": None, "whisper_model_path": None}
        )
    assert "whisper_cli_path is not set" in str(exc.value)


def test_parakeet_happy_path(tmp_path):
    validate_backend_requirements("parakeet", _make_parakeet_config(tmp_path))


def test_parakeet_missing_dir():
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements(
            "parakeet", {"parakeet_model_dir": "/no/such/dir"}
        )
    assert "parakeet_model_dir" in str(exc.value)


def test_parakeet_unset_dir():
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements("parakeet", {"parakeet_model_dir": None})
    assert "parakeet_model_dir is not set" in str(exc.value)


def test_parakeet_missing_files(tmp_path):
    config = _make_parakeet_config(tmp_path, missing=("encoder.int8.onnx",))
    with pytest.raises(ValueError) as exc:
        validate_backend_requirements("parakeet", config)
    assert "encoder.int8.onnx" in str(exc.value)


def test_unsupported_backend():
    with pytest.raises(ValueError):
        validate_backend_requirements("bogus", {})
