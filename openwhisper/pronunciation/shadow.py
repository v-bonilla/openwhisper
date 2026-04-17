from __future__ import annotations

from dataclasses import dataclass

from .normalize import tokenize
from .score import AlignOp, Op, accuracy, align

_RESET = "\033[0m"
_DIM = "\033[2m"
_RED = "\033[31m"
_STRIKE = "\033[9m"


@dataclass(frozen=True)
class ShadowResult:
    target_tokens: list[str]
    heard_tokens: list[str]
    ops: list[AlignOp]
    accuracy: float


def compute_shadow(target_text: str, transcript: str) -> ShadowResult:
    target_tokens = tokenize(target_text)
    heard_tokens = tokenize(transcript)
    ops = align(target_tokens, heard_tokens)
    acc = accuracy(ops, len(target_tokens))
    return ShadowResult(
        target_tokens=target_tokens,
        heard_tokens=heard_tokens,
        ops=ops,
        accuracy=acc,
    )


def render_diff(ops: list[AlignOp], *, color: bool = True) -> str:
    parts: list[str] = []
    for op in ops:
        if op.op == Op.MATCH:
            parts.append(op.target or "")
        elif op.op == Op.SUBSTITUTE:
            if color:
                parts.append(
                    f"{_STRIKE}{op.target}{_RESET} {_RED}{op.heard}{_RESET}"
                )
            else:
                parts.append(f"~{op.target}~ !{op.heard}!")
        elif op.op == Op.DELETE:
            if color:
                parts.append(f"{_DIM}{op.target}{_RESET}")
            else:
                parts.append(f"-{op.target}")
        elif op.op == Op.INSERT:
            if color:
                parts.append(f"{_RED}{op.heard}{_RESET}")
            else:
                parts.append(f"+{op.heard}")
    return " ".join(parts)


def format_accuracy(acc: float) -> str:
    return f"Accuracy: {acc:.2%} ({acc:.3f})"


def ops_to_json(ops: list[AlignOp]) -> list[dict]:
    return [
        {"op": op.op.value, "target": op.target, "heard": op.heard}
        for op in ops
    ]
