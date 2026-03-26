"""OR-Tools integration placeholder."""

from __future__ import annotations

from vrp_model.core.model import Feature, Model
from vrp_model.core.solution import Solution
from vrp_model.solvers.base import Solver


class ORToolsSolver(Solver):
    name = "ortools"
    supported_features = frozenset({Feature.CAPACITY})

    def _run(self, model: Model, options: dict) -> tuple[object, Solution]:
        del model, options
        raise NotImplementedError("OR-Tools adapter is planned for Phase 2")
