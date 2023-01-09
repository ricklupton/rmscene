"""Read structure of reMarkable tablet lines format v6

With help from ddvk's v6 reader, and enum values from remt.

"""

from __future__ import annotations

from abc import ABC
from collections.abc import Iterable
import math
from uuid import UUID
from dataclasses import dataclass
import enum
import logging
import typing as tp

from .tagged_block_stream import CrdtId, TaggedBlockStream

_logger = logging.getLogger(__name__)


############################################################
# Top-level block types
############################################################


class Block(ABC):
    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> Block:
        raise NotImplementedError()


@dataclass
class AuthorIdsBlock(Block):
    author_uuids: dict[int, UUID]

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> AuthorIdsBlock:
        num_subblocks = stream.data.read_varuint()
        author_ids = {}
        for _ in range(num_subblocks):
            with stream.read_subblock(0):
                uuid_length = stream.data.read_varuint()
                if uuid_length != 16:
                    raise ValueError("Expected UUID length to be 16 bytes")
                uuid = UUID(bytes_le=stream.data.read_bytes(uuid_length))
                author_id = stream.data.read_uint16()
                author_ids[author_id] = uuid
        return AuthorIdsBlock(author_ids)


@dataclass
class MigrationInfoBlock(Block):
    migration_id: CrdtId
    is_device: bool

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> MigrationInfoBlock:
        "Parse migration info"
        migration_id = stream.read_id(1)
        is_device = stream.read_bool(2)
        return MigrationInfoBlock(migration_id, is_device)


@dataclass
class TreeNodeBlock(Block):
    node_id: CrdtId
    label: tuple[CrdtId, str]
    visible: tuple[CrdtId, bool]

    anchor_id: tp.Optional[tuple[CrdtId, CrdtId]] = None
    anchor_type: tp.Optional[tuple[CrdtId, int]] = None
    anchor_threshold: tp.Optional[tuple[CrdtId, float]] = None
    anchor_origin_x: tp.Optional[tuple[CrdtId, float]] = None

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> TreeNodeBlock:
        "Parse tree node block."

        node = TreeNodeBlock(
            stream.read_id(1),
            stream.read_lww_string(2),
            stream.read_lww_bool(3),
        )

        if stream.bytes_remaining_in_block() > 0:
            node.anchor_id = stream.read_lww_id(7)
            node.anchor_type = stream.read_lww_byte(8)
            node.anchor_threshold = stream.read_lww_float(9)
            node.anchor_origin_x = stream.read_lww_float(10)

        return node


@dataclass
class PageInfoBlock(Block):
    loads_count: int
    merges_count: int
    text_chars_count: int
    text_lines_count: int

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> PageInfoBlock:
        "Parse page info block"
        info = PageInfoBlock(
            loads_count=stream.read_int(1),
            merges_count=stream.read_int(2),
            text_chars_count=stream.read_int(3),
            text_lines_count=stream.read_int(4),
        )
        return info


@dataclass
class SceneTreeBlock(Block):
    # XXX not sure what the difference is
    tree_id: CrdtId
    node_id: CrdtId
    is_update: bool
    parent_id: CrdtId

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> SceneTreeBlock:
        "Parse scene tree block"

        # XXX not sure what the difference is
        tree_id = stream.read_id(1)
        node_id = stream.read_id(2)
        is_update = stream.read_bool(3)
        with stream.read_subblock(4):
            parent_id = stream.read_id(1)
            # XXX can there sometimes be something else here?

        return SceneTreeBlock(tree_id, node_id, is_update, parent_id)


@dataclass
class Point:
    x: float
    y: float
    speed: int
    direction: int
    width: int
    pressure: int

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream, version: int = 2) -> Point:
        if version not in (1, 2):
            raise ValueError("Unknown version %s" % version)
        d = stream.data
        x = d.read_float32()
        y = d.read_float32()
        if version == 1:
            # calculation based on ddvk's reader
            speed = int(round(d.read_float32() * 4))
            direction = int(round(255 * d.read_float32() / (math.pi * 2)))
            width = int(round(d.read_float32() * 4))
            pressure = int(round(d.read_float32() * 255))
        else:
            speed = d.read_uint16()
            width = d.read_uint16()
            direction = d.read_uint8()
            pressure = d.read_uint8()
        return cls(x, y, speed, direction, width, pressure)

    @classmethod
    def serialized_size(cls, version: int = 2) -> int:
        if version == 1:
            return 0x18
        elif version == 2:
            return 0x0E
        else:
            raise ValueError("Unknown version %s" % version)


