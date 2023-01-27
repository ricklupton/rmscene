from rmscene.crdt_sequence import CrdtSequenceItem, CrdtSequence
from rmscene import CrdtId


def cid(k):
    "Shorthand for making end-markers or IDs with author-id = 1."
    return CrdtId(0 if k == 0 else 1, k)


def make_item(item_id, left_id, right_id, *args):
    "Shorthand for creating ids."
    return CrdtSequenceItem(cid(item_id), cid(left_id), cid(right_id), *args)


def test_empty():
    assert list(CrdtSequence([])) == []


def test_just_one():
    items = [
        make_item(1, 0, 0, 0, "A"),
    ]
    result = list(CrdtSequence(items))
    assert result == [cid(1)]


def test_two():
    items = [
        make_item(1, 0, 0, 0, "A"),
        make_item(2, 1, 0, 0, "B"),
    ]
    result1 = list(CrdtSequence(items))
    result2 = list(CrdtSequence(reversed(items)))
    assert result1 == result2


def test_overlapping():
    items = [
        make_item(1, 0, 0, 0, "A"),
        make_item(2, 1, 0, 0, "B"),
        make_item(3, 0, 0, 0, "C"),
    ]
    result1 = list(CrdtSequence(items))
    result2 = list(CrdtSequence(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(1), cid(3), cid(2)]


def test_overlapping_sorted_by_id():
    items = [
        make_item(8, 0, 0, 0, "A"),
        make_item(9, 8, 0, 0, "B"),
        make_item(3, 0, 0, 0, "C"),
    ]
    result1 = list(CrdtSequence(items))
    result2 = list(CrdtSequence(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(3), cid(8), cid(9)]


def test_unknown_id():
    items = [
        make_item(28, 0, 15, 0, "A"),
        make_item(31, 30, 15, 2, ""),
        make_item(33, 32, 15, 0, "B"),
        make_item(15, 0, 0, 0, "C"),
    ]
    result1 = list(CrdtSequence(items))
    result2 = list(CrdtSequence(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(28), cid(31), cid(33), cid(15)]
