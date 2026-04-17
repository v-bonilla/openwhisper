from __future__ import annotations

from pathlib import Path


class ParagraphError(RuntimeError):
    pass


def load_paragraph_by_id(paragraphs_dir: Path, paragraph_id: str) -> str:
    if not paragraph_id:
        raise ParagraphError("Paragraph id is empty.")
    path = paragraphs_dir / f"{paragraph_id}.txt"
    if not path.exists():
        raise ParagraphError(f"Paragraph not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ParagraphError(f"Paragraph is empty: {path}")
    return text


def load_paragraph_from_file(path: Path) -> str:
    if not path.exists():
        raise ParagraphError(f"Paragraph file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ParagraphError(f"Paragraph file is empty: {path}")
    return text


def list_paragraph_ids(paragraphs_dir: Path) -> list[str]:
    if not paragraphs_dir.is_dir():
        return []
    return sorted(path.stem for path in paragraphs_dir.glob("*.txt"))
