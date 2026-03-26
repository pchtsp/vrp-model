"""Node classification for unified ``Model._nodes`` storage."""

from __future__ import annotations

from enum import Enum, auto


class NodeKind(Enum):
    DEPOT = auto()
    JOB = auto()
