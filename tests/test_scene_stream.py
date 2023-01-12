import pytest
from io import BytesIO
from pathlib import Path
from uuid import UUID
from rmscene import parse_blocks, LwwValue, TaggedBlockWriter, TaggedBlockReader
from rmscene.scene_stream import *

import logging
logger = logging.getLogger(__name__)


DATA_PATH = Path(__file__).parent / "data"


def test_normal_ab():
    with open(DATA_PATH / "Normal_AB.rm", "rb") as f:
        result = list(parse_blocks(f))

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
                    text="AB",
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
                    text="AB",
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
