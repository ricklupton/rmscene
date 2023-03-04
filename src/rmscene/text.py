"""Process text from remarkable scene files.

"""

from __future__ import annotations

from uuid import uuid4
from collections.abc import Iterable
from collections import defaultdict
import logging
import typing as tp

from .scene_stream import (
    TextFormat,
    read_blocks,
    TextItem,
    TextFormatItem,
    Block,
    RootTextBlock,
    AuthorIdsBlock,
    MigrationInfoBlock,
    PageInfoBlock,
    SceneTreeBlock,
    TreeNodeBlock,
    SceneGroupItemBlock
)
from . import scene_items as si
from .tagged_block_common import CrdtId, LwwValue
from .crdt_sequence import CrdtSequence, CrdtSequenceItem

_logger = logging.getLogger(__name__)


END_MARKER = CrdtId(0, 0)


def expand_text_item(item: TextItem) -> Iterable[TextItem]:
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
        yield TextItem(item_id, left_id, right_id, deleted_length, c)
        left_id = item_id
        item_id = right_id
    yield TextItem(item_id, left_id, item.right_id, deleted_length, chars[-1])


def expand_text_items(items: Iterable[TextItem]) -> Iterable[TextItem]:
    """Expand a sequence of TextItems into single-character TextItems."""
    for item in items:
        yield from expand_text_item(item)


def extract_text_lines(
    root_text_block: RootTextBlock,
) -> tp.Iterator[tuple[TextFormat, str, list[CrdtId]]]:
    """Extract lines of text with associated formatting.

    Returns (format, line, char_ids) tuples.

    """
    format_for_char = {fmt.char_id: fmt for fmt in root_text_block.text_formats}
    if END_MARKER in format_for_char:
        current_format = format_for_char[END_MARKER].format_type
    else:
        current_format = TextFormat.PLAIN

    char_items = CrdtSequence(expand_text_items(root_text_block.text_items))

    current_line = ""
    current_ids = []
    for k in char_items:
        char = char_items[k]
        assert len(char) <= 1
        current_line += char
        current_ids += [k]
        if char == "\n":
            yield (current_format, current_line, current_ids)
            current_format = TextFormat.PLAIN
            current_line = ""
            current_ids = []
        if k in format_for_char:
            current_format = format_for_char[k].format_type
            if char != "\n":
                _logger.warning("format does not apply to whole line")

    yield (current_format, current_line, current_ids)


LINE_HEIGHTS = {
    TextFormat.PLAIN: 30,
    TextFormat.BULLET: 30,
    TextFormat.BOLD: 35,
    TextFormat.HEADING: 70,
}


def anchor_positions(
    lines: tp.Iterable[tuple[TextFormat, str, list[CrdtId]]],
    anchor_ids: tp.Optional[tp.Collection[CrdtId]] = None,
):
    if anchor_ids is not None:
        anchor_ids = set(anchor_ids)
    y = 0

    result = {}
    for fmt, line, ids in lines:
        relevant_ids = set(ids) & anchor_ids if anchor_ids is not None else set(ids)
        for k in relevant_ids:
            result[k] = y
        y += LINE_HEIGHTS[fmt]
    return result


def extract_text(data: tp.BinaryIO) -> Iterable[tuple[TextFormat, str]]:
    """
    Parse reMarkable file and return iterator of text (format, line) pairs.

    :param data: reMarkable file data.
    """
    for block in read_blocks(data):
        if isinstance(block, RootTextBlock):
            for fmt, s, _ in extract_text_lines(block):
                yield (fmt, s)


def simple_text_document(text: str, author_uuid=None) -> Iterable[Block]:
    """Return the basic blocks to represent `text` as plain text."""

    if author_uuid is None:
        author_uuid = uuid4()

    yield AuthorIdsBlock(author_uuids={1: author_uuid})

    yield MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True)

    yield PageInfoBlock(loads_count=1,
                        merges_count=0,
                        text_chars_count=len(text) + 1,
                        text_lines_count=text.count("\n") + 1)

    yield SceneTreeBlock(tree_id=CrdtId(0, 11),
                         node_id=CrdtId(0, 0),
                         is_update=True,
                         parent_id=CrdtId(0, 1))

    yield RootTextBlock(block_id=CrdtId(0, 0),
                        text_items=[TextItem(item_id=CrdtId(1, 16),
                                             left_id=CrdtId(0, 0),
                                             right_id=CrdtId(0, 0),
                                             deleted_length=0,
                                             value=text)],
                        text_formats=[TextFormatItem(item_id=CrdtId(1, 15),
                                                     char_id=CrdtId(0, 0),
                                                     format_type=TextFormat.PLAIN)],
                        pos_x=-468.0,
                        pos_y=234.0,
                        width=936.0)

    yield TreeNodeBlock(
        si.Group(
            node_id=CrdtId(0, 1),
        )
    )

    yield TreeNodeBlock(
        si.Group(
            node_id=CrdtId(0, 11),
            label=LwwValue(timestamp=CrdtId(0, 12), value='Layer 1'),
        )
    )

    yield SceneGroupItemBlock(
        parent_id=CrdtId(0, 1),
        item=CrdtSequenceItem(
            item_id=CrdtId(0, 13),
            left_id=CrdtId(0, 0),
            right_id=CrdtId(0, 0),
            deleted_length=0,
            value=CrdtId(0, 11)
        )
    )
