"""Data structures for the contents of a scene."""

from dataclasses import dataclass, field
import enum
import logging
import typing as tp

from .tagged_block_common import CrdtId, LwwValue
from .crdt_sequence import CrdtSequence
from .text import expand_text_items


_logger = logging.getLogger(__name__)


## Base class


@dataclass
class SceneItem:
    """Base class for items stored in scene tree."""


## Group


@dataclass
class Group(SceneItem):
    """A Group represents a group of nested items.

    Groups are used to represent layers.

    node_id is the id that this sub-tree is stored as a "SceneTreeBlock".

    children is a sequence of other SceneItems.

    `anchor_id` refers to a text character which provides the anchor y-position
    for this group. There are two values that seem to be special:
    - `0xfffffffffffe` seems to be used for lines right at the top of the page?
    - `0xffffffffffff` seems to be used for lines right at the bottom of the page?

    """

    node_id: CrdtId
    children: CrdtSequence[SceneItem] = field(default_factory=CrdtSequence)
    label: LwwValue[str] = LwwValue(CrdtId(0, 0), "")
    visible: LwwValue[bool] = LwwValue(CrdtId(0, 0), True)

    anchor_id: tp.Optional[LwwValue[CrdtId]] = None
    anchor_type: tp.Optional[LwwValue[int]] = None
    anchor_threshold: tp.Optional[LwwValue[float]] = None
    anchor_origin_x: tp.Optional[LwwValue[float]] = None


## Strokes


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


@dataclass
class Point:
    x: float
    y: float
    speed: int
    direction: int
    width: int
    pressure: int


@dataclass
class Line(SceneItem):
    color: PenColor
    tool: Pen
    points: list[Point]
    thickness_scale: float
    starting_length: float


## Text


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


END_MARKER = CrdtId(0, 0)


@dataclass
class Text(SceneItem):
    """Block of text.

    `items` are a CRDT sequence of strings. The `item_id` for each string refers
    to its first character; subsequent characters implicitly have sequential
    ids.

    `formats` are LWW values representing a mapping of character IDs to
    `TextFormat` values. These formats apply to each line of text (until the
    next newline).

    `pos_x`, `pos_y` and `width` are dimensions for the text block.

    """

    items: CrdtSequence[str]
    formats: dict[CrdtId, LwwValue[TextFormat]]
    pos_x: float
    pos_y: float
    width: float

    def formatted_lines_with_ids(self) -> tp.Iterator[tuple[TextFormat, str, list[CrdtId]]]:
        """Extract lines of text with associated formatting and char ids.

        Returns (format, line, char_ids) tuples.

        """

        char_formats = {k: lww.value for k, lww in self.formats.items()}
        if END_MARKER in char_formats:
            current_format = char_formats[END_MARKER]
        else:
            current_format = TextFormat.PLAIN

        # Expand from strings to characters
        char_items = CrdtSequence(expand_text_items(self.items.sequence_items()))

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
            if k in char_formats:
                current_format = char_formats[k]
                if char != "\n":
                    _logger.warning("format does not apply to whole line")

        yield (current_format, current_line, current_ids)

    def formatted_lines(self) -> tp.Iterator[tuple[TextFormat, str]]:
        """Extract lines of text with associated formatting.

        Returns (format, line) tuples.

        """
        for fmt, s, _ in self.formatted_lines_with_ids():
            yield (fmt, s)


## Glyph range


@dataclass
class Rectangle:
    x: float
    y: float
    w: float
    h: float


@dataclass
class GlyphRange(SceneItem):
    start: int
    length: int
    text: str
    color: PenColor
    rectangles: list[Rectangle]
