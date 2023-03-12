"""Process text from remarkable scene files.

"""

from __future__ import annotations

from collections.abc import Iterable
from collections import defaultdict
import logging
import typing as tp

from . import scene_items as si
from .tagged_block_common import CrdtId
from .crdt_sequence import CrdtSequence, CrdtSequenceItem

_logger = logging.getLogger(__name__)


def expand_text_item(item: CrdtSequenceItem[str]) -> Iterable[CrdtSequenceItem[str]]:
    """Expand TextItem into single-character TextItems.

    Text is stored as strings in TextItems, each with an associated ID for the
    block. This ID identifies the character at the start of the block. The
    subsequent characters' IDs are implicit.

    This function expands a TextItem into multiple single-character TextItems,
    so that each character has an explicit ID.

    """

    if item.deleted_length > 0:
        assert item.value == ""
        chars = [""] * item.deleted_length
        deleted_length = 1
    else:
        assert len(item.value) > 0
        chars = item.value
        deleted_length = 0

    item_id = item.item_id
    left_id = item.left_id
    for c in chars[:-1]:
        right_id = CrdtId(item_id.part1, item_id.part2 + 1)
        yield CrdtSequenceItem(item_id, left_id, right_id, deleted_length, c)
        left_id = item_id
        item_id = right_id
    yield CrdtSequenceItem(item_id, left_id, item.right_id, deleted_length, chars[-1])


def expand_text_items(items: Iterable[CrdtSequenceItem[str]]) -> Iterable[CrdtSequenceItem[str]]:
    """Expand a sequence of TextItems into single-character TextItems."""
    for item in items:
        yield from expand_text_item(item)
