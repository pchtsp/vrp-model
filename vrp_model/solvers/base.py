"""Abstract solver interface and orchestrated solve flow."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vrp_model.core.model import Feature, Model
from vrp_model.solvers.status import SolutionStatus


class Solver(ABC):
    """Pluggable VRP solver; :meth:`solve` validates then calls :meth:`_run`."""

    name: str
    supported_features: frozenset[Feature]

    @abstractmethod
    def _run(self, model: Model) -> SolutionStatus:
        """Attach ``model._solution`` and return run statistics (including :class:`SolveStatus`)."""
        ...

    def solve(self, model: Model) -> SolutionStatus:
        """Validate ``model``, check solver compatibility, run :meth:`_run`."""
        model.validate()
        model.check_solver_compatibility(self)
        return self._run(model)
