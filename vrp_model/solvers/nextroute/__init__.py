"""Nextmv Nextroute backend via ``nextroute``."""

from __future__ import annotations

from vrp_model.solvers.nextroute.solver import NextrouteSolver
from vrp_model.solvers.registry import register

register("nextroute", NextrouteSolver)

__all__ = ["NextrouteSolver"]
