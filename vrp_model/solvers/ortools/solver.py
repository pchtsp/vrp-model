"""OR-Tools integration placeholder."""

from __future__ import annotations

from vrp_model.core.model import Feature, Model
from vrp_model.solvers.base import Solver
from vrp_model.solvers.status import SolutionStatus


class ORToolsSolver(Solver):
    name = "ortools"
    supported_features = frozenset({Feature.CAPACITY})

    def _run(self, model: Model, options: dict) -> SolutionStatus:
        del model, options
        raise NotImplementedError("OR-Tools adapter is planned for Phase 2")
