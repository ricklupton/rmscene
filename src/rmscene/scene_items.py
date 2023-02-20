"""Data structures for the contents of a scene."""

from dataclasses import dataclass, field
import enum
import logging
import typing as tp

from .tagged_block_common import CrdtId, LwwValue
from .tagged_block_reader import TaggedBlockReader
from .tagged_block_writer import TaggedBlockWriter
from .crdt_sequence import CrdtSequence, CrdtSequenceItem

_logger = logging.getLogger(__name__)


@dataclass
class SceneItem:
    """Base class for items stored in scene tree."""


@dataclass
class GlyphHighlight(SceneItem):
    """A GlyphItem represents some highlighted text."""


@dataclass
class Group(SceneItem):
    """A Group represents a group of nested items.

    Groups are used to represent layers.

    node_id is the id that this sub-tree is stored as a "SceneTreeBlock".

    children is a sequence of other SceneItems.

    """

    node_id: CrdtId
    children: CrdtSequence[SceneItem] = field(default_factory=CrdtSequence)
    label: LwwValue[str] = LwwValue(CrdtId(0, 0), "")
    visible: LwwValue[bool] = LwwValue(CrdtId(0, 0), True)

    anchor_id: tp.Optional[LwwValue[CrdtId]] = None
    anchor_type: tp.Optional[LwwValue[int]] = None
    anchor_threshold: tp.Optional[LwwValue[float]] = None
    anchor_origin_x: tp.Optional[LwwValue[float]] = None

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


class Text(SceneItem):
    """Not sure how this is used."""


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
