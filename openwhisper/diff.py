from __future__ import annotations

import re

_WORD_RE = re.compile(r"\S+")


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def _normalize(word: str) -> str:
    return word.casefold().strip(".,;:!?-—\"'()[]{}…")


def compute_suffix(
    committed: str,
    new_chunk: str,
    overlap_window_words: int = 12,
    min_match_words: int = 2,
) -> str:
    """Return the portion of ``new_chunk`` to append after ``committed``.

    The chunks come from overlapping ASR runs over the same audio. The
    overlap region of ``new_chunk`` is expected to re-cover the trailing
    words of ``committed``, but the wording may drift slightly (whisper
    rephrasing, punctuation flicker, capitalization).

    Strategy: align the tail of ``committed`` against the head of
    ``new_chunk`` over a bounded window using word-level LCS. The longest
    LCS pair anchors where ``committed`` ends inside ``new_chunk``; we
    return everything after the last matched word.

    Fallback when no match meets ``min_match_words``: append the entire
    ``new_chunk`` (with a single space separator). This duplicates the
    overlap region but never drops new content. Callers should view this
    as a soft failure and log it.
    """
    if not new_chunk:
        return ""
    if not committed:
        return new_chunk

    committed_tokens = _tokenize(committed)
    new_tokens = _tokenize(new_chunk)
    if not new_tokens:
        return ""

    tail = committed_tokens[-overlap_window_words:]
    head = new_tokens[:overlap_window_words]

    tail_norm = [_normalize(t[0]) for t in tail]
    head_norm = [_normalize(t[0]) for t in head]

    last_new_idx = _last_lcs_end_in_head(tail_norm, head_norm, min_match_words)
    if last_new_idx is None:
        return " " + new_chunk if not new_chunk.startswith(" ") else new_chunk

    if last_new_idx + 1 >= len(new_tokens):
        return ""

    cut = new_tokens[last_new_idx + 1][1]
    suffix = new_chunk[cut:]
    if suffix and not suffix[0].isspace() and not committed.endswith((" ", "\n", "\t")):
        suffix = " " + suffix.lstrip()
    return suffix


def _last_lcs_end_in_head(
    tail: list[str], head: list[str], min_match: int
) -> int | None:
    """Find the LCS between ``tail`` and ``head``. Return the index in
    ``head`` of the last matched element, or None if the LCS length is
    below ``min_match``.
    """
    n, m = len(tail), len(head)
    if n == 0 or m == 0:
        return None

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    last_j = [[-1] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if tail[i - 1] and tail[i - 1] == head[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                last_j[i][j] = j - 1
            else:
                if dp[i - 1][j] >= dp[i][j - 1]:
                    dp[i][j] = dp[i - 1][j]
                    last_j[i][j] = last_j[i - 1][j]
                else:
                    dp[i][j] = dp[i][j - 1]
                    last_j[i][j] = last_j[i][j - 1]

    if dp[n][m] < min_match:
        return None
    return last_j[n][m]
