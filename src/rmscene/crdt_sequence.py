"""Data structure representing CRDT sequence.

"""

import logging
import typing as tp
from typing import Iterable
from collections import defaultdict
from dataclasses import dataclass

from .tagged_block_common import CrdtId

_logger = logging.getLogger(__name__)


# If the type constraint is for a CrdtSequenceItem[Superclass], then a
# CrdtSequenceItem[Subclass] would do, so it is covariant.

_T = tp.TypeVar("_T", covariant=True)


@dataclass
class CrdtSequenceItem(tp.Generic[_T]):
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    value: _T


# As a mutable container, CrdtSequence is invariant.
_Ti = tp.TypeVar("_Ti", covariant=False)


class CrdtSequence(tp.Generic[_Ti]):
    """Ordered CRDT Sequence container.

    The Sequence contains `CrdtSequenceItem`s, each of which has an ID and
    left/right IDs establishing a partial order.

    Iterating through the `CrdtSequence` yields IDs following this order.

    """

    def __init__(self, items=None):
        if items is None:
            items = []
        self._items = {item.item_id: item for item in items}

    def __eq__(self, other):
        if isinstance(other, CrdtSequence):
            return self._items == other._items
        if isinstance(other, (list, tuple)):
            return self == CrdtSequence(other)
        raise NotImplemented

    def __repr__(self):
        return "CrdtSequence(%s)" % (", ".join(str(i) for i in self._items.values()))

    ## Access values, in order

    def __iter__(self) -> tp.Iterator[CrdtId]:
        """Return ids in order"""
        yield from toposort_items(self._items.values())

    def keys(self) -> list[CrdtId]:
        """Return CrdtIds in order."""
        return list(self)

    def values(self) -> list[_Ti]:
        """Return list of sorted values."""
        return [self[item_id] for item_id in self]

    def items(self) -> Iterable[tuple[CrdtId, _Ti]]:
        """Return list of sorted key, value pairs."""
        return [(item_id, self[item_id]) for item_id in self]

    def __getitem__(self, key: CrdtId) -> _Ti:
        """Return item with key"""
        return self._items[key].value

    ## Access SequenceItems

    def sequence_items(self) -> list[CrdtSequenceItem[_Ti]]:
        """Iterate through CrdtSequenceItems."""
        return list(self._items.values())

    ## Modify sequence

    def add(self, item: CrdtSequenceItem[_Ti]):
        if item.item_id in self._items:
            raise ValueError("Already have item %s" % item.item_id)
        self._items[item.item_id] = item


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
        if side_id == END_MARKER or side_id not in item_dict:
            if side_id != END_MARKER:
                _logger.debug("Ignoring unknown %s_id %s of %s", side, side_id, item)
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
