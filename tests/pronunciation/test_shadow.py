from openwhisper.pronunciation.score import Op
from openwhisper.pronunciation.shadow import (
    compute_shadow,
    format_accuracy,
    ops_to_json,
    render_diff,
)

TARGET = "The sun rose slowly over the quiet town."


def test_compute_shadow_perfect_match():
    result = compute_shadow(TARGET, TARGET)
    assert result.accuracy == 1.0
    assert all(op.op == Op.MATCH for op in result.ops)


def test_compute_shadow_substitute():
    heard = "The sun rose quickly over the quiet town."
    result = compute_shadow(TARGET, heard)
    subs = [op for op in result.ops if op.op == Op.SUBSTITUTE]
    assert len(subs) == 1
    assert subs[0].target == "slowly"
    assert subs[0].heard == "quickly"
    assert 0 < result.accuracy < 1


def test_compute_shadow_missed_word():
    heard = "The sun rose slowly over the town."
    result = compute_shadow(TARGET, heard)
    dels = [op for op in result.ops if op.op == Op.DELETE]
    assert [op.target for op in dels] == ["quiet"]


def test_compute_shadow_empty_transcript_all_deletes():
    result = compute_shadow(TARGET, "")
    assert result.heard_tokens == []
    assert all(op.op == Op.DELETE for op in result.ops)
    assert result.accuracy == 0.0


def test_render_diff_plain_text():
    result = compute_shadow(TARGET, "The sun rose quickly over the town.")
    plain = render_diff(result.ops, color=False)
    assert "slowly" in plain
    assert "quickly" in plain
    assert "quiet" in plain


def test_render_diff_golden_plain():
    target = "a b c"
    heard = "a x c d"
    result = compute_shadow(target, heard)
    plain = render_diff(result.ops, color=False)
    assert plain == "a ~b~ !x! c +d"


def test_render_diff_color_contains_ansi():
    result = compute_shadow("a b", "a c")
    colored = render_diff(result.ops, color=True)
    assert "\033[" in colored


def test_format_accuracy_formatting():
    assert format_accuracy(0.75).startswith("Accuracy: 75.00%")


def test_ops_to_json_shape():
    result = compute_shadow("a b", "a c")
    data = ops_to_json(result.ops)
    assert isinstance(data, list)
    assert {entry["op"] for entry in data} <= {"match", "substitute", "insert", "delete"}
