from openwhisper.pronunciation.score import AlignOp, Op, accuracy, align


def _ops(pairs):
    return [AlignOp(op, target, heard) for op, target, heard in pairs]


def test_all_match():
    ops = align(["the", "quick", "fox"], ["the", "quick", "fox"])
    assert ops == _ops([
        (Op.MATCH, "the", "the"),
        (Op.MATCH, "quick", "quick"),
        (Op.MATCH, "fox", "fox"),
    ])
    assert accuracy(ops, 3) == 1.0


def test_single_substitute():
    ops = align(["the", "quick", "fox"], ["the", "slow", "fox"])
    assert ops == _ops([
        (Op.MATCH, "the", "the"),
        (Op.SUBSTITUTE, "quick", "slow"),
        (Op.MATCH, "fox", "fox"),
    ])
    assert accuracy(ops, 3) == 2 / 3


def test_deletion_missed_word():
    ops = align(["hello", "world"], ["hello"])
    assert ops == _ops([
        (Op.MATCH, "hello", "hello"),
        (Op.DELETE, "world", None),
    ])
    assert accuracy(ops, 2) == 0.5


def test_insertion_extra_word():
    ops = align(["hello", "world"], ["hello", "brave", "world"])
    assert ops == _ops([
        (Op.MATCH, "hello", "hello"),
        (Op.INSERT, None, "brave"),
        (Op.MATCH, "world", "world"),
    ])
    assert accuracy(ops, 2) == 1.0


def test_composite_operations():
    ops = align(["a", "b", "c", "d"], ["a", "x", "d", "e"])
    matches = [op for op in ops if op.op == Op.MATCH]
    assert len(matches) == 2
    assert accuracy(ops, 4) == 0.5


def test_empty_heard_all_deletes():
    ops = align(["one", "two", "three"], [])
    assert all(op.op == Op.DELETE for op in ops)
    assert len(ops) == 3
    assert accuracy(ops, 3) == 0.0


def test_empty_target_all_inserts():
    ops = align([], ["one", "two"])
    assert all(op.op == Op.INSERT for op in ops)
    assert accuracy(ops, 0) == 0.0


def test_both_empty():
    ops = align([], [])
    assert ops == []
    assert accuracy(ops, 0) == 0.0
