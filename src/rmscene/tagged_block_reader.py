"""Read structure of remarkable .rm files version 6.

Based on my investigation of the format with lots of help from ddvk's v6 reader
code.

"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import typing as tp

from .tagged_block_common import DataStream, TagType, CrdtId, UnexpectedBlockError, LwwValue


_logger = logging.getLogger(__name__)


@dataclass
class BlockHeader:
    "Top-level block header information."
    block_type: int
    min_version: int
    current_version: int
    block_size: int = None
    offset: tp.Optional[int] = None


class BlockOverflowError(Exception):
    """Read past end of block."""


class TaggedBlockReader:
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

    ## Read simple values

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
        _logger.debug("Block header: %d %d %d", min_version, current_version, block_type)
        assert unknown == 0
        assert current_version >= 0
        assert min_version >= 0
        assert min_version <= current_version

        i0 = self.data.tell()
        self.current_block = BlockHeader(
            block_type=block_type,
            min_version=min_version,
            current_version=current_version,
            block_size=block_length,
            offset=i0,
        )

        yield self.current_block

        assert self.current_block is not None
        self._check_position("Block", i0, block_length)
        self.current_block = None

    def bytes_remaining_in_block(self) -> int:
        """Return the number of bytes remaining in the current block."""
        header = self.current_block
        if header is None or header.offset is None:
            raise ValueError("Not in a block")
        return header.offset + header.block_size - self.data.tell()

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

    def read_lww_bool(self, index: int) -> LwwValue[bool]:
        "Read a LWW bool."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_bool(2)
        return LwwValue(timestamp, value)

    def read_lww_byte(self, index: int) -> LwwValue[int]:
        "Read a LWW byte."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_byte(2)
        return LwwValue(timestamp, value)

    def read_lww_float(self, index: int) -> LwwValue[float]:
        "Read a LWW float."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            value = self.read_float(2)
        return LwwValue(timestamp, value)

    def read_lww_id(self, index: int) -> LwwValue[CrdtId]:
        "Read a LWW ID."
        with self.read_subblock(index):
            # XXX ddvk has these the other way round?
            timestamp = self.read_id(1)
            value = self.read_id(2)
        return LwwValue(timestamp, value)

    def read_lww_string(self, index: int) -> LwwValue[str]:
        "Read a LWW string."
        with self.read_subblock(index):
            timestamp = self.read_id(1)
            string = self.read_string(2)
        return LwwValue(timestamp, string)

    def read_string(self, index: int) -> str:
        """Read a standard string block."""
        with self.read_subblock(index) as block_length:
            string_length = self.data.read_varuint()
            # XXX not sure if this is right meaning?
            is_ascii = self.data.read_bool()
            assert is_ascii == 1
            assert string_length + 2 == block_length
            string = self.data.read_bytes(string_length).decode()
            return string
