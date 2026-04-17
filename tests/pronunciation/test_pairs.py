import json
from pathlib import Path

import pytest

from openwhisper.config import REPO_ROOT
from openwhisper.pronunciation.pairs import (
    PairsError,
    filter_pairs,
    find_pair_by_word,
    list_categories,
    load_pairs,
)

SEED_PATH = REPO_ROOT / "data" / "pronunciation" / "minimal_pairs.json"


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_seed_file_loads():
    pairs = load_pairs(SEED_PATH)
    assert len(pairs) >= 40
    categories = list_categories(pairs)
    # Spot-check required categories
    for required in ("th-s", "v-b", "r-l", "i-ii", "ae-uh"):
        assert required in categories


def test_seed_all_entries_have_category():
    pairs = load_pairs(SEED_PATH)
    assert all(pair.category for pair in pairs)


def test_seed_unique_ordered_pairs():
    pairs = load_pairs(SEED_PATH)
    seen = set()
    for pair in pairs:
        key = (pair.word, pair.partner)
        assert key not in seen, f"duplicate pair: {key}"
        seen.add(key)


def test_missing_file_raises(tmp_path):
    with pytest.raises(PairsError):
        load_pairs(tmp_path / "missing.json")


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(PairsError):
        load_pairs(path)


def test_missing_field_raises(tmp_path):
    path = tmp_path / "p.json"
    _write(path, [{"word": "a", "category": "x"}])
    with pytest.raises(PairsError) as exc:
        load_pairs(path)
    assert "partner" in str(exc.value)


def test_duplicate_pair_raises(tmp_path):
    path = tmp_path / "p.json"
    _write(
        path,
        [
            {"word": "a", "partner": "b", "category": "x"},
            {"word": "a", "partner": "b", "category": "y"},
        ],
    )
    with pytest.raises(PairsError):
        load_pairs(path)


def test_filter_pairs_by_category():
    pairs = load_pairs(SEED_PATH)
    i_ii = filter_pairs(pairs, "i-ii")
    assert i_ii, "expected non-empty i-ii bucket"
    assert all(p.category == "i-ii" for p in i_ii)


def test_filter_pairs_none_returns_copy():
    pairs = load_pairs(SEED_PATH)
    copy = filter_pairs(pairs, None)
    assert copy == pairs
    assert copy is not pairs


def test_find_pair_by_word_case_insensitive():
    pairs = load_pairs(SEED_PATH)
    pair = find_pair_by_word(pairs, "SHEEP")
    assert pair is not None
    assert pair.word == "sheep"
    assert pair.partner == "ship"


def test_find_pair_by_word_missing():
    pairs = load_pairs(SEED_PATH)
    assert find_pair_by_word(pairs, "xyzzy") is None
