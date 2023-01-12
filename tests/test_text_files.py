from pathlib import Path
from rmscene.text import extract_text_lines, extract_text
from rmscene.scene_stream import *


DATA_PATH = Path(__file__).parent / "data"


def test_normal_ab():
    with open(DATA_PATH / "Normal_AB.rm", "rb") as f:
        lines = list(extract_text(f))
    assert lines == [(TextFormat.PLAIN, "AB")]


def test_list():
    with open(DATA_PATH / "Bold_Heading_Bullet_Normal.rm", "rb") as f:
        lines = list(extract_text(f))
    assert lines == [
        (TextFormat.BOLD, "A"),
        (TextFormat.HEADING, "new line"),
        (TextFormat.BULLET, "B is a letter of the alphabet"),
        (TextFormat.PLAIN, "C"),
    ]
