from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .normalize import tokenize
from .pairs import Pair

OUTCOME_PASS = "PASS"
OUTCOME_CONFUSED = "CONFUSED"
OUTCOME_UNCLEAR = "UNCLEAR"
OUTCOMES = (OUTCOME_PASS, OUTCOME_CONFUSED, OUTCOME_UNCLEAR)


@dataclass(frozen=True)
class AttemptResult:
    word: str
    partner: str
    category: str
    transcript: str
    outcome: str
    heard: str


def _norm_word(word: str) -> str:
    tokens = tokenize(word)
    return tokens[0] if tokens else word.lower()


def classify(transcript: str, word: str, partner: str) -> tuple[str, str]:
    tokens = tokenize(transcript)
    word_token = _norm_word(word)
    partner_token = _norm_word(partner)

    if not tokens:
        return OUTCOME_UNCLEAR, ""

    has_word = word_token in tokens
    has_partner = partner_token in tokens

    if has_word and not has_partner:
        return OUTCOME_PASS, word_token
    if has_partner and not has_word:
        return OUTCOME_CONFUSED, partner_token
    if has_word and has_partner:
        if tokens[0] == word_token:
            return OUTCOME_PASS, word_token
        return OUTCOME_UNCLEAR, " ".join(tokens)
    return OUTCOME_UNCLEAR, " ".join(tokens)


def sample_targets(
    pairs: list[Pair],
    count: int,
    rng: random.Random | None = None,
) -> list[Pair]:
    if count <= 0:
        return []
    if not pairs:
        return []
    rng = rng or random.Random()
    if len(pairs) >= count:
        indices = rng.sample(range(len(pairs)), count)
        return [pairs[i] for i in indices]
    return [rng.choice(pairs) for _ in range(count)]


def run_drill_session(
    pairs: list[Pair],
    count: int,
    get_transcript: Callable[[Pair], str],
    *,
    rng: random.Random | None = None,
    on_attempt: Callable[[AttemptResult], None] | None = None,
) -> list[AttemptResult]:
    targets = sample_targets(pairs, count, rng)
    results: list[AttemptResult] = []
    for target in targets:
        transcript = get_transcript(target)
        outcome, heard = classify(transcript, target.word, target.partner)
        result = AttemptResult(
            word=target.word,
            partner=target.partner,
            category=target.category,
            transcript=transcript,
            outcome=outcome,
            heard=heard,
        )
        if on_attempt is not None:
            on_attempt(result)
        results.append(result)
    return results


def aggregate(results: list[AttemptResult]) -> dict:
    totals = {outcome: 0 for outcome in OUTCOMES}
    per_category: dict[str, dict[str, int]] = {}
    for result in results:
        totals[result.outcome] = totals.get(result.outcome, 0) + 1
        bucket = per_category.setdefault(
            result.category, {outcome: 0 for outcome in OUTCOMES}
        )
        bucket[result.outcome] = bucket.get(result.outcome, 0) + 1
    return {"totals": totals, "categories": per_category}


def format_attempt(result: AttemptResult) -> str:
    if result.outcome == OUTCOME_PASS:
        return "PASS"
    if result.outcome == OUTCOME_CONFUSED:
        return f'CONFUSED → heard "{result.heard}"'
    return f'UNCLEAR → heard "{result.heard}"'


def format_summary(results: list[AttemptResult]) -> str:
    if not results:
        return "No attempts recorded."
    summary = aggregate(results)
    totals = summary["totals"]
    lines = [
        f"Total attempts: {len(results)}",
        f"  PASS: {totals[OUTCOME_PASS]}",
        f"  CONFUSED: {totals[OUTCOME_CONFUSED]}",
        f"  UNCLEAR: {totals[OUTCOME_UNCLEAR]}",
    ]
    categories: dict[str, dict[str, int]] = summary["categories"]
    if categories:
        lines.append("")
        lines.append("Categories (worst first):")

        def pass_rate(bucket: dict[str, int]) -> float:
            total = sum(bucket.values())
            return bucket.get(OUTCOME_PASS, 0) / total if total else 0.0

        ordered = sorted(categories.items(), key=lambda kv: (pass_rate(kv[1]), kv[0]))
        for category, bucket in ordered:
            total = sum(bucket.values())
            passed = bucket.get(OUTCOME_PASS, 0)
            lines.append(f"  {category}: {passed}/{total} pass")
    return "\n".join(lines)


def results_to_json(results: list[AttemptResult]) -> list[dict]:
    return [
        {
            "word": r.word,
            "partner": r.partner,
            "category": r.category,
            "transcript": r.transcript,
            "outcome": r.outcome,
            "heard": r.heard,
        }
        for r in results
    ]