@enum.unique
class Pen(enum.IntEnum):
    """
    Stroke pen id representing reMarkable tablet tools.

    Tool examples: ballpoint, fineliner, highlighter or eraser.
    """

    # XXX this list is from remt pre-v6

    BALLPOINT_1 = 2
    BALLPOINT_2 = 15
    CALIGRAPHY = 21
    ERASER = 6
    ERASER_AREA = 8
    FINELINER_1 = 4
    FINELINER_2 = 17
    HIGHLIGHTER_1 = 5
    HIGHLIGHTER_2 = 18
    MARKER_1 = 3
    MARKER_2 = 16
    MECHANICAL_PENCIL_1 = 7
    MECHANICAL_PENCIL_2 = 13
    PAINTBRUSH_1 = 0
    PAINTBRUSH_2 = 12
    PENCIL_1 = 1
    PENCIL_2 = 14

    @classmethod
    def is_highlighter(cls, value: int) -> bool:
        return value in (cls.HIGHLIGHTER_1, cls.HIGHLIGHTER_2)


@enum.unique
class PenColor(enum.IntEnum):
    """
    Color index value.
    """

    # XXX list from remt pre-v6

    BLACK = 0
    GRAY = 1
    WHITE = 2

    YELLOW = 3
    GREEN = 4
    PINK = 5

    BLUE = 6
    RED = 7

    GRAY_OVERLAP = 8


@dataclass
class Line:
    color: PenColor
    tool: Pen
    points: list[Point]
    thickness_scale: float
    starting_length: float
    # BoundingRect   image.Rectangle

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream, version: int = 2) -> Line:
        tool_id = stream.read_int(1)
        tool = Pen(tool_id)
        color_id = stream.read_int(2)
        color = PenColor(color_id)
        thickness_scale = stream.read_double(3)
        starting_length = stream.read_float(4)
        with stream.read_subblock(5) as data_length:
            point_size = Point.serialized_size(version)
            if data_length % point_size != 0:
                raise ValueError(
                    "Point data size mismatch: %d is not multiple of point_size"
                    % data_length
                )
            num_points = data_length // point_size
            points = [
                Point.from_stream(stream, version=version) for _ in range(num_points)
            ]

        # XXX unused
        timestamp = stream.read_id(6)

        return Line(color, tool, points, thickness_scale, starting_length)


@dataclass
class SceneItemBlock(Block):
    parent_id: CrdtId
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    item_type: str
    value: tp.Any

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> SceneItemBlock:
        "Group item block?"

        parent_id = stream.read_id(1)
        item_id = stream.read_id(2)
        left_id = stream.read_id(3)
        right_id = stream.read_id(4)
        deleted_length = stream.read_int(5)

        if stream.has_subblock(6):
            with stream.read_subblock(6):
                item_type = stream.data.read_uint8()
                if item_type == 2:
                    # group item
                    # XXX don't know what this means
                    value = stream.read_id(2)
                    item_label = "group"
                elif item_type == 3:
                    # line item type
                    assert stream.current_block is not None
                    version = stream.current_block.current_version
                    value = Line.from_stream(stream, version)
                    item_label = "line"
                else:
                    raise ValueError(
                        "unknown scene type %d in %s"
                        % (item_type, stream.current_block)
                    )
        else:
            item_label = "unknown"
            value = None

        return SceneItemBlock(
            parent_id, item_id, left_id, right_id, deleted_length, item_label, value
        )


