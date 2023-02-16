"""Read structure of reMarkable tablet lines format v6

With help from ddvk's v6 reader, and enum values from remt.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
import math
from uuid import UUID
from dataclasses import dataclass, replace, KW_ONLY
import enum
import logging
import typing as tp

from .tagged_block_common import CrdtId, LwwValue
from .tagged_block_reader import TaggedBlockReader
from .tagged_block_writer import TaggedBlockWriter
from .crdt_sequence import CrdtSequence, CrdtSequenceItem
from .scene_tree import SceneTree
from . import scene_items as si

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

    group: si.Group

    @classmethod
    def from_stream(cls, stream: TaggedBlockReader) -> TreeNodeBlock:
        "Parse tree node block."
        _logger.debug("Reading %s", cls.__name__)

        group = si.Group(
            node_id=stream.read_id(1),
            label=stream.read_lww_string(2),
            visible=stream.read_lww_bool(3),
        )

        # XXX this may need to be generalised for other examples
        if stream.bytes_remaining_in_block() > 0:
            group.anchor_id = stream.read_lww_id(7)
            group.anchor_type = stream.read_lww_byte(8)
            group.anchor_threshold = stream.read_lww_float(9)
            group.anchor_origin_x = stream.read_lww_float(10)

        return cls(group)

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        group = self.group
        writer.write_id(1, group.node_id)
        writer.write_lww_string(2, group.label)
        writer.write_lww_bool(3, group.visible)
        if group.anchor_id is not None:
            # FIXME group together in an anchor type?
            assert (
                group.anchor_type is not None
                and group.anchor_threshold is not None
                and group.anchor_origin_x is not None
            )
            writer.write_lww_id(7, group.anchor_id)
            writer.write_lww_byte(8, group.anchor_type)
            writer.write_lww_float(9, group.anchor_threshold)
            writer.write_lww_float(10, group.anchor_origin_x)


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

        # XXX not sure what the difference is. This "tree_id" is used as the
        # plain "Id" in the SceneTree.NodeMap in ddvk's reader. If the parent_id
        # is equal to the root_id (1, 1), this node represents a layer.
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


def point_from_stream(stream: TaggedBlockReader, version: int = 2) -> si.Point:
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
    return si.Point(x, y, speed, direction, width, pressure)


def point_serialized_size(version: int = 2) -> int:
    if version == 1:
        return 0x18
    elif version == 2:
        return 0x0E
    else:
        raise ValueError("Unknown version %s" % version)


def point_to_stream(point: si.Point, writer: TaggedBlockWriter, version: int = 2):
    if version not in (1, 2):
        raise ValueError("Unknown version %s" % version)
    d = writer.data
    d.write_float32(point.x)
    d.write_float32(point.y)
    _logger.debug("Writing Point v%d: %s", version, point)
    if version == 1:
        # calculation based on ddvk's reader
        d.write_float32(point.speed / 4)
        d.write_float32(point.direction * (2 * math.pi) / 255)
        d.write_float32(point.width / 4)
        d.write_float32(point.pressure / 255)
    else:
        d.write_uint16(point.speed)
        d.write_uint16(point.width)
        d.write_uint8(point.direction)
        d.write_uint8(point.pressure)


def line_from_stream(stream: TaggedBlockReader, version: int = 2) -> si.Line:
    _logger.debug("Reading Line version %d", version)
    tool_id = stream.read_int(1)
    tool = si.Pen(tool_id)
    color_id = stream.read_int(2)
    color = si.PenColor(color_id)
    thickness_scale = stream.read_double(3)
    starting_length = stream.read_float(4)
    with stream.read_subblock(5) as block_info:
        data_length = block_info.size
        point_size = point_serialized_size(version)
        if data_length % point_size != 0:
            raise ValueError(
                "Point data size mismatch: %d is not multiple of point_size"
                % data_length
            )
        num_points = data_length // point_size
        points = [
            point_from_stream(stream, version=version) for _ in range(num_points)
        ]

    # XXX unused
    timestamp = stream.read_id(6)

    return si.Line(color, tool, points, thickness_scale, starting_length)


def line_to_stream(line: si.Line, writer: TaggedBlockWriter, version: int = 2):
    _logger.debug("Writing Line version %d", version)
    writer.write_int(1, line.tool)
    writer.write_int(2, line.color)
    writer.write_double(3, line.thickness_scale)
    writer.write_float(4, line.starting_length)
    with writer.write_subblock(5):
        for point in line.points:
            point_to_stream(point, writer, version)

    # XXX didn't save
    timestamp = CrdtId(0, 1)
    writer.write_id(6, timestamp)


@dataclass
class SceneItemBlock(Block):
    parent_id: CrdtId
    item: CrdtSequenceItem

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
            CrdtSequenceItem(item_id, left_id, right_id, deleted_length, value),
            extra_data=extra_data,
        )

    def to_stream(self, writer: TaggedBlockWriter):
        _logger.debug("Writing %s", type(self).__name__)
        writer.write_id(1, self.parent_id)
        writer.write_id(2, self.item.item_id)
        writer.write_id(3, self.item.left_id)
        writer.write_id(4, self.item.right_id)
        writer.write_int(5, self.item.deleted_length)

        if self.item.value is not None:
            with writer.write_subblock(6):
                writer.data.write_uint8(self.ITEM_TYPE)
                self.value_to_stream(writer, self.item.value)

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

    value: tp.Optional[si.Line]

    def version_info(self, writer: TaggedBlockWriter) -> tuple[int, int]:
        """Return (min_version, current_version) to use when writing."""
        ver = writer.options.get("line_version", 2)
        return (ver, ver)

    @classmethod
    def value_from_stream(cls, reader: TaggedBlockReader) -> si.Line:
        assert reader.current_block is not None
        version = reader.current_block.current_version
        value = line_from_stream(reader, version)
        return value

    def value_to_stream(self, writer: TaggedBlockWriter, value: si.Line):
        # XXX make sure this version ends up in block header
        version = writer.options.get("line_version", 2)
        line_to_stream(value, writer, version=version)


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
class TextItem(CrdtSequenceItem[str]):

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

            if self.value:
                writer.write_string(6, self.value)


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


def build_tree(tree: SceneTree, blocks: Iterable[Block]):
    for b in blocks:
        if isinstance(b, SceneTreeBlock):
            # XXX check node_id and is_update
            # pending_tree_nodes[b.tree_id] = b
            tree.add_node(b.tree_id, parent_id=b.parent_id)
        elif isinstance(b, TreeNodeBlock):
            # Expect this node to already exist; adding information
            # if b.node_id not in pending_tree_nodes:
            if b.group.node_id not in tree:
                raise ValueError("Node does not exist for TreeNodeBlock: %s" % b.group.node_id)
            node = tree[b.group.node_id]
            node.label = b.group.label
            node.visible = b.group.visible
        elif isinstance(b, SceneGroupItemBlock):
            # Add this entry to children of parent_id
            node_id = b.item.value
            if node_id not in tree:
                raise ValueError("Node does not exist for SceneGroupItemBlock: %s" % node_id)
            item = replace(b.item, value=tree[node_id])
            tree.add_item(item, b.parent_id)
        elif isinstance(b, SceneLineItemBlock):
            # Add this entry to children of parent_id
            tree.add_item(b.item, b.parent_id)

    pass
