"""Data structure representing CRDT sequence.

"""

import typing as tp
from typing import Iterable
from collections import defaultdict
from dataclasses import dataclass

from .tagged_block_common import CrdtId


_T = tp.TypeVar("_T")

@dataclass
class CrdtSequenceItem(tp.Generic[_T]):
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    value: _T


class CrdtSequence(tp.Generic[_T]):
    def __init__(self, items=None):
        if items is None:
            items = []
        self._items = {item.item_id: item for item in items}

    def __iter__(self) -> tp.Iterator[CrdtId]:
        """Return ids in order"""
        yield from toposort_items(self._items.values())

    def values(self) -> Iterable[CrdtSequenceItem[_T]]:
        return self._items.values()

    def __getitem__(self, key: CrdtId) -> _T:
        """Return item with key"""
        return self._items[key].value


END_MARKER = CrdtId(0, 0)


def toposort_items(items: Iterable[CrdtSequenceItem]) -> Iterable[CrdtId]:
    """Sort SequenceItems based on left and right ids.

    Returns `CrdtId`s in the sorted order.

    """

    item_dict = {}
    for item in items:
        item_dict[item.item_id] = item
    if not item_dict:
        return  # nothing to do

    def _side_id(item, side):
        side_id = getattr(item, f"{side}_id")
        if side_id == END_MARKER:
            return "__start" if side == "left" else "__end"
        else:
            return side_id

    # build dictionary: key "comes after" values
    data = defaultdict(set)
    for item in item_dict.values():
        left_id = _side_id(item, "left")
        right_id = _side_id(item, "right")
        data[item.item_id].add(left_id)
        data[right_id].add(item.item_id)

    # fill in sources not explicitly included
    sources_not_in_data = {dep for deps in data.values() for dep in deps} - {
        k for k in data.keys()
    }
    data.update({k: set() for k in sources_not_in_data})

    while True:
        next_items = {item for item, deps in data.items() if not deps}
        if next_items == {"__end"}:
            break
        assert next_items
        yield from sorted(k for k in next_items if k in item_dict)
        data = {
            item: (deps - next_items)
            for item, deps in data.items()
            if item not in next_items
        }

    if data != {"__end": set()}:
        raise ValueError("cyclic dependency")
