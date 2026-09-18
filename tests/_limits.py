"""Solver time limits used across the test suite.

PyVRP and Nextroute run their full budget on every call, so their limits set the suite's
runtime almost by themselves; OR-Tools and VROOM return as soon as their search finishes,
so their limits are safety caps that cost nothing. The toy instances here are small enough
that PyVRP and Nextroute reach the documented optimum in well under 0.05s, so the defaults
below keep a wide margin while staying fast.

Set ``VRP_MODEL_TEST_TIME_LIMIT_SCALE`` to re-run the suite with longer budgets, e.g.
``VRP_MODEL_TEST_TIME_LIMIT_SCALE=20`` when investigating a flaky cost assertion.
"""

from __future__ import annotations

import os

_SCALE = float(os.environ.get("VRP_MODEL_TEST_TIME_LIMIT_SCALE", "1"))


def scaled(seconds: float) -> float:
    """Apply ``VRP_MODEL_TEST_TIME_LIMIT_SCALE`` to a base limit."""
    return seconds * _SCALE


# Budget-burning solvers: these dominate suite runtime.
PYVRP_TIME_LIMIT = scaled(0.25)
NEXTROUTE_TIME_LIMIT = scaled(0.25)

# Early-returning solvers: caps, not costs.
ORTOOLS_TIME_LIMIT = scaled(15.0)
VROOM_TIME_LIMIT = scaled(10.0)


def pyvrp_options(**extra: object) -> dict:
    """Default PyVRP test options: short budget, no progress output."""
    return {"time_limit": PYVRP_TIME_LIMIT, "msg": False, **extra}
