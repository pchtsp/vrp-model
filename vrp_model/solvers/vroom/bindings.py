"""Lazy pyvroom imports (no vrp_model.core imports)."""

from __future__ import annotations

from typing import Any

VroomInput: Any = None

try:
    from vroom.input.input import Input as _VroomInput

    VroomInput = _VroomInput
except ModuleNotFoundError:  # pragma: no cover - exercised when extra not installed
    pass

VROOM_PROFILE = "car"
VROOM_UINT32_MAX = 4_294_967_295
