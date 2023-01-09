from pathlib import Path
from uuid import UUID
from rmscene import parse_blocks, LwwValue
from rmscene.scene_stream import *


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
        SceneItemBlock(
            parent_id=CrdtId(0, 1),
            item_id=CrdtId(0, 13),
            left_id=CrdtId(0, 0),
            right_id=CrdtId(0, 0),
            deleted_length=0,
            item_type="group",
            value=CrdtId(0, 11),
        ),
    ]
