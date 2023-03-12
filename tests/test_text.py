from rmscene.text import expand_text_item
from rmscene import CrdtId, CrdtSequenceItem


def cid(k):
    "Shorthand for making end-markers or IDs with author-id = 1."
    return CrdtId(0 if k == 0 else 1, k)


def make_item(item_id, left_id, right_id, *args):
    "Shorthand for creating ids."
    return CrdtSequenceItem(cid(item_id), cid(left_id), cid(right_id), *args)


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
