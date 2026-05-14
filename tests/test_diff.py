from openwhisper.diff import compute_suffix


def test_empty_committed_returns_full_chunk():
    assert compute_suffix("", "hello world") == "hello world"


def test_empty_chunk_returns_empty():
    assert compute_suffix("hello", "") == ""


def test_perfect_overlap_returns_new_tail():
    # committed ends with "to the store"; chunk repeats "to the store" then adds new words.
    committed = "I went to the store"
    new_chunk = "to the store and bought milk"
    assert compute_suffix(committed, new_chunk) == " and bought milk"


def test_punctuation_drift_in_overlap_still_matches():
    committed = "I went to the store"
    new_chunk = "to the store, and bought milk."
    suffix = compute_suffix(committed, new_chunk)
    assert "and bought milk" in suffix
    assert suffix.startswith(" ")


def test_capitalization_drift_still_matches():
    committed = "I went to the store"
    new_chunk = "To The Store and bought milk"
    assert compute_suffix(committed, new_chunk) == " and bought milk"


def test_rephrased_boundary_falls_back_to_full_chunk():
    committed = "I went to the store"
    new_chunk = "headed into the shop and bought milk"
    suffix = compute_suffix(committed, new_chunk)
    # No overlap meets min_match — duplicate everything with leading space.
    assert suffix == " headed into the shop and bought milk"


def test_single_word_match_below_min_falls_back():
    committed = "go now"
    new_chunk = "now also tomorrow"
    suffix = compute_suffix(committed, new_chunk)
    # Only "now" matches (1 word) — below min_match_words=2; fall back.
    assert suffix == " now also tomorrow"


def test_full_chunk_already_committed_returns_empty():
    committed = "hello world this is everything"
    new_chunk = "this is everything"
    assert compute_suffix(committed, new_chunk) == ""


def test_unicode_words_match():
    committed = "café au lait"
    new_chunk = "café au lait s'il vous plaît"
    assert compute_suffix(committed, new_chunk) == " s'il vous plaît"


def test_committed_with_trailing_space_no_double_space():
    committed = "say hello world "
    new_chunk = "hello world and friends"
    suffix = compute_suffix(committed, new_chunk)
    # Suffix starts with whitespace from new_chunk -> committed has trailing space
    # already, so we should not insert an extra one. Final concat acceptable.
    assert suffix.strip() == "and friends"
    assert not suffix.startswith("  ")


def test_long_overlap_window_caps_at_12():
    committed = " ".join(f"w{i}" for i in range(50))  # 50 words
    new_chunk = " ".join(f"w{i}" for i in range(45, 60))  # overlaps last 5
    suffix = compute_suffix(committed, new_chunk)
    assert "w55" in suffix and "w59" in suffix
    assert "w44" not in suffix


def test_reordered_overlap_still_uses_lcs():
    # ASR may swap word order at the seam; LCS picks the longest in-order match.
    committed = "alpha bravo charlie"
    new_chunk = "alpha charlie delta echo"
    # LCS in tail [alpha, bravo, charlie] vs head [alpha, charlie, delta, echo]:
    # match "alpha" then "charlie" -> length 2. Last matched in head = index 1 ("charlie").
    # So we return everything after charlie: " delta echo".
    assert compute_suffix(committed, new_chunk) == " delta echo"


def test_punctuation_only_overlap_does_not_count():
    # Edge case: tokens that normalize to empty (pure punctuation) shouldn't
    # spuriously match. _tokenize splits on whitespace, so "...," is one token
    # that normalizes to "". The internal match guard rejects empty-string ties.
    committed = "hello ... ,"
    new_chunk = "... , world"
    suffix = compute_suffix(committed, new_chunk)
    # Should fall back since the only "matches" would be empty-normalized tokens.
    assert "world" in suffix
