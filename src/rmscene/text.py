"""Process text from remarkable scene files.

"""

from __future__ import annotations

from collections.abc import Iterable
from collections import defaultdict
from dataclasses import dataclass, field
import logging
import typing as tp

from . import scene_items as si
from .tagged_block_common import CrdtId, LwwValue
from .crdt_sequence import CrdtSequence, CrdtSequenceItem

_logger = logging.getLogger(__name__)


def expand_text_item(item: CrdtSequenceItem[str | int]) -> Iterable[CrdtSequenceItem[str] | CrdtSequenceItem[int]]:
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
    elif isinstance(item.value, int):
        yield item
        return
    else:
        # Actually the value can be empty
        # assert len(item.value) > 0
        chars = item.value
        deleted_length = 0

    if not chars:
        _logger.warning("Unexpected empty text item: %s", item)
        return

    item_id = item.item_id
    left_id = item.left_id
    for c in chars[:-1]:
        right_id = CrdtId(item_id.part1, item_id.part2 + 1)
        yield CrdtSequenceItem(item_id, left_id, right_id, deleted_length, c)
        left_id = item_id
        item_id = right_id
    yield CrdtSequenceItem(item_id, left_id, item.right_id, deleted_length, chars[-1])


def expand_text_items(items: Iterable[CrdtSequenceItem[str | int]]) -> Iterable[CrdtSequenceItem[str] | CrdtSequenceItem[int]]:
    """Expand a sequence of TextItems into single-character TextItems."""
    for item in items:
        yield from expand_text_item(item)


@dataclass
class CrdtStr:
    s: str = ""
    i: list[CrdtId] = field(default_factory=list)

    def __str__(self):
        return self.s


@dataclass
class TextSpan:
    """Base class for text spans with formatting."""
    contents: list[tp.Union["TextSpan", CrdtStr]]


class BoldSpan(TextSpan):
    pass


class ItalicSpan(TextSpan):
    pass


@dataclass
class Paragraph:
    """Paragraph of text."""
    contents: list[TextSpan]
    start_id: CrdtId
    style: LwwValue[si.ParagraphStyle]

    def __str__(self):
        return "".join(str(s) for s in self.contents)


@dataclass
class TextDocument:

    contents: list[Paragraph]

    @classmethod
    def from_scene_item(cls, text: si.Text):
        """Extract spans of text with associated formatting and char ids.

        This uses the inline formatting introduced in v3.3.2.
        """

        char_formats = {k: lww.value for k, lww in text.styles.items()}
        if si.END_MARKER not in char_formats:
            char_formats[si.END_MARKER] = si.ParagraphStyle.PLAIN

        # Expand from strings to characters
        char_items = CrdtSequence(expand_text_items(text.items.sequence_items()))
        keys = list(char_items)
        last_linebreak = si.END_MARKER

        span_start_codes = {
            1: BoldSpan,
            3: ItalicSpan,
        }
        span_end_codes = {
            2: BoldSpan,
            4: ItalicSpan,
        }

        def parse_paragraph_contents():
            nonlocal last_linebreak
            stack = [(None, [])]
            k = None
            done = False
            while keys:
                # If we've seen a newline character, only interested in
                # span-closing format codes.
                if done and char_items[keys[0]] not in (2, 4):
                    break

                k = keys.pop(0)
                char = char_items[k]
                if isinstance(char, int):
                    if char in span_start_codes:
                        span_type = span_start_codes[char]
                        stack.append((span_type, []))
                    elif char in span_end_codes:
                        span_type, nested = stack.pop()
                        if span_type is not span_end_codes[char]:
                            _logger.error("Unexpected end of span at %s: got %s, expected %s",
                                          k, span_end_codes[char], span_type)
                        stack[-1][1].append(span_type(nested))
                    else:
                        _logger.warning("Unknown format code %d at %s!", char, k)
                elif char == "\n":
                    # End of paragraph
                    done = True
                    last_linebreak = k
                else:
                    assert len(char) <= 1
                    _, contents = stack[-1]
                    if not contents or not isinstance(contents[-1], CrdtStr):
                        contents += [CrdtStr()]
                    contents[-1].s += char
                    contents[-1].i += [k]

            if len(stack) > 1:
                _logger.error("Unbalanced stack! %s", stack)

            _, contents = stack[-1]
            return contents

        paragraphs = []
        while keys:
            style = text.styles.get(last_linebreak, LwwValue(CrdtId(0, 0), si.ParagraphStyle.PLAIN))
            contents = parse_paragraph_contents()
            p = Paragraph(contents, last_linebreak, style)
            paragraphs += [p]

        doc = cls(paragraphs)
        return doc

        # if k in char_formats:
        #     current_format = char_formats[k]
        #     if char != "\n":
        #         _logger.warning("format does not apply to whole line")