@dataclass
class TextItem:
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    text: str

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> TextItem:
        with stream.read_subblock(0):
            item_id = stream.read_id(2)
            left_id = stream.read_id(3)
            right_id = stream.read_id(4)
            deleted_length = stream.read_int(5)

            if stream.has_subblock(6):
                with stream.read_subblock(6) as length:
                    assert length >= 2
                    num_chars = stream.data.read_varuint()
                    _ = stream.data.read_uint8()  # "is ascii"?
                    assert num_chars + 2 == length
                    text = stream.data.read_bytes(num_chars).decode()
            else:
                text = ""

            return TextItem(item_id, left_id, right_id, deleted_length, text)


@enum.unique
class TextFormat(enum.IntEnum):
    """
    Text format type.
    """

    PLAIN = 1
    HEADING = 2
    BOLD = 3
    BULLET = 4
    BULLET2 = 5


@dataclass
class TextFormatItem:
    # identifier or timestamp?
    item_id: CrdtId

    # Identifier for the character at start of formatting. This may be implicit,
    # based on counting on from the identifier for the start of a span of text.
    char_id: CrdtId

    format_type: TextFormat

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> TextFormatItem:
        # These are character ids, but not with an initial tag like other ids
        # have?
        a = stream.data.read_uint8()
        b = stream.data.read_varuint()
        char_id = CrdtId(a, b)

        # This seems to be the item ID for this format data? It doesn't appear
        # elsewhere in the file. Sometimes coincides with a character id but I
        # don't think it is referring to it.
        item_id = stream.read_id(1)

        with stream.read_subblock(2) as length:
            assert length == 2
            # XXX not sure what this is format?
            c = stream.data.read_uint8()
            assert c == 17
            format_type = TextFormat(stream.data.read_uint8())

        return TextFormatItem(item_id, char_id, format_type)


@dataclass
class RootTextBlock(Block):
    block_id: CrdtId
    text_items: list[TextItem]
    text_formats: list[TextFormatItem]
    pos_x: float
    pos_y: float
    width: float

    @classmethod
    def from_stream(cls, stream: TaggedBlockStream) -> RootTextBlock:
        "Parse root text block."

        block_id = stream.read_id(1)
        assert block_id == CrdtId(0, 0)

        with stream.read_subblock(2):

            # Text items
            with stream.read_subblock(1):
                with stream.read_subblock(1):
                    num_subblocks = stream.data.read_varuint()
                    text_items = [
                        TextItem.from_stream(stream) for _ in range(num_subblocks)
                    ]

            # Formatting
            with stream.read_subblock(2):
                with stream.read_subblock(1):
                    num_subblocks = stream.data.read_varuint()
                    text_formats = [
                        TextFormatItem.from_stream(stream) for _ in range(num_subblocks)
                    ]

        # Last section
        with stream.read_subblock(3):
            # "pos_x" and "pos_y" from ddvk? Gives negative number -- possibly could
            # be bounding box?
            pos_x = stream.data.read_float64()
            pos_y = stream.data.read_float64()

        # "width" from ddvk
        width = stream.read_float(4)

        return RootTextBlock(block_id, text_items, text_formats, pos_x, pos_y, width)


BLOCK_TYPES: dict[int, tp.Type[Block]] = {
    0x00: MigrationInfoBlock,
    0x01: SceneTreeBlock,
    0x02: TreeNodeBlock,
    0x04: SceneItemBlock,
    0x05: SceneItemBlock,
    0x07: RootTextBlock,
    0x09: AuthorIdsBlock,
    0x0A: PageInfoBlock,
}


def _parse_blocks(stream: TaggedBlockStream) -> Iterable[Block]:
    """
    Parse blocks from reMarkable v6 file.
    """
    while True:
        with stream.read_block() as header:
            if header is None:
                # no more blocks
                return

            if header.block_type in BLOCK_TYPES:
                block_type = BLOCK_TYPES[header.block_type]
                yield block_type.from_stream(stream)
            else:
                print("UNKNOWN BLOCK TYPE", header.block_type)
                print("SKIPPING", header.block_size, "bytes")
                stream.data.read_bytes(header.block_size)


def parse_blocks(data: tp.BinaryIO) -> Iterable[Block]:
    """
    Parse reMarkable file and return iterator of document items.

    :param data: reMarkable file data.
    """
    stream = TaggedBlockStream(data)
    stream.read_header()
    yield from _parse_blocks(stream)
