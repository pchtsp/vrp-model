"""Optional name → solver class registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vrp_model.solvers.base import Solver

_registry: dict[str, type[Solver]] = {}


def register(name: str, solver_cls: type[Solver]) -> None:
    _registry[name] = solver_cls


def get(name: str) -> type[Solver]:
    if name not in _registry:
        msg = f"unknown solver {name!r}"
        raise KeyError(msg)
    return _registry[name]
