from uuid import UUID
from io import BytesIO
from pathlib import Path
from rmscene.scene_stream import *
from rmscene.scene_items import Text, ParagraphStyle
from rmscene.text import TextDocument, CrdtStr, BoldSpan, ItalicSpan

DATA_PATH = Path(__file__).parent / "data"


def _hex_lines(b, n=32):
    return [
        b[i*n:(i+1)*n].hex()
        for i in range(len(b) // n + 1)
    ]


def extract_doc(filename):
    with open(filename, "rb") as f:
        tree = read_tree(f)
        assert tree.root_text
        doc = TextDocument.from_scene_item(tree.root_text)
        return doc


def strip_ids(x):
    if isinstance(x, CrdtStr):
        return x.s
    else:
        return type(x)([strip_ids(y) for y in x.contents])


def formatted_lines(doc):
    return [
        (p.style.value, str(p)) for p in doc.contents
    ]


def extract_paragraphs(filename):
    with open(filename, "rb") as f:
        tree = read_tree(f)
        assert tree.root_text


def test_normal_ab():
    lines = formatted_lines(extract_doc(DATA_PATH / "Normal_AB.rm"))
    assert lines == [(ParagraphStyle.PLAIN, "AB")]


def test_list():
    lines = formatted_lines(extract_doc(DATA_PATH / "Bold_Heading_Bullet_Normal.rm"))
    assert lines == [
        (ParagraphStyle.BOLD, "A"),
        (ParagraphStyle.HEADING, "new line"),
        (ParagraphStyle.BULLET, "B is a letter of the alphabet"),
        (ParagraphStyle.PLAIN, "C"),
    ]


def test_inline_formats():
    doc = extract_doc(DATA_PATH / "Normal_A_stroke_2_layers_v3.3.2.rm")
    lines = [
        (p.style.value, [strip_ids(x) for x in p.contents])
        for p in doc.contents
    ]
    assert lines == [
        (ParagraphStyle.PLAIN, ["A"]),
        (ParagraphStyle.PLAIN, ["v3.2.2"]),
        (ParagraphStyle.PLAIN, ["Normal ", BoldSpan(["bold"]), " ", ItalicSpan(["italic"])]),
        (ParagraphStyle.PLAIN, [BoldSpan(["Bold"]), " ", ItalicSpan(["italic"]), " normal"]),
        (ParagraphStyle.BOLD, ["Bold line"]),
        (ParagraphStyle.PLAIN, ["Normal line"]),
        (ParagraphStyle.HEADING, ["Heading line"]),
    ]



def test_simple_text_document():
    test_file = "Normal_AB.rm"
    with open(DATA_PATH / test_file, "rb") as f:
        expected = f.read()

    output_buf = BytesIO()
    author_id = UUID('495ba59f-c943-2b5c-b455-3682f6948906')
    write_blocks(
        output_buf, simple_text_document("AB", author_id), options={"version": "3.0"}
    )

    assert _hex_lines(output_buf.getvalue()) == _hex_lines(expected)
