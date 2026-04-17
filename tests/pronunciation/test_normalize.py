from openwhisper.pronunciation.normalize import normalize_text, tokenize


def test_lowercase_and_strips_punctuation():
    assert normalize_text("Hello, World!") == "hello world"


def test_strip_outer_apostrophes():
    assert normalize_text("'hello'") == "hello"


def test_preserves_inner_apostrophe():
    assert normalize_text("don't stop") == "don't stop"


def test_collapses_whitespace():
    assert normalize_text("  She   said\n\thi  ") == "she said hi"


def test_is_idempotent():
    sample = "Did you say 'sheep'? Yes—I did!"
    once = normalize_text(sample)
    twice = normalize_text(once)
    assert once == twice


def test_tokenize_basic():
    assert tokenize("She said, 'hi!' and left.") == ["she", "said", "hi", "and", "left"]


def test_tokenize_empty_returns_empty_list():
    assert tokenize("") == []
    assert tokenize("   ") == []
    assert tokenize("!!!") == []


def test_normalize_numbers_kept():
    assert normalize_text("I have 3 cats.") == "i have 3 cats"


def test_normalize_hyphenated_words_split():
    assert tokenize("mother-in-law") == ["mother", "in", "law"]
