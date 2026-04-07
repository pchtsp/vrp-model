"""Abstract solver interface and orchestrated solve flow."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vrp_model.core.model import Feature, Model
from vrp_model.solvers.options import merge_solver_options
from vrp_model.solvers.status import SolutionStatus


class Solver(ABC):
    """Pluggable VRP solver; :meth:`solve` validates then calls :meth:`_run`."""

    name: str
    supported_features: frozenset[Feature]

    def _default_solve_options(self) -> dict:
        return {}

    @abstractmethod
    def _run(self, model: Model, options: dict) -> SolutionStatus:
        """Attach ``model._solution`` and return run statistics (including mapped status)."""
        ...

    def solve(self, model: Model, options: dict | None = None) -> SolutionStatus:
        """Validate ``model``, check compatibility, merge options, run :meth:`_run`."""
        model.validate()
        model.check_solver_compatibility(self)
        opts = merge_solver_options(
            self._default_solve_options(),
            options,
        )
        return self._run(model, opts)
