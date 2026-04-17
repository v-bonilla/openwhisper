import random

from openwhisper.pronunciation.drill import (
    OUTCOME_CONFUSED,
    OUTCOME_PASS,
    OUTCOME_UNCLEAR,
    aggregate,
    classify,
    format_attempt,
    format_summary,
    run_drill_session,
    sample_targets,
)
from openwhisper.pronunciation.pairs import Pair


PAIRS = [
    Pair(word="sheep", partner="ship", category="i-ii"),
    Pair(word="think", partner="sink", category="th-s"),
    Pair(word="right", partner="light", category="r-l"),
]


def test_classify_pass():
    assert classify("sheep", "sheep", "ship") == (OUTCOME_PASS, "sheep")


def test_classify_pass_sentence():
    assert classify("I said sheep", "sheep", "ship") == (OUTCOME_PASS, "sheep")


def test_classify_confused():
    assert classify("ship", "sheep", "ship") == (OUTCOME_CONFUSED, "ship")


def test_classify_unclear_neither():
    outcome, _ = classify("um", "sheep", "ship")
    assert outcome == OUTCOME_UNCLEAR


def test_classify_unclear_empty():
    assert classify("", "sheep", "ship") == (OUTCOME_UNCLEAR, "")


def test_classify_both_words_first_token_wins():
    outcome, _ = classify("sheep ship", "sheep", "ship")
    assert outcome == OUTCOME_PASS
    outcome, _ = classify("ship sheep", "sheep", "ship")
    assert outcome == OUTCOME_UNCLEAR


def test_sample_targets_without_replacement():
    rng = random.Random(0)
    targets = sample_targets(PAIRS, 3, rng=rng)
    assert sorted(p.word for p in targets) == sorted(p.word for p in PAIRS)


def test_sample_targets_falls_back_to_replacement():
    rng = random.Random(0)
    targets = sample_targets(PAIRS[:2], 5, rng=rng)
    assert len(targets) == 5
    assert all(t.word in {"sheep", "think"} for t in targets)


def test_sample_zero_empty():
    assert sample_targets(PAIRS, 0) == []


def test_run_drill_session_fake_transcribe():
    rng = random.Random(1)

    def fake_transcribe(pair: Pair) -> str:
        if pair.word == "sheep":
            return pair.word
        if pair.word == "think":
            return pair.partner
        return "um"

    results = run_drill_session(PAIRS, 3, fake_transcribe, rng=rng)
    outcomes = {r.word: r.outcome for r in results}
    assert outcomes == {
        "sheep": OUTCOME_PASS,
        "think": OUTCOME_CONFUSED,
        "right": OUTCOME_UNCLEAR,
    }

    totals = aggregate(results)["totals"]
    assert totals[OUTCOME_PASS] == 1
    assert totals[OUTCOME_CONFUSED] == 1
    assert totals[OUTCOME_UNCLEAR] == 1


def test_format_attempt_strings():
    from openwhisper.pronunciation.drill import AttemptResult

    passed = AttemptResult("sheep", "ship", "i-ii", "sheep", OUTCOME_PASS, "sheep")
    confused = AttemptResult("sheep", "ship", "i-ii", "ship", OUTCOME_CONFUSED, "ship")
    unclear = AttemptResult("sheep", "ship", "i-ii", "uh", OUTCOME_UNCLEAR, "uh")
    assert format_attempt(passed) == "PASS"
    assert 'CONFUSED' in format_attempt(confused)
    assert '"ship"' in format_attempt(confused)
    assert 'UNCLEAR' in format_attempt(unclear)


def test_format_summary_contains_categories():
    def fake(pair):
        return pair.word if pair.word == "sheep" else "um"

    results = run_drill_session(PAIRS, 3, fake, rng=random.Random(2))
    summary = format_summary(results)
    assert "Total attempts: 3" in summary
    # Worst-performing category should be listed
    assert "r-l" in summary or "th-s" in summary


def test_format_summary_empty():
    assert format_summary([]) == "No attempts recorded."
