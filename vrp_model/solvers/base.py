"""Abstract solver interface and orchestrated solve flow."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vrp_model.core.model import Feature, Model, SolveStatus
from vrp_model.core.solution import Solution
from vrp_model.solvers.options import merge_solver_options


class Solver(ABC):
    name: str
    supported_features: frozenset[Feature]

    def _default_solve_options(self) -> dict:
        return {}

    @abstractmethod
    def _run(self, model: Model, options: dict) -> tuple[object, Solution]: ...

    def solve(self, model: Model, options: dict | None = None) -> SolveStatus:
        model.validate()
        model.check_solver_compatibility(self)
        opts = merge_solver_options(
            self._default_solve_options(),
            options,
        )
        raw_status, solution = self._run(model, opts)
        model._solution = solution
        return model.map_status(raw_status)
