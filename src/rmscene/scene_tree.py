"""Build scene tree structure from block data.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
import math
from uuid import UUID
from dataclasses import dataclass, field
import enum
import logging
import typing as tp

from .tagged_block_common import CrdtId, LwwValue
from .tagged_block_reader import TaggedBlockReader
from .tagged_block_writer import TaggedBlockWriter
from .crdt_sequence import CrdtSequence, CrdtSequenceItem
from . import scene_items as si

_logger = logging.getLogger(__name__)


ROOT_ID = CrdtId(0, 1)


class SceneTree:
    def __init__(self):
        self.root = si.Group(ROOT_ID)
        self._node_ids = {self.root.node_id: self.root}
        # self.root = SceneTreeNode(CrdtId(0, 1), CrdtSequence([]))
        # self._nodes = {self.root.node_id: self.root}

    def __contains__(self, node_id: CrdtId):
        return node_id in self._node_ids

    def __getitem__(self, node_id: CrdtId):
        return self._node_ids[node_id]

    def add_node(self, node_id: CrdtId, parent_id: CrdtId):
        if node_id in self._node_ids:
            raise ValueError("Node %s already in tree" % node_id)
        node = si.Group(node_id)
        self._node_ids[node_id] = node
        # parent = self._node_ids[parent_id]
        # parent.children.add(item)

    def add_item(self, item: CrdtSequenceItem[si.SceneItem], parent_id: CrdtId):
        if parent_id not in self._node_ids:
            raise ValueError("Parent id not known: %s" % parent_id)
        parent = self._node_ids[parent_id]
        parent.children.add(item)
