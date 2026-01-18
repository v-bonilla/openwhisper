from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime, timezone


def write_history(
    history_dir: Path,
    transcript: str,
    final_text: str,
    metadata: dict,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    entry_dir = history_dir / timestamp
    entry_dir.mkdir(parents=True, exist_ok=True)

    (entry_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    (entry_dir / "output.txt").write_text(final_text, encoding="utf-8")
    metadata_path = entry_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return entry_dir
