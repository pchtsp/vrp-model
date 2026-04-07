"""Node classification for unified ``Model._nodes`` storage."""

from __future__ import annotations

from enum import Enum, auto


class NodeKind(Enum):
    """Discriminator for rows in :attr:`~vrp_model.core.model.Model._nodes`."""

    DEPOT = auto()
    JOB = auto()
