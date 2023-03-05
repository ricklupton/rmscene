"""Read structure of reMarkable tablet lines format v6

With help from ddvk's v6 reader, and enum values from remt.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
import math
from uuid import UUID
from dataclasses import dataclass, KW_ONLY
import enum
import logging
import typing as tp

from .tagged_block_common import CrdtId, LwwValue
from .tagged_block_reader import TaggedBlockReader
from .tagged_block_writer import TaggedBlockWriter

_logger = logging.getLogger(__name__)


############################################################
# Top-level block types
############################################################


@dataclass
class Block(ABC):
    BLOCK_TYPE: tp.ClassVar

    # Store any unrecognised data we can't understand
    _: KW_ONLY
    extra_data: bytes = b""

    def version_info(self, writer: TaggedBlockWriter) -> tuple[int, int]:
        """Return (min_version, current_version) to use when writing."""
        return (1, 1)

    @classmethod
    def lookup(cls, block_type: int) -> tp.Optional[tp.Type[Block]]:
        if getattr(cls, "BLOCK_TYPE", None) == block_type:
            return cls
        for subclass in cls.__subclasses__():
            if match := subclass.lookup(block_type):
                return match
        return None

    @classmethod
    @abstractmethod
    def from_stream(cls, reader: TaggedBlockReader) -> Block:
        raise NotImplementedError()

    @abstractmethod
    def to_stream(self, writer: TaggedBlockWriter):
        raise NotImplementedError()


@dataclass
class AuthorIdsBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x09

    author_uuids: dict[int, UUID]

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> AuthorIdsBlock:
        _logger.debug("Reading %s", cls.__name__)
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

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        num_subblocks = len(self.author_uuids)
        writer.data.write_varuint(num_subblocks)
        for author_id, uuid in self.author_uuids.items():
            with writer.write_subblock(0):
                writer.data.write_varuint(len(uuid.bytes_le))
                writer.data.write_bytes(uuid.bytes_le)
                writer.data.write_uint16(author_id)


@dataclass
class MigrationInfoBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x00

    migration_id: CrdtId
    is_device: bool

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> MigrationInfoBlock:
        "Parse migration info"
        _logger.debug("Reading %s", cls.__name__)
        migration_id = stream.read_id(1)
        is_device = stream.read_bool(2)
        return MigrationInfoBlock(migration_id, is_device)

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.migration_id)
        writer.write_bool(2, self.is_device)


@dataclass
class TreeNodeBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x02

    node_id: CrdtId
    label: LwwValue[str]
    visible: LwwValue[bool]

    anchor_id: tp.Optional[LwwValue[CrdtId]] = None
    anchor_type: tp.Optional[LwwValue[int]] = None
    anchor_threshold: tp.Optional[LwwValue[float]] = None
    anchor_origin_x: tp.Optional[LwwValue[float]] = None

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> TreeNodeBlock:
        "Parse tree node block."
        _logger.debug("Reading %s", cls.__name__)

        node = TreeNodeBlock(
            stream.read_id(1),
            stream.read_lww_string(2),
            stream.read_lww_bool(3),
        )

        # XXX this may need to be generalised for other examples
        if stream.bytes_remaining_in_block() > 0:
            node.anchor_id = stream.read_lww_id(7)
            node.anchor_type = stream.read_lww_byte(8)
            node.anchor_threshold = stream.read_lww_float(9)
            node.anchor_origin_x = stream.read_lww_float(10)

        return node

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.node_id)
        writer.write_lww_string(2, self.label)
        writer.write_lww_bool(3, self.visible)
        if self.anchor_id is not None:
            # FIXME group together in an anchor type?
            assert (
                self.anchor_type is not None
                and self.anchor_threshold is not None
                and self.anchor_origin_x is not None
            )
            writer.write_lww_id(7, self.anchor_id)
            writer.write_lww_byte(8, self.anchor_type)
            writer.write_lww_float(9, self.anchor_threshold)
            writer.write_lww_float(10, self.anchor_origin_x)


@dataclass
class PageInfoBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x0A

    def version_info(self, _) -> tuple[int, int]:
        """Return (min_version, current_version) to use when writing."""
        return (0, 1)

    loads_count: int
    merges_count: int
    text_chars_count: int
    text_lines_count: int

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> PageInfoBlock:
        "Parse page info block"
        _logger.debug("Reading %s", cls.__name__)
        info = PageInfoBlock(
            loads_count=stream.read_int(1),
            merges_count=stream.read_int(2),
            text_chars_count=stream.read_int(3),
            text_lines_count=stream.read_int(4),
        )
        return info

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_int(1, self.loads_count)
        writer.write_int(2, self.merges_count)
        writer.write_int(3, self.text_chars_count)
        writer.write_int(4, self.text_lines_count)


@dataclass
class SceneTreeBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x01

    # XXX not sure what the difference is
    tree_id: CrdtId
    node_id: CrdtId
    is_update: bool
    parent_id: CrdtId

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> SceneTreeBlock:
        "Parse scene tree block"
        _logger.debug("Reading %s", cls.__name__)

        # XXX not sure what the difference is
        tree_id = stream.read_id(1)
        node_id = stream.read_id(2)
        is_update = stream.read_bool(3)
        with stream.read_subblock(4):
            parent_id = stream.read_id(1)
            # XXX can there sometimes be something else here?

        return SceneTreeBlock(tree_id, node_id, is_update, parent_id)

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.tree_id)
        writer.write_id(2, self.node_id)
        writer.write_bool(3, self.is_update)
        with writer.write_subblock(4):
            writer.write_id(1, self.parent_id)


@dataclass
class Point:
    x: float
    y: float
    speed: int
    direction: int
    width: int
    pressure: int

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader, version: int = 2) -> Point:
        if version not in (1, 2):
            raise ValueError("Unknown version %s" % version)
        d = stream.data
        x = d.read_float32()
        y = d.read_float32()
        if version == 1:
            # calculation based on ddvk's reader
            # XXX removed rounding so that can round-trip correctly?
            speed = d.read_float32() * 4
            # speed = int(round(d.read_float32() * 4))
            direction = 255 * d.read_float32() / (math.pi * 2)
            # direction = int(round(255 * d.read_float32() / (math.pi * 2)))
            width = int(round(d.read_float32() * 4))
            pressure = d.read_float32() * 255
            # pressure = int(round(d.read_float32() * 255))
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

    def to_stream(self, writer: TaggedBlockWriter, version: int = 2):
        if version not in (1, 2):
            raise ValueError("Unknown version %s" % version)
        d = writer.data
        d.write_float32(self.x)
        d.write_float32(self.y)
        _logger.debug("Writing Point v%d: %s", version, self)
        if version == 1:
            # calculation based on ddvk's reader
            d.write_float32(self.speed / 4)
            d.write_float32(self.direction * (2 * math.pi) / 255)
            d.write_float32(self.width / 4)
            d.write_float32(self.pressure / 255)
        else:
            d.write_uint16(self.speed)
            d.write_uint16(self.width)
            d.write_uint8(self.direction)
            d.write_uint8(self.pressure)


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
    def from_stream(cls, stream: TaggedBlockReader, version: int = 2) -> Line:
        _logger.debug("Reading Line version %d", version)
        tool_id = stream.read_int(1)
        tool = Pen(tool_id)
        color_id = stream.read_int(2)
        color = PenColor(color_id)
        thickness_scale = stream.read_double(3)
        starting_length = stream.read_float(4)
        with stream.read_subblock(5) as block_info:
            data_length = block_info.size
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

    def to_stream(self, writer: TaggedBlockWriter, version: int = 2):
        _logger.debug("Writing Line version %d", version)
        writer.write_int(1, self.tool)
        writer.write_int(2, self.color)
        writer.write_double(3, self.thickness_scale)
        writer.write_float(4, self.starting_length)
        with writer.write_subblock(5):
            for point in self.points:
                point.to_stream(writer, version)

        # XXX didn't save
        timestamp = CrdtId(0, 1)
        writer.write_id(6, timestamp)


@dataclass
class SceneItemBlock(Block):
    parent_id: CrdtId
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    value: tp.Optional[tp.Any]

    ITEM_TYPE: tp.ClassVar[int] = 0

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> SceneItemBlock:
        "Group item block?"
        _logger.debug("Reading %s", cls.__name__)

        assert stream.current_block
        block_type = stream.current_block.block_type
        if block_type == SceneGlyphItemBlock.BLOCK_TYPE:
            subclass = SceneGlyphItemBlock
        elif block_type == SceneGroupItemBlock.BLOCK_TYPE:
            subclass = SceneGroupItemBlock
        elif block_type == SceneLineItemBlock.BLOCK_TYPE:
            subclass = SceneLineItemBlock
        elif block_type == SceneTextItemBlock.BLOCK_TYPE:
            subclass = SceneTextItemBlock
        else:
            raise ValueError(
                "unknown scene type %d in %s" % (block_type, stream.current_block)
            )

        parent_id = stream.read_id(1)
        item_id = stream.read_id(2)
        left_id = stream.read_id(3)
        right_id = stream.read_id(4)
        deleted_length = stream.read_int(5)

        if stream.has_subblock(6):
            with stream.read_subblock(6) as block_info:
                item_type = stream.data.read_uint8()
                assert item_type == subclass.ITEM_TYPE
                value = subclass.value_from_stream(stream)
            # Keep known extra data
            extra_data = block_info.extra_data
        else:
            value = None
            extra_data = b""

        return subclass(
            parent_id,
            item_id,
            left_id,
            right_id,
            deleted_length,
            value,
            extra_data=extra_data,
        )

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.parent_id)
        writer.write_id(2, self.item_id)
        writer.write_id(3, self.left_id)
        writer.write_id(4, self.right_id)
        writer.write_int(5, self.deleted_length)

        if self.value is not None:
            with writer.write_subblock(6):
                writer.data.write_uint8(self.ITEM_TYPE)
                self.value_to_stream(writer, self.value)

                writer.data.write_bytes(self.extra_data)

    @classmethod
    @abstractmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> tp.Any:
        """Read the specific content of this block"""
        raise NotImplementedError()

    @abstractmethod
    def value_to_stream(self, writer: TaggedBlockWriter, value: tp.Any):
        """Write the specific content of this block"""
        raise NotImplementedError()


# These share the same structure so can share the same implementation?


class SceneGlyphItemBlock(SceneItemBlock):
    BLOCK_TYPE: tp.ClassVar = 0x03
    ITEM_TYPE: tp.ClassVar = 0x01

    value: tp.Any

    @classmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> tp.Any:
        return None

    def value_to_stream(self, writer: TaggedBlockWriter, value):
        pass


class SceneGroupItemBlock(SceneItemBlock):
    BLOCK_TYPE: tp.ClassVar = 0x04
    ITEM_TYPE: tp.ClassVar = 0x02

    value: tp.Optional[CrdtId]

    @classmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> CrdtId:
        # XXX don't know what this means
        value = reader.read_id(2)
        return value

    def value_to_stream(self, writer: TaggedBlockWriter, value: CrdtId):
        writer.write_id(2, value)


class SceneLineItemBlock(SceneItemBlock):
    BLOCK_TYPE: tp.ClassVar = 0x05
    ITEM_TYPE: tp.ClassVar = 0x03

    value: tp.Optional[Line]

    def version_info(self, writer: TaggedBlockWriter) -> tuple[int, int]:
        """Return (min_version, current_version) to use when writing."""
        ver = writer.options.get("line_version", 2)
        return (ver, ver)

    @classmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> Line:
        assert reader.current_block is not None
        version = reader.current_block.current_version
        value = Line.from_stream(reader, version)
        return value

    def value_to_stream(self, writer: TaggedBlockWriter, value: Line):
        # XXX make sure this version ends up in block header
        version = writer.options.get("line_version", 2)
        value.to_stream(writer, version=version)


# XXX missing "PathItemBlock"? with ITEM_TYPE 0x04


class SceneTextItemBlock(SceneItemBlock):
    BLOCK_TYPE: tp.ClassVar = 0x06
    ITEM_TYPE: tp.ClassVar = 0x05

    @classmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> tp.Any:
        return None

    def value_to_stream(self, writer: TaggedBlockWriter, value):
        pass


@dataclass
class TextItem:
    item_id: CrdtId
    left_id: CrdtId
    right_id: CrdtId
    deleted_length: int
    text: str

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> TextItem:
        with stream.read_subblock(0):
            item_id = stream.read_id(2)
            left_id = stream.read_id(3)
            right_id = stream.read_id(4)
            deleted_length = stream.read_int(5)

            if stream.has_subblock(6):
                text = stream.read_string(6)
            else:
                text = ""

            return TextItem(item_id, left_id, right_id, deleted_length, text)

    def to_stream(self, writer: TaggedBlockWriter):
        with writer.write_subblock(0):
            writer.write_id(2, self.item_id)
            writer.write_id(3, self.left_id)
            writer.write_id(4, self.right_id)
            writer.write_int(5, self.deleted_length)

            if self.text:
                writer.write_string(6, self.text)


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
    def from_stream(cls, stream: TaggedBlockReader) -> TextFormatItem:
        # These are character ids, but not with an initial tag like other ids
        # have?
        a = stream.data.read_uint8()
        b = stream.data.read_varuint()
        char_id = CrdtId(a, b)

        # This seems to be the item ID for this format data? It doesn't appear
        # elsewhere in the file. Sometimes coincides with a character id but I
        # don't think it is referring to it.
        item_id = stream.read_id(1)

        with stream.read_subblock(2):
            # XXX not sure what this is format?
            c = stream.data.read_uint8()
            assert c == 17
            format_type = TextFormat(stream.data.read_uint8())

        return TextFormatItem(item_id, char_id, format_type)

    def to_stream(self, writer: TaggedBlockWriter):
        # These are character ids, but not with an initial tag like other ids
        # have?
        writer.data.write_uint8(self.char_id.part1)
        writer.data.write_varuint(self.char_id.part2)

        writer.write_id(1, self.item_id)

        with writer.write_subblock(2):
            # XXX not sure what this is format?
            c = 17
            writer.data.write_uint8(c)
            writer.data.write_uint8(self.format_type)


@dataclass
class RootTextBlock(Block):
    BLOCK_TYPE: tp.ClassVar = 0x07

    block_id: CrdtId
    text_items: list[TextItem]
    text_formats: list[TextFormatItem]
    pos_x: float
    pos_y: float
    width: float

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> RootTextBlock:
        "Parse root text block."
        _logger.debug("Reading %s", cls.__name__)

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

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.block_id)

        with writer.write_subblock(2):

            # Text items
            with writer.write_subblock(1):
                with writer.write_subblock(1):
                    writer.data.write_varuint(len(self.text_items))
                    for item in self.text_items:
                        item.to_stream(writer)

            # Formatting
            with writer.write_subblock(2):
                with writer.write_subblock(1):
                    writer.data.write_varuint(len(self.text_formats))
                    for item in self.text_formats:
                        item.to_stream(writer)

        # Last section
        with writer.write_subblock(3):
            writer.data.write_float64(self.pos_x)
            writer.data.write_float64(self.pos_y)

        # "width" from ddvk
        writer.write_float(4, self.width)


def _read_blocks(stream: TaggedBlockReader) -> Iterable[Block]:
    """
    Parse blocks from reMarkable v6 file.
    """
    while True:
        with stream.read_block() as block_info:
            if block_info is None:
                # no more blocks
                return

            block_type = Block.lookup(block_info.block_type)
            if block_type:
                yield block_type.from_stream(stream)
            else:
                _logger.error(
                    "Unknown block type %s. Skipping %d bytes.",
                    block_info.block_type,
                    block_info.size,
                )
                stream.data.read_bytes(block_info.size)


def read_blocks(data: tp.BinaryIO) -> Iterable[Block]:
    """
    Parse reMarkable file and return iterator of document items.

    :param data: reMarkable file data.
    """
    stream = TaggedBlockReader(data)
    stream.read_header()
    yield from _read_blocks(stream)


def _write_block(writer: TaggedBlockWriter, block: Block):
    min_version, current_version = block.version_info(writer)
    with writer.write_block(block.BLOCK_TYPE, min_version, current_version):
        block.to_stream(writer)


def write_blocks(
    data: tp.BinaryIO, blocks: Iterable[Block], options: tp.Optional[dict] = None
):
    """
    Write blocks to file.
    """
    stream = TaggedBlockWriter(data, options=options)
    stream.write_header()
    for block in blocks:
        _write_block(stream, block)
