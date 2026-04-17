from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class PairsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pair:
    word: str
    partner: str
    category: str


def load_pairs(path: Path) -> list[Pair]:
    if not path.exists():
        raise PairsError(f"Pairs file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PairsError(f"Pairs file is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise PairsError("Pairs file must be a JSON array.")

    pairs: list[Pair] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise PairsError(f"Pairs entry {index} must be an object.")
        try:
            word = entry["word"]
            partner = entry["partner"]
            category = entry["category"]
        except KeyError as exc:
            raise PairsError(f"Pairs entry {index} missing field {exc}.") from exc
        if not (
            isinstance(word, str)
            and isinstance(partner, str)
            and isinstance(category, str)
        ):
            raise PairsError(f"Pairs entry {index} has non-string fields.")
        if not word or not partner or not category:
            raise PairsError(f"Pairs entry {index} has empty fields.")
        key = (word, partner)
        if key in seen:
            raise PairsError(f"Duplicate pair: ({word}, {partner}).")
        seen.add(key)
        pairs.append(Pair(word=word, partner=partner, category=category))
    return pairs


def filter_pairs(pairs: list[Pair], category: str | None) -> list[Pair]:
    if category is None:
        return list(pairs)
    return [pair for pair in pairs if pair.category == category]


def find_pair_by_word(pairs: list[Pair], word: str) -> Pair | None:
    target = word.lower()
    for pair in pairs:
        if pair.word.lower() == target:
            return pair
    return None


def list_categories(pairs: list[Pair]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for pair in pairs:
        if pair.category not in seen:
            seen.add(pair.category)
            result.append(pair.category)
    return result
