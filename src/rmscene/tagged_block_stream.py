"""Read structure of remarkable .rm files version 6.

Based on my investigation of the format with lots of help from ddvk's v6 reader
code.

"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import enum
import logging
import struct
import typing as tp


_logger = logging.getLogger(__name__)


HEADER_V6 = b"reMarkable .lines file, version=6          "


class TagType(enum.IntEnum):
    "Tag type representing the type of following data."
    ID = 0xF
    Length4 = 0xC
    Byte8 = 0x8
    Byte4 = 0x4
    Byte1 = 0x1


class DataStream:
    """Read basic values from a remarkable v6 file stream."""

    def __init__(self, data: tp.BinaryIO):
        self.data = data

    def tell(self) -> int:
        return self.data.tell()

    def read_header(self) -> None:
        """Read the file header.

        This should be the first call when starting to read a new file.

        """
        header = self.read_bytes(len(HEADER_V6))
        if header != HEADER_V6:
            raise ValueError("Wrong header: %r" % header)

    def check_tag(self, expected_index: int, expected_type: TagType) -> bool:
        """Check that INDEX and TAG_TYPE are next.

        Returns True if the expected index and tag type are found. Does not
        advance the stream.

        """
        pos = self.data.tell()
        try:
            index, tag_type = self._read_tag_values()
            return (index == expected_index) and (tag_type == expected_type)
        except (ValueError, EOFError):
            return False
        finally:
            self.data.seek(pos)  # Go back

    def read_tag(
        self, expected_index: int, expected_type: TagType
    ) -> tuple[int, TagType]:
        """Read a tag from the stream.

        Raise an error if the expected index and tag type are not found, and
        rewind the stream.

        """
        pos = self.data.tell()
        index, tag_type = self._read_tag_values()

        if index != expected_index:
            self.data.seek(pos)  # Go back
            raise UnexpectedBlockError(
                "Expected index %d, got %d, at position %d"
                % (expected_index, index, self.data.tell())
            )

        if tag_type != expected_type:
            self.data.seek(pos)  # Go back
            raise UnexpectedBlockError(
                "Expected tag type %s (0x%X), got 0x%X at position %d"
                % (
                    expected_type.name,
                    expected_type.value,
                    tag_type,
                    self.data.tell(),
                )
            )

        return index, tag_type

    def _read_tag_values(self) -> tuple[int, TagType]:
        """Read tag values from the stream."""

        x = self.read_varuint()

        # First part is an index number that identifies if this is the right
        # data we're expecting
        index = x >> 4

        # Second part is a tag type that identifies what kind of data it is
        tag_type = x & 0xF
        try:
            tag_type = TagType(tag_type)
        except ValueError as e:
            raise ValueError(
                "Bad tag type 0x%X at position %d" % (tag_type, self.data.tell())
            )

        return index, tag_type

    def read_bytes(self, n: int) -> bytes:
        "Read `n` bytes, raising `EOFError` if there are not enough."
        result = self.data.read(n)
        if len(result) != n:
            raise EOFError()
        return result

    def _read_struct(self, pattern: str):
        pattern = "<" + pattern
        n = struct.calcsize(pattern)
        return struct.unpack(pattern, self.read_bytes(n))[0]

    def read_bool(self) -> bool:
        """Read a bool from the data stream."""
        return self._read_struct("?")

    def read_varuint(self) -> int:
        """Read a varuint from the data stream."""
        shift = 0
        result = 0
        while True:
            i = ord(self.read_bytes(1))
            result |= (i & 0x7F) << shift
            shift += 7
            if not (i & 0x80):
                break
        return result

    def read_uint8(self) -> int:
        """Read a uint8 from the data stream."""
        return self._read_struct("B")

    def read_uint16(self) -> int:
        """Read a uint16 from the data stream."""
        return self._read_struct("H")

    def read_uint32(self) -> int:
        """Read a uint32 from the data stream."""
        return self._read_struct("I")

    def read_float32(self) -> float:
        """Read a float32 from the data stream."""
        return self._read_struct("f")

    def read_float64(self) -> float:
        """Read a float64 (double) from the data stream."""
        return self._read_struct("d")


@dataclass
class BlockHeader:
    "Top-level block header information."
    block_size: int
    block_type: int
    min_version: int
    current_version: int
    offset: tp.Optional[int] = None


@dataclass(eq=True, order=True, frozen=True)
class CrdtId:
    "An identifier or timestamp."
    part1: int
    part2: int

    def __repr__(self) -> str:
        return f"CrdtId({self.part1}, {self.part2})"


class UnexpectedBlockError(Exception):
    """Unexpected tag or index in block stream."""


class BlockOverflowError(Exception):
    """Read past end of block."""


class TaggedBlockStream:
    """Read blocks and values from a remarkable v6 file stream."""

    def __init__(self, data: tp.BinaryIO):
        rm_data = DataStream(data)
        self.data = rm_data
        self.current_block: tp.Optional[BlockHeader] = None

    def read_header(self) -> None:
        """Read the file header.

        This should be the first call when starting to read a new file.

        """
        self.data.read_header()

    def bytes_remaining_in_block(self) -> int:
        """Return the number of bytes remaining in the current block."""
        header = self.current_block
        if header is None or header.offset is None:
            raise ValueError("Not in a block")
        return header.offset + header.block_size - self.data.tell()

    def read_id(self, index: int) -> CrdtId:
        """Read a tagged CRDT ID."""
        self.data.read_tag(index, TagType.ID)

        # Based on ddvk's reader.go
        # TODO: should be var unit?
        part1 = self.data.read_uint8()
        part2 = self.data.read_varuint()
        # result = (part1 << 48) | part2
        result = CrdtId(part1, part2)
        return result

    def read_bool(self, index: int) -> bool:
        """Read a tagged bool."""
        self.data.read_tag(index, TagType.Byte1)
        result = self.data.read_bool()
        return result

    def read_byte(self, index: int) -> int:
        """Read a tagged byte as an unsigned integer."""
        self.data.read_tag(index, TagType.Byte1)
        result = self.data.read_uint8()
        return result

    def read_int(self, index: int) -> int:
        """Read a tagged 4-byte unsigned integer."""
        self.data.read_tag(index, TagType.Byte4)
        # TODO: is this supposed to be signed or unsigned?
        result = self.data.read_uint32()
        return result

    def read_float(self, index: int) -> float:
        """Read a tagged 4-byte float."""
        self.data.read_tag(index, TagType.Byte4)
        result = self.data.read_float32()
        return result

    def read_double(self, index: int) -> float:
        """Read a tagged 8-byte double."""
        self.data.read_tag(index, TagType.Byte8)
        result = self.data.read_float64()
        return result

    ## Blocks

    @contextmanager
    def read_block(self) -> Iterator[tp.Optional[BlockHeader]]:
        """Read a top-level block header.

        This acts as a context manager. Upon exiting the with-block, the amount
        of data read is checked and an error raised if it has not reached the
        end of the block.

        Returns the `BlockHeader` if successfully read. If no block can be read,
        None is returned.

        """
        if self.current_block is not None:
            raise UnexpectedBlockError("Already in a block")

        try:
            block_length = self.data.read_uint32()
        except EOFError:
            yield None  # no more blocks to read
            return

        unknown = self.data.read_uint8()
        min_version = self.data.read_uint8()
        current_version = self.data.read_uint8()
        block_type = self.data.read_uint8()
        assert unknown == 0
        assert current_version >= 0
        assert min_version >= 0 and min_version <= current_version

        i0 = self.data.tell()
        self.current_block = BlockHeader(
            block_size=block_length,
            block_type=block_type,
            min_version=min_version,
            current_version=current_version,
            offset=i0,
        )

        yield self.current_block

        assert self.current_block is not None
        self._check_position("Block", i0, block_length)
        self.current_block = None

    @contextmanager
    def read_subblock(self, index: int) -> Iterator[int]:
        """Read a subblock length and return as context object.

        Checks that the correct length has been read at the end of the with
        block.

        If `optional` is True and the block is not found, return None.
        """
        self.data.read_tag(index, TagType.Length4)
        subblock_length = self.data.read_uint32()
        i0 = self.data.tell()

        yield subblock_length

        self._check_position("Sub-block", i0, subblock_length)

    def has_subblock(self, index: int) -> bool:
        """Check if a subblock with the given index is next."""
        return self.data.check_tag(index, TagType.Length4)

    def _check_position(self, what: str, i0: int, length: int):
        i1 = self.data.tell()
        if i1 > i0 + length:
            raise BlockOverflowError(
                "%s starting at %d, length %d, read up to %d (overflow by %d)"
                % (what, i0, length, i1, i1 - (i0 + length))
            )
        if i1 < i0 + length:
            _logger.warning(
                "%s starting at %d, length %d, only read %d"
                % (what, i0, length, i1 - i0)
            )

    ## Higher level constructs

    def read_lww_bool(self, index: int) -> tuple[CrdtId, bool]:
        "Read a LWW bool."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_bool(2)
        return timestamp, value

    def read_lww_byte(self, index: int) -> tuple[CrdtId, int]:
        "Read a LWW byte."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_byte(2)
        return timestamp, value

    def read_lww_float(self, index: int) -> tuple[CrdtId, float]:
        "Read a LWW float."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_float(2)
        return timestamp, value

    def read_lww_id(self, index: int) -> tuple[CrdtId, CrdtId]:
        "Read a LWW ID."
        with self.read_subblock(index):
            # XXX ddvk has these the other way round?
            timestamp = self.read_id(1)
            value = self.read_id(2)
        return timestamp, value

    def read_lww_string(self, index: int) -> tuple[CrdtId, str]:
        "Read a LWW string."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            with self.read_subblock(2) as block_length:
                string_length = self.data.read_varuint()
                # XXX not sure if this is right meaning?
                is_ascii = self.data.read_bool()
                assert is_ascii == 1
                assert string_length + 2 == block_length
                string = self.data.read_bytes(string_length).decode()
        return timestamp, string
