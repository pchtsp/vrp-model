"""Lazy nextroute imports (no :mod:`vrp_model.core` import cycle)."""

from __future__ import annotations

from typing import Any

NextrouteInput: Any = None
NextrouteOptions: Any = None
nextroute_solve: Any = None

try:
    from nextroute import Options as _NextrouteOptions
    from nextroute import solve as _nsolve
    from nextroute.schema.input import Input as _NInp

    NextrouteInput = _NInp
    NextrouteOptions = _NextrouteOptions
    nextroute_solve = _nsolve
except ModuleNotFoundError:  # pragma: no cover - exercised when extra not installed
    NextrouteInput = None
    NextrouteOptions = None
    nextroute_solve = None
