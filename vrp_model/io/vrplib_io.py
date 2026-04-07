"""VRPLIB / Solomon interchange: re-exports from split IO modules.

Read dict keys match ``vrplib.read_instance`` (snake_case). Write dict keys match
``vrplib.write_instance`` (UPPER specs and ``*_SECTION`` headers). See
``vrplib_keys.write_spec_key`` / ``write_section_key`` and module
``vrplib.parse.parse_vrplib`` for the exact mapping.
"""

from __future__ import annotations

from vrp_model.io.vrplib_read import read_model, vrplib_dict_to_model
from vrp_model.io.vrplib_types import VRPLibReadDict, VRPLibWriteDict
from vrp_model.io.vrplib_write import (
    model_to_vrplib_dict,
    solution_to_vrplib_routes,
    write_vrplib_instance,
    write_vrplib_solution,
)

__all__ = [
    "VRPLibReadDict",
    "VRPLibWriteDict",
    "model_to_vrplib_dict",
    "read_model",
    "solution_to_vrplib_routes",
    "vrplib_dict_to_model",
    "write_vrplib_instance",
    "write_vrplib_solution",
]
