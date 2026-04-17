from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Op(str, Enum):
    MATCH = "match"
    SUBSTITUTE = "substitute"
    INSERT = "insert"
    DELETE = "delete"


@dataclass(frozen=True)
class AlignOp:
    op: Op
    target: str | None
    heard: str | None


def align(target: list[str], heard: list[str]) -> list[AlignOp]:
    m, n = len(target), len(heard)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if target[i - 1] == heard[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j - 1],
                    dp[i - 1][j],
                    dp[i][j - 1],
                )

    ops: list[AlignOp] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and target[i - 1] == heard[j - 1]:
            ops.append(AlignOp(Op.MATCH, target[i - 1], heard[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(AlignOp(Op.DELETE, target[i - 1], None))
            i -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ops.append(AlignOp(Op.INSERT, None, heard[j - 1]))
            j -= 1
        else:
            ops.append(AlignOp(Op.SUBSTITUTE, target[i - 1], heard[j - 1]))
            i -= 1
            j -= 1
    ops.reverse()
    return ops


def accuracy(ops: list[AlignOp], target_len: int) -> float:
    if target_len <= 0:
        return 0.0
    matches = sum(1 for op in ops if op.op == Op.MATCH)
    return matches / target_len
