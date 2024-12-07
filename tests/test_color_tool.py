from pathlib import Path

import pytest

from rmscene import SceneGlyphItemBlock, SceneLineItemBlock, read_blocks
from rmscene.scene_items import Pen, PenColor

DATA_PATH = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    "block_type,colors,tools",
    [
        (SceneGlyphItemBlock, {PenColor.HIGHLIGHT}, None),
        (SceneLineItemBlock, {PenColor.HIGHLIGHT}, {Pen.SHADER}),
        (
            SceneLineItemBlock,
            {PenColor.GREEN_2, PenColor.CYAN, PenColor.MAGENTA},
            {Pen.BALLPOINT_2},
        ),
    ],
)
def test_color_tool_parsing(block_type, colors, tools):
    FILE_NAME = DATA_PATH / "Color_and_tool_v3.14.4.rm"
    with open(FILE_NAME, "rb") as f:
        result = read_blocks(f)
        for el in result:
            if not getattr(el, "item", None):
                continue
            if not getattr(el.item, "value", None):
                continue
            if isinstance(el, block_type) and el.item.value.color in colors:
                if tools is None:
                    continue
                assert el.item.value.tool in tools, "Tool and colors don't match"


def test_highlight_shader_colors():
    FILE_NAME = DATA_PATH / "More_color_highlight_shader_v3.15.4.2.rm"
    with open(FILE_NAME, "rb") as f:
        result = read_blocks(f)
        expected_colors = [
            PenColor.HIGHLIGHT_YELLOW,
            PenColor.HIGHLIGHT_BLUE,
            PenColor.HIGHLIGHT_PINK,
            PenColor.HIGHLIGHT_ORANGE,
            PenColor.HIGHLIGHT_GREEN,
            PenColor.HIGHLIGHT_GRAY,
            PenColor.SHADER_GRAY,
            PenColor.SHADER_ORANGE,
            PenColor.SHADER_MAGENTA,
            PenColor.SHADER_BLUE,
            PenColor.SHADER_RED,
            PenColor.SHADER_GREEN,
            PenColor.SHADER_YELLOW,
            PenColor.SHADER_CYAN,
            PenColor.BLACK,
            PenColor.GRAY,
            PenColor.WHITE,
            PenColor.BLUE,
            PenColor.RED,
            PenColor.GREEN_2,
            PenColor.YELLOW_2,
            PenColor.CYAN,
            PenColor.MAGENTA,
        ]
        start = 0
        for block in result:
            if isinstance(block, SceneLineItemBlock) and block.item.value:
                assert (
                    block.item.value.color == expected_colors[start]
                ), f"Unexpected color {block.item.value.color} at index {start}"
                start += 1
        assert start == len(expected_colors)
