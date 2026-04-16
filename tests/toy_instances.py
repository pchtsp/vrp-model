"""Small hand-defined VRP instances for cross-solver regression tests.

Optional vs mandatory jobs: ``prize is None`` ⇒ mandatory; ``prize`` set ⇒ optional
(skip penalty in :meth:`vrp_model.core.model.Model.solution_cost`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import permutations
from typing import Literal

from vrp_model import Feature, Model, TravelEdgeAttrs, TravelEdgesMap
from vrp_model.core.travel_edges import TRAVEL_COST_INF


@dataclass(frozen=True, slots=True)
class ToyCase:
    """Metadata for a toy model used in tests."""

    name: str
    required_features: frozenset[Feature]
    build: Callable[[], Model]
    documented_optimal_travel: int | None
    documented_optimal_objective: float | None
    cost_assertion: Literal["exact", "bounded", "none"]
    cost_tolerance: float = 0.0
    skip_for_solvers: frozenset[str] = frozenset()


def build_tiny_line_two_jobs() -> Model:
    """Depot at origin, two unit-spaced jobs; symmetric line (optimal travel 4)."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d)
    m.add_job(3, location=(1.0, 0.0), label="j0")
    m.add_job(4, location=(2.0, 0.0), label="j1")
    m.validate()
    return m


def build_asymmetric_matrix_two_jobs() -> Model:
    """Two jobs; explicit asymmetric matrix (dummy coords). Best order j_first then j_second."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_job(3, location=(0.0, 0.0), label="j_first")
    m.add_job(4, location=(0.0, 0.0), label="j_second")
    m.add_vehicle([10], d)
    edges: TravelEdgesMap = {}
    n = 3
    dist = [
        [0, 1, 100],
        [100, 0, 50],
        [1, 1, 0],
    ]
    dur = [
        [0, 1, 100],
        [100, 0, 50],
        [1, 1, 0],
    ]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            edges[(i, j)] = TravelEdgeAttrs(distance=dist[i][j], duration=dur[i][j])
    m.set_travel_edges(edges)
    m.validate()
    return m


def build_forced_split_two_vehicles() -> Model:
    """Two vehicles capacity 1; two unit-demand jobs far apart (optimal travel 40)."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([1], d, label="v0")
    m.add_vehicle([1], d, label="v1")
    m.add_job(1, location=(10.0, 0.0), label="east")
    m.add_job(1, location=(-10.0, 0.0), label="west")
    m.validate()
    return m


def build_prize_collecting() -> Model:
    """One mandatory stop; optional far with huge skip penalty so skipping beats visiting."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d)
    m.add_job(1, location=(1.0, 0.0), label="mandatory", prize=None)
    m.add_job(0, location=(20.0, 0.0), label="optional_far", prize=10_000.0)
    m.validate()
    # Mandatory-only round trip distance 2; skip penalty 10000 ⇒ objective 10002.
    # Visiting optional is ~40 travel, still worse than skipping under canonical cost.
    return m


def build_vehicle_fixed_cost_choice() -> Model:
    """Cheap vehicle has huge fixed cost; zero-fixed vehicle should serve the job."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d, label="cheap_fixed", fixed_use_cost=0)
    m.add_vehicle([10], d, label="expensive_fixed", fixed_use_cost=1_000_000)
    m.add_job(1, location=(1.0, 0.0), label="only_job")
    m.validate()
    return m


