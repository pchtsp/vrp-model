"""Solver registry tests."""

import unittest

from vrp_model.solvers.base import Solver
from vrp_model.solvers.registry import get, register


class _Dummy(Solver):
    name = "dummy"
    supported_features = frozenset()

    def _run(self, model, options):  # noqa: ARG002
        raise NotImplementedError


class TestRegistry(unittest.TestCase):
    def test_register_and_get(self) -> None:
        register("vrp_model_test_dummy_solver", _Dummy)
        self.assertIs(get("vrp_model_test_dummy_solver"), _Dummy)

    def test_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            get("no_such_solver_ever")


if __name__ == "__main__":
    unittest.main()
