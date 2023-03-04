from uuid import UUID
from io import BytesIO
from pathlib import Path
from rmscene.text import extract_text_lines, extract_text, simple_text_document, anchor_positions
from rmscene.scene_stream import *


DATA_PATH = Path(__file__).parent / "data"


def _hex_lines(b, n=32):
    return [
        b[i*n:(i+1)*n].hex()
        for i in range(len(b) // n + 1)
    ]


def test_normal_ab():
    with open(DATA_PATH / "Normal_AB.rm", "rb") as f:
        lines = list(extract_text(f))
    assert lines == [(TextFormat.PLAIN, "AB")]


def test_list():
    with open(DATA_PATH / "Bold_Heading_Bullet_Normal.rm", "rb") as f:
        lines = list(extract_text(f))
    assert lines == [
        (TextFormat.BOLD, "A\n"),
        (TextFormat.HEADING, "new line\n"),
        (TextFormat.BULLET, "B is a letter of the alphabet\n"),
        (TextFormat.PLAIN, "C"),
    ]


def test_simple_text_document():
    test_file = "Normal_AB.rm"
    with open(DATA_PATH / test_file, "rb") as f:
        expected = f.read()

    output_buf = BytesIO()
    author_id = UUID('495ba59f-c943-2b5c-b455-3682f6948906')
    write_blocks(output_buf, simple_text_document("AB", author_id))

    assert _hex_lines(output_buf.getvalue()) == _hex_lines(expected)


def test_anchor_positions_1():
    result = anchor_positions([
        (TextFormat.PLAIN, "AB", [CrdtId(1, 10), CrdtId(1, 11)])
    ], [CrdtId(1, 10)])

    assert result == {
        CrdtId(1, 10): 0,
    }


def test_anchor_positions_2():
    result = anchor_positions([
        (TextFormat.PLAIN, "AB\n", [CrdtId(1, 10), CrdtId(1, 11), CrdtId(1, 12)]),
        (TextFormat.PLAIN, "CD\n", [CrdtId(1, 13), CrdtId(1, 14), CrdtId(1, 15)]),
    ])

    assert result == {
        CrdtId(1, 10): 0,
        CrdtId(1, 11): 0,
        CrdtId(1, 12): 0,
        CrdtId(1, 13): 30,
        CrdtId(1, 14): 30,
        CrdtId(1, 15): 30,
    }


def test_anchor_positions_heading_taller_than_plain():
    result1 = anchor_positions([
        (TextFormat.PLAIN, "AB\n", [CrdtId(1, 10), CrdtId(1, 11), CrdtId(1, 12)]),
        (TextFormat.PLAIN, "CD\n", [CrdtId(1, 13), CrdtId(1, 14), CrdtId(1, 15)]),
    ], [CrdtId(1, 13)])

    result2 = anchor_positions([
        (TextFormat.HEADING, "AB\n", [CrdtId(1, 10), CrdtId(1, 11), CrdtId(1, 12)]),
        (TextFormat.PLAIN, "CD\n", [CrdtId(1, 13), CrdtId(1, 14), CrdtId(1, 15)]),
    ], [CrdtId(1, 13)])

    assert result2[CrdtId(1, 13)] > result1[CrdtId(1, 13)]
