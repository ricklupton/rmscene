from uuid import UUID
from io import BytesIO
from pathlib import Path
from rmscene.scene_stream import *
from rmscene.scene_items import Text, TextFormat


DATA_PATH = Path(__file__).parent / "data"


def _hex_lines(b, n=32):
    return [
        b[i*n:(i+1)*n].hex()
        for i in range(len(b) // n + 1)
    ]


def extract_text(filename):
    with open(filename, "rb") as f:
        tree = read_tree(f)
        assert tree.root_text
        return [(fmt, s) for fmt, s, _ in tree.root_text.formatted_lines()]


def test_normal_ab():
    lines = extract_text(DATA_PATH / "Normal_AB.rm")
    assert lines == [(TextFormat.PLAIN, "AB")]


def test_list():
    lines = extract_text(DATA_PATH / "Bold_Heading_Bullet_Normal.rm")
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
