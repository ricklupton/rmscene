from rmscene.text import expand_text_item, toposort_text
from rmscene import TextItem, CrdtId


def cid(k):
    "Shorthand for making end-markers or IDs with author-id = 1."
    return CrdtId(0 if k == 0 else 1, k)


def make_item(item_id, left_id, right_id, *args):
    "Shorthand for creating ids."
    return TextItem(cid(item_id), cid(left_id), cid(right_id), *args)


def test_empty():
    assert list(toposort_text([])) == []


def test_just_one():
    items = [
        make_item(1, 0, 0, 0, "A"),
    ]
    result = list(toposort_text(items))
    assert result == [cid(1)]


def test_two():
    items = [
        make_item(1, 0, 0, 0, "A"),
        make_item(2, 1, 0, 0, "B"),
    ]
    result1 = list(toposort_text(items))
    result2 = list(toposort_text(reversed(items)))
    assert result1 == result2


def test_overlapping():
    items = [
        make_item(1, 0, 0, 0, "A"),
        make_item(2, 1, 0, 0, "B"),
        make_item(3, 0, 0, 0, "C"),
    ]
    result1 = list(toposort_text(items))
    result2 = list(toposort_text(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(1), cid(3), cid(2)]


def test_overlapping_sorted_by_id():
    items = [
        make_item(8, 0, 0, 0, "A"),
        make_item(9, 8, 0, 0, "B"),
        make_item(3, 0, 0, 0, "C"),
    ]
    result1 = list(toposort_text(items))
    result2 = list(toposort_text(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(3), cid(8), cid(9)]


def test_unknown_id():
    items = [
        make_item(28, 0, 15, 0, "A"),
        make_item(31, 30, 15, 2, ""),
        make_item(33, 32, 15, 0, "B"),
        make_item(15, 0, 0, 0, "C"),
    ]
    result1 = list(toposort_text(items))
    result2 = list(toposort_text(reversed(items)))
    assert result1 == result2
    assert result1 == [cid(28), cid(31), cid(33), cid(15)]


def test_expand_text_1():
    result = expand_text_item(make_item(17, 0, 0, 0, "AAAA"))
    assert list(result) == [
        make_item(17, 0, 18, 0, "A"),
        make_item(18, 17, 19, 0, "A"),
        make_item(19, 18, 20, 0, "A"),
        make_item(20, 19, 0, 0, "A"),
    ]


def test_expand_text_2():
    result = expand_text_item(make_item(34, 20, 21, 0, "x"))
    assert list(result) == [
        make_item(34, 20, 21, 0, "x"),
    ]


def test_expand_text_3():
    result = expand_text_item(make_item(21, 20, 0, 0, "A\nB"))
    assert list(result) == [
        make_item(21, 20, 22, 0, "A"),
        make_item(22, 21, 23, 0, "\n"),
        make_item(23, 22, 0, 0, "B"),
    ]


def test_expand_text_empty():
    result = expand_text_item(make_item(21, 20, 0, 2, ""))
    assert list(result) == [
        make_item(21, 20, 22, 1, ""),
        make_item(22, 21, 0, 1, ""),
    ]
