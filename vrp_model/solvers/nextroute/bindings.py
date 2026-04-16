"""Lazy nextroute imports."""

from __future__ import annotations

from typing import Any

NextrouteInput: Any = None
nextroute_solve: Any = None

try:
    from nextroute import solve as _nsolve
    from nextroute.schema.input import Input as _NInp

    NextrouteInput = _NInp
    nextroute_solve = _nsolve
except ModuleNotFoundError:  # pragma: no cover
    pass
