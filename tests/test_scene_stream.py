import pytest
from io import BytesIO
from pathlib import Path
from uuid import UUID
from rmscene import read_blocks, write_blocks, LwwValue, TaggedBlockWriter, TaggedBlockReader
from rmscene.scene_stream import *
from rmscene.tagged_block_common import HEADER_V6

import logging
logger = logging.getLogger(__name__)


DATA_PATH = Path(__file__).parent / "data"


def _hex_lines(b, n=32):
    return [
        b[i*n:(i+1)*n].hex()
        for i in range(len(b) // n + 1)
    ]


@pytest.mark.parametrize(
    "test_file,line_version",
    [
        ("Normal_AB.rm", 1),
        ("Normal_A_stroke_2_layers.rm", 1),
        ("Bold_Heading_Bullet_Normal.rm", 1),
        ("Lines_v2.rm", 2),
        ("Lines_v2_updated.rm", 2),  # extra 7fXXXX part of Line data was added
    ],
)
def test_full_roundtrip(test_file, line_version):
    with open(DATA_PATH / test_file, "rb") as f:
        data = f.read()

    input_buf = BytesIO(data)
    output_buf = BytesIO()
    options = {"line_version": line_version}

    write_blocks(output_buf, read_blocks(input_buf), options)

    assert _hex_lines(input_buf.getvalue()) == _hex_lines(output_buf.getvalue())


def test_normal_ab():
    with open(DATA_PATH / "Normal_AB.rm", "rb") as f:
        result = list(read_blocks(f))

    assert result == [
        AuthorIdsBlock(author_uuids={1: UUID("495ba59f-c943-2b5c-b455-3682f6948906")}),
        MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True),
        PageInfoBlock(
            loads_count=1, merges_count=0, text_chars_count=3, text_lines_count=1
        ),
        SceneTreeBlock(
            tree_id=CrdtId(0, 11),
            node_id=CrdtId(0, 0),
            is_update=True,
            parent_id=CrdtId(0, 1),
        ),
        RootTextBlock(
            block_id=CrdtId(0, 0),
            text_items=[
                TextItem(
                    item_id=CrdtId(1, 16),
                    left_id=CrdtId(0, 0),
                    right_id=CrdtId(0, 0),
                    deleted_length=0,
                    value="AB",
                )
            ],
            text_formats=[
                TextFormatItem(
                    item_id=CrdtId(1, 15),
                    char_id=CrdtId(0, 0),
                    format_type=TextFormat.PLAIN,
                )
            ],
            pos_x=-468.0,
            pos_y=234.0,
            width=936.0,
        ),
        TreeNodeBlock(
            node_id=CrdtId(0, 1),
            label=LwwValue(CrdtId(0, 0), ""),
            visible=LwwValue(CrdtId(0, 0), True),
        ),
        TreeNodeBlock(
            node_id=CrdtId(0, 11),
            label=LwwValue(CrdtId(0, 12), "Layer 1"),
            visible=LwwValue(CrdtId(0, 0), True),
        ),
        SceneGroupItemBlock(
            parent_id=CrdtId(0, 1),
            item_id=CrdtId(0, 13),
            left_id=CrdtId(0, 0),
            right_id=CrdtId(0, 0),
            deleted_length=0,
            value=CrdtId(0, 11),
        ),
    ]


