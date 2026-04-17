from __future__ import annotations

import wave
from pathlib import Path


class ParakeetError(RuntimeError):
    pass


PARAKEET_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


_recognizer_cache: dict[tuple[str, int], object] = {}


def _load_recognizer(model_dir: Path, num_threads: int):
    try:
        import sherpa_onnx
    except ImportError as exc:
        raise ParakeetError(
            "sherpa-onnx is not installed. Install with: "
            "uv sync --extra parakeet"
        ) from exc

    key = (str(model_dir), num_threads)
    cached = _recognizer_cache.get(key)
    if cached is not None:
        return cached

    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(model_dir / "encoder.int8.onnx"),
        decoder=str(model_dir / "decoder.int8.onnx"),
        joiner=str(model_dir / "joiner.int8.onnx"),
        tokens=str(model_dir / "tokens.txt"),
        num_threads=num_threads,
        sample_rate=16000,
        feature_dim=80,
        decoding_method="greedy_search",
        model_type="nemo_transducer",
    )
    _recognizer_cache[key] = recognizer
    return recognizer


def _read_wav_mono_float32(audio_path: Path) -> tuple[object, int]:
    try:
        import numpy as np
    except ImportError as exc:
        raise ParakeetError(
            "numpy is not installed. Install with: uv sync --extra parakeet"
        ) from exc

    with wave.open(str(audio_path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())

    if sample_width != 2:
        raise ParakeetError(
            f"Expected 16-bit PCM WAV, got sample width {sample_width} bytes."
        )

    pcm = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
    samples = pcm.astype(np.float32) / 32768.0
    return samples, sample_rate


def run_parakeet(
    audio_path: Path,
    model_dir: str,
    language: str | None,
    num_threads: int = 4,
) -> tuple[str, str | None]:
    """Transcribe audio with Parakeet-TDT via sherpa-onnx.

    Returns (transcript, detected_language). Parakeet v3 auto-detects
    language internally but sherpa-onnx does not surface it, so
    detected is always None.
    """
    del language  # Parakeet does not accept a language hint.

    model_path = Path(model_dir)
    if not model_path.is_dir():
        raise ParakeetError(f"Parakeet model directory not found: {model_dir}")

    recognizer = _load_recognizer(model_path, num_threads)
    samples, sample_rate = _read_wav_mono_float32(audio_path)

    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, samples)
    recognizer.decode_stream(stream)
    transcript = (stream.result.text or "").strip()
    if not transcript:
        raise ParakeetError("Parakeet returned empty transcript.")

    return transcript, None