def build_skills_routing() -> Model:
    """Job needs skill 1; only vehicle A has it."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([10], d, label="has_skill_1", skills={1})
    m.add_vehicle([10], d, label="has_skill_2", skills={2})
    m.add_job(1, location=(2.0, 0.0), label="needs_1", skills_required={1})
    m.validate()
    return m


def build_multi_depot_end() -> Model:
    """Vehicle returns to a different depot than start."""
    m = Model()
    d0 = m.add_depot(location=(0.0, 0.0), label="d0")
    m.add_job(1, location=(1.0, 0.0), label="mid")
    d1 = m.add_depot(location=(3.0, 0.0), label="d1")
    m.add_vehicle([10], d0, end_depot=d1)
    m.add_job(1, location=(2.0, 0.0), label="last")
    m.validate()
    return m


def build_heterogeneous_capacities() -> Model:
    """Large demand fits only the high-capacity vehicle."""
    m = Model()
    d = m.add_depot(location=(0.0, 0.0))
    m.add_vehicle([1], d, label="small")
    m.add_vehicle([10], d, label="big")
    m.add_job(5, location=(1.0, 0.0), label="heavy")
    m.add_job(1, location=(2.0, 0.0), label="light")
    m.validate()
    return m


TOY_CASES: list[ToyCase] = [
    ToyCase(
        name="tiny_line_two_jobs",
        required_features=frozenset(),
        build=build_tiny_line_two_jobs,
        documented_optimal_travel=4,
        documented_optimal_objective=4.0,
        cost_assertion="exact",
    ),
    ToyCase(
        name="asymmetric_matrix_two_jobs",
        required_features=frozenset(),
        build=build_asymmetric_matrix_two_jobs,
        documented_optimal_travel=52,
        documented_optimal_objective=52.0,
        cost_assertion="exact",
        skip_for_solvers=frozenset({"nextroute"}),
    ),
    ToyCase(
        name="forced_split_two_vehicles",
        required_features=frozenset({Feature.CAPACITY}),
        build=build_forced_split_two_vehicles,
        documented_optimal_travel=40,
        documented_optimal_objective=40.0,
        cost_assertion="bounded",
        cost_tolerance=2.0,
    ),
    ToyCase(
        name="prize_collecting",
        required_features=frozenset({Feature.PRIZE_COLLECTING}),
        build=build_prize_collecting,
        documented_optimal_travel=None,
        documented_optimal_objective=10002.0,
        cost_assertion="none",
    ),
    ToyCase(
        name="vehicle_fixed_cost",
        required_features=frozenset({Feature.VEHICLE_FIXED_COST}),
        build=build_vehicle_fixed_cost_choice,
        documented_optimal_travel=2,
        documented_optimal_objective=2.0,
        cost_assertion="exact",
    ),
    ToyCase(
        name="skills",
        required_features=frozenset({Feature.SKILLS}),
        build=build_skills_routing,
        documented_optimal_travel=None,
        documented_optimal_objective=None,
        cost_assertion="none",
    ),
    ToyCase(
        name="multi_depot",
        required_features=frozenset({Feature.MULTI_DEPOT}),
        build=build_multi_depot_end,
        documented_optimal_travel=None,
        documented_optimal_objective=None,
        cost_assertion="none",
    ),
    ToyCase(
        name="heterogeneous_fleet",
        required_features=frozenset({Feature.HETEROGENEOUS_FLEET, Feature.CAPACITY}),
        build=build_heterogeneous_capacities,
        documented_optimal_travel=None,
        documented_optimal_objective=None,
        cost_assertion="none",
    ),
]


def brute_force_optimal_travel_single_vehicle(model: Model) -> int | None:
    """Enumerate permutations for a single-vehicle model with full matrix; travel distance only."""
    if len(list(model.vehicles)) != 1:
        return None
    job_ids = [j.node_id for j in model.jobs]
    if not job_ids or len(job_ids) > 7:
        return None
    d = next(iter(model.depots))
    start = d.node_id
    end = start
    v = next(iter(model.vehicles))
    if v.start_depot.node_id != start or v.end_depot.node_id != end:
        return None

    best: int | None = None
    for perm in permutations(job_ids):
        dist = 0
        prev = start
        for nid in perm:
            leg = model._directed_travel_distance(prev, nid)
            if leg >= TRAVEL_COST_INF:
                dist = TRAVEL_COST_INF
                break
            dist += leg
            prev = nid
        if dist >= TRAVEL_COST_INF:
            continue
        leg = model._directed_travel_distance(prev, end)
        if leg >= TRAVEL_COST_INF:
            continue
        dist += leg
        best = dist if best is None else min(best, dist)
    return best