@pytest.mark.parametrize(
    "block",
    [
        AuthorIdsBlock(author_uuids={1: UUID("495ba59f-c943-2b5c-b455-3682f6948906")}),
        AuthorIdsBlock(author_uuids={1: UUID("495ba59f-c943-2b5c-b455-3682f6948906"),
                                     2: UUID("cd83324a-917f-11ed-bb7b-3c0754484e34")}),
        MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True),
        PageInfoBlock(
            loads_count=3, merges_count=2, text_chars_count=3, text_lines_count=1
        ),
        SceneTreeBlock(
            tree_id=CrdtId(0, 11),
            node_id=CrdtId(0, 0),
            is_update=True,
            parent_id=CrdtId(0, 1),
        ),
        RootTextBlock(
            block_id=CrdtId(0, 0),
            text_items=[
                TextItem(
                    item_id=CrdtId(1, 16),
                    left_id=CrdtId(0, 0),
                    right_id=CrdtId(0, 0),
                    deleted_length=0,
                    value="AB",
                )
            ],
            text_formats=[
                TextFormatItem(
                    item_id=CrdtId(1, 15),
                    char_id=CrdtId(0, 0),
                    format_type=TextFormat.PLAIN,
                )
            ],
            pos_x=-468.0,
            pos_y=234.0,
            width=936.0,
        ),
        TreeNodeBlock(
            node_id=CrdtId(0, 11),
            label=LwwValue(CrdtId(0, 12), "Layer 1"),
            visible=LwwValue(CrdtId(0, 0), True),
        ),
        SceneGroupItemBlock(
            parent_id=CrdtId(0, 1),
            item_id=CrdtId(0, 13),
            left_id=CrdtId(0, 0),
            right_id=CrdtId(0, 0),
            deleted_length=0,
            value=CrdtId(0, 11),
        ),
    ],
)
def test_blocks_roundtrip(block):
    buf = BytesIO()
    writer = TaggedBlockWriter(buf)
    reader = TaggedBlockReader(buf)

    # Mock header
    with writer.write_block(4, 1, 1):
        block.to_stream(writer)

    buf.seek(0)
    logger.info("After writing block %s", type(block))
    logger.info("Buffer: %s", buf.getvalue().hex())
    with reader.read_block():
        block2 = block.from_stream(reader)
    assert block2 == block


def test_write_blocks():
    blocks = [
        MigrationInfoBlock(migration_id=CrdtId(1, 1), is_device=True),
    ]

    buf = BytesIO()
    write_blocks(buf, blocks)

    assert buf.getvalue()[:43] == b"reMarkable .lines file, version=6          "
    assert buf.getvalue()[43:].hex() == "05000000000101001f01012101"


def test_blocks_keep_unknown_data():
    # The "7f 010f" is new, unknown data
    data_hex = """
    56000000 00020205
    1f 0219
    2f 021e
    3f 0000
    4f 0000
    54 0000 0000
    6c 4000 0000
       03
       14 0f000000
       24 00000000
       38 00000000 0000f03f
       44 00000000
       5c 1c000000
          f8fe82c2 f42a30c3 03000800 0000b869
          83c2622d 30c30000 08000000
       6f 0001
       7f 010f
    """
    buf = BytesIO(HEADER_V6 + bytes.fromhex(data_hex))
    reader = TaggedBlockReader(buf)
    block = next(read_blocks(buf))
    assert isinstance(block, SceneLineItemBlock)
    assert block.extra_data == bytes.fromhex("7f 010f")


from hypothesis import given, strategies as st


crdt_id_strategy = st.builds(
    CrdtId,
    st.integers(min_value=0, max_value=2**8-1),
    st.integers(min_value=0, max_value=2**64-1),
)
st.register_type_strategy(CrdtId, crdt_id_strategy)

author_ids_block_strategy = st.builds(
    AuthorIdsBlock,
    st.dictionaries(st.integers(min_value=0, max_value=65535), st.uuids())
)

block_strategy = st.one_of([
    author_ids_block_strategy,
    st.builds(MigrationInfoBlock),
])



@given(block_strategy)
def test_blocks_roundtrip_2(block):
    buf = BytesIO()
    writer = TaggedBlockWriter(buf)
    reader = TaggedBlockReader(buf)

    # Mock header
    with writer.write_block(4, 1, 1):
        block.to_stream(writer)

    buf.seek(0)
    logger.info("After writing block %s", type(block))
    logger.info("Buffer: %s", buf.getvalue().hex())
    with reader.read_block():
        block2 = block.from_stream(reader)
    assert block2 == block


@given(...)
def test_write_id(crdt_id: CrdtId):
    buf = BytesIO()
    s = TaggedBlockWriter(buf)
    s.write_id(3, crdt_id)
