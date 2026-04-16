"""VROOM backend via ``pyvroom``."""

from __future__ import annotations

from vrp_model.solvers.registry import register
from vrp_model.solvers.vroom.solver import VroomSolver

register("vroom", VroomSolver)

__all__ = ["VroomSolver"]
