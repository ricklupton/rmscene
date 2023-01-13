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
from .tagged_block_common import CrdtId, LwwValue

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
        assert item.text == ""
        chars = [""] * item.deleted_length
        deleted_length = 1
    else:
        assert len(item.text) > 0
        chars = item.text
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


def toposort_text(items: Iterable[TextItem]) -> Iterable[CrdtId]:
    """Sort TextItems based on left and right ids.

    Call `expand_text_items` first, so that all character IDs are present.

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


def extract_text_lines(
    root_text_block: RootTextBlock,
) -> tp.Iterator[tuple[TextFormat, str]]:
    """Extract lines of text with associated formatting.

    Returns (format, line) pairs.

    """
    expanded = list(expand_text_items(root_text_block.text_items))
    char_ids = {item.item_id: item for item in expanded}
    char_order = toposort_text(expanded)
    format_for_char = {fmt.char_id: fmt for fmt in root_text_block.text_formats}

    if END_MARKER in format_for_char:
        current_format = format_for_char[END_MARKER].format_type
    else:
        current_format = TextFormat.PLAIN

    current_line = ""
    for k in char_order:
        char = char_ids[k].text
        assert len(char) <= 1
        if char == "\n":
            yield (current_format, current_line)
            current_format = TextFormat.PLAIN
            current_line = ""
        else:
            current_line += char
        if k in format_for_char:
            current_format = format_for_char[k].format_type
            if char != "\n":
                _logger.warning("format does not apply to whole line")
    yield (current_format, current_line)


def extract_text(data: tp.BinaryIO) -> Iterable[tuple[TextFormat, str]]:
    """
    Parse reMarkable file and return iterator of text (format, line) pairs.

    :param data: reMarkable file data.
    """
    for block in read_blocks(data):
        if isinstance(block, RootTextBlock):
            yield from extract_text_lines(block)


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
                                             text=text)],
                        text_formats=[TextFormatItem(item_id=CrdtId(1, 15),
                                                     char_id=CrdtId(0, 0),
                                                     format_type=TextFormat.PLAIN)],
                        pos_x=-468.0,
                        pos_y=234.0,
                        width=936.0)

    yield TreeNodeBlock(node_id=CrdtId(0, 1),
                        label=LwwValue(timestamp=CrdtId(0, 0), value=''),
                        visible=LwwValue(timestamp=CrdtId(0, 0), value=True),
                        anchor_id=None,
                        anchor_type=None,
                        anchor_threshold=None,
                        anchor_origin_x=None)

    yield TreeNodeBlock(node_id=CrdtId(0, 11),
                        label=LwwValue(timestamp=CrdtId(0, 12), value='Layer 1'),
                        visible=LwwValue(timestamp=CrdtId(0, 0), value=True),
                        anchor_id=None,
                        anchor_type=None,
                        anchor_threshold=None,
                        anchor_origin_x=None)

    yield SceneGroupItemBlock(parent_id=CrdtId(0, 1),
                              item_id=CrdtId(0, 13),
                              left_id=CrdtId(0, 0),
                              right_id=CrdtId(0, 0),
                              deleted_length=0,
                              value=CrdtId(0, 11))
