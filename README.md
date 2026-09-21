# vrp-model

Solver-agnostic vehicle routing: a canonical [`Model`](vrp_model/core/model.py), layered **validation**, automatic **feature detection**, and pluggable backends. Entities reference each other via view objects (`Depot`, `Vehicle`, `Job`) on the same model. Optional **`label`** is for display/export only.

**Python:** 3.11+ (CI tests 3.12 and 3.13) · **Core dependency:** [`vrplib`](https://pypi.org/project/vrplib/) (instance I/O).

## Installation

### As a dependency

The distribution name on PyPI is **`vrp-model`**; import the package as **`vrp_model`**.

**pip**

```bash
pip install vrp-model
pip install "vrp-model[pyvrp]"  # one optional extra
pip install "vrp-model[pyvrp,ortools,vroom,nextroute]"  # multiple extras
```

**uv**

```bash
uv add vrp-model
uv add "vrp-model[pyvrp]"
uv add "vrp-model[pyvrp,ortools,vroom,nextroute]"
```

Optional dependency groups use the same names as in [Available solvers](#available-solvers): `pyvrp`, `ortools`, `vroom`, `nextroute`.

### From this repository

```bash
uv sync                                    # core only (no solver backends)
uv sync --extra pyvrp                      # PyVRP
uv sync --extra ortools                    # Google OR-Tools
uv sync --extra vroom                      # VROOM (pyvroom + NumPy + pandas)
uv sync --extra nextroute                  # Nextmv Nextroute
uv sync --extra pyvrp --extra ortools --extra vroom --extra nextroute --group dev
```

Each extra installs the matching third-party package; solver classes raise [`SolverNotInstalledError`](vrp_model/core/errors.py) if the extra was not installed.

## Available solvers

Solvers register under short names (import the submodule once so registration runs, or construct the class directly):

| Registry name | Class | Extra | Notes |
|---------------|-------|-------|--------|
| `pyvrp` | [`PyVRPSolver`](vrp_model/solvers/pyvrp/solver.py) | `pyvrp` | In-process PyVRP; strong default for “classic” VRP with sparse matrices or Euclidean legs. |
| `ortools` | [`ORToolsSolver`](vrp_model/solvers/ortools/solver.py) | `ortools` | Google OR-Tools routing; broadest feature coverage in this repo. |
| `vroom` | [`VroomSolver`](vrp_model/solvers/vroom/solver.py) | `vroom` | [pyvroom](https://pypi.org/project/pyvroom/); matrix-based. On some platforms, matrix setup can fail unless NumPy and pyvroom versions match (see solver docstring). |
| `nextroute` | [`NextrouteSolver`](vrp_model/solvers/nextroute/solver.py) | `nextroute` | [Nextmv Nextroute](https://pypi.org/project/nextroute/); time windows use an anchor datetime in solver options. |

```python
from vrp_model.solvers.pyvrp import PyVRPSolver  # registers "pyvrp"
from vrp_model.solvers import get

solver_cls = get("pyvrp")
result = solver_cls({"time_limit": 2.0, "msg": False}).solve(model)
```

### Solver options

Every solver takes one options `dict`. Keys you omit get package defaults. Each backend reads the standard keys it supports and ignores the rest.

| Key | Default | Meaning |
|-----|---------|---------|
| `time_limit` | `3.0` | Wall-clock budget for the search, in seconds |
| `seed` | `0` | Random seed |
| `max_iterations` | `None` | Iteration cap (`None` leaves it to the solver) |
| `gap_rel` / `gap_abs` | `None` | Relative / absolute optimality gap to stop at |
| `msg` | `False` | Print solver progress |
| `log_path` | `None` | File that receives progress logs (PyVRP) |
| `missing_arc_distance` / `missing_arc_duration` | `None` | Cost used for arcs the model marks unreachable (`None` keeps each backend's own sentinel) |
| `omit_unreachable_arcs` | `False` | PyVRP only: fill an arc's whole edge when either of its components is unreachable (see [PyVRP forbidden arcs](#model-assumptions-and-travel)) |

Backend-specific keys:

- **ortools:** `first_solution_strategy`, `local_search_metaheuristic` (OR-Tools enum values; `None` keeps the OR-Tools default)
- **pyvrp:** `skill_incompatible_cost` (cost of arcs into jobs whose skills the vehicle lacks)
- **vroom:** `exploration_level` (default `5`), `nb_threads` (default `4`)
- **nextroute:** `time_anchor` (datetime that model time `0` maps to; default `2020-01-01T00:00Z`), `speed_mps` (fallback speed in m/s when travel is not matrix-only; default `30.0`)

### What is modeled (VRP in this package)

Vehicle routing here means assigning jobs to vehicles (routes), respecting travel between unified **node ids** (depots and jobs), optional **capacity** dimensions, **time** logic (service durations, windows, and caps), **pickup–delivery** pairs, **job groups** (mutually exclusive alternatives via [`add_job_group`](vrp_model/core/model.py)), **job compatibility** (a `job_type` per job plus incompatible type pairs via [`add_job_type_incompatibility`](vrp_model/core/model.py); incompatible types never share a route), **vehicle groups** (vehicles sharing one unit of availability via [`add_vehicle_group`](vrp_model/core/model.py); at most `max_active` members run a route), depot topology, and fleet diversity. The canonical [`Model`](vrp_model/core/model.py) holds jobs, vehicles, optional pickup–delivery links, and sparse **travel** overrides; [`Feature`](vrp_model/core/model.py) summarizes which constraint families appear so solvers can declare compatibility.

**Detection vs. adapters.** [`Model.detect_features()`](vrp_model/core/model.py) sets [`Feature`](vrp_model/core/model.py) from stored fields (e.g. any positive demand or non-empty vehicle capacity → `CAPACITY`; job or vehicle time windows → `TIME_WINDOWS`; soft penalties in [`TimeWindowFlex`](vrp_model/core/time_window_flex.py) → `FLEXIBLE_TIME_WINDOWS`). Other behavior, such as **service times** and Euclidean vs matrix travel, is not a `Feature` flag but is still passed through each solver adapter where the backend supports it.

### Solver capability matrix

Before solving, [`Solver.solve`](vrp_model/solvers/base.py) runs [`Model.validate()`](vrp_model/core/model.py) and [`Model.check_solver_compatibility(solver)`](vrp_model/core/model.py), which raises [`SolverCapabilityError`](vrp_model/core/errors.py) if a declared [`Feature`](vrp_model/core/model.py) is missing from the solver’s `supported_features`. One row per modeled capability:

| Capability | `Feature` | pyvrp | ortools | nextroute | vroom |
|------------|-----------|:-----:|:-------:|:---------:|:-----:|
| Capacity (one or more resource dimensions; demands on jobs, caps on vehicles) | `CAPACITY` | ✓ | ✓ | ✓ | ✓ |
| Hard time windows at jobs | `TIME_WINDOWS` | ✓ | ✓ | ✓ | ✓ |
| Hard time windows at vehicles (shift / availability) | `TIME_WINDOWS` | ✓ | ✓ | ✓ | ✓ |
| Pickup–delivery pairs (precedence and same vehicle) | `PICKUP_DELIVERY` | ✓ | ✓ | ✓ | ✓ |
| Multi-depot (vehicles may start/end at different depots) | `MULTI_DEPOT` | ✓ | ✓ | ✓ | ✓ |
| Heterogeneous fleet (distinct vehicle definitions) | `HETEROGENEOUS_FLEET` | ✓ | ✓ | ✓ | ✓ |
| Service time at jobs (added into time accounting) | — | ✓ | ✓ | ✓ | ✓ |
| Vehicle fixed use cost (activation / fixed cost per route) | `VEHICLE_FIXED_COST` | ✓ | ✓ | ✓ | ✓ |
| Maximum route distance per vehicle | `MAX_ROUTE_DISTANCE` | ✓ | ✓ | ✓ | ✓ |
| Maximum route duration / shift length per vehicle | `MAX_ROUTE_TIME` | ✓ | ✓ | ✓ | ✓ |
| Skills (jobs require a subset of vehicle skills) | `SKILLS` | ✓ | ✓ | ✓ | ✓ |
| Optional jobs / prize-collecting (mandatory vs skip penalty via `prize`) | `PRIZE_COLLECTING` | ✓ | ✓ | ✗ | ✗ |
| Job groups (mutually exclusive job alternatives) | `JOB_GROUPS` | ✓ | ✓ | ✗ | ✗ |
| Route overtime (extra duration allowed + unit penalty on overage) | `ROUTE_OVERTIME` | ✓ | ✓ | ✗ | ✗ |
| Job compatibility (jobs of incompatible `job_type`s never share a route) | `JOB_COMPATIBILITY` | ✗ | ✓ | ✗ | ✗ |
| Vehicle groups (at most `max_active` vehicles of a group run a route) | `VEHICLE_GROUPS` | ✗ | ✓ | ✗ | ✗ |
| Flexible time windows (linear soft penalties via `TimeWindowFlex`) | `FLEXIBLE_TIME_WINDOWS` | ✗ | ✓ | ✗ | ✗ |
| Maximum wait / time slack at nodes (`max_slack_time` on vehicles) | `MAX_NODE_SLACK` | ✗ | ✓ | ✗ | ✗ |

### Objective function

**Canonical objective.** [`Model.solution_cost()`](vrp_model/core/model.py) scores any attached solution the same way, whichever solver produced it. It is the sum of:

- total **travel distance**
- **`fixed_use_cost`** of every vehicle whose route serves at least one job
- the **`prize`** of every optional job left unvisited (jobs inside a job group don't count here)
- the **`skip_penalty`** of every optional job group with no member visited
- linear **soft time-window penalties** from `TimeWindowFlex` on jobs and vehicles
- **overtime charge**: time beyond `max_route_time` × `route_overtime_unit_cost`

`max_slack_time` adds no cost.

**What each backend minimizes.** Each backend optimizes its own objective, so `SolutionStatus.solver_reported_cost` can differ from `model.solution_cost()`. This matters most for VROOM and Nextroute, which minimize duration instead of distance.

| Solver | Minimizes |
|--------|-----------|
| [`ORToolsSolver`](vrp_model/solvers/ortools/solver.py) | Travel **distance** (arc cost; time is a separate dimension) + vehicle fixed cost + disjunction penalties (prizes, group skip penalties) + soft time-window penalties + overtime |
| [`PyVRPSolver`](vrp_model/solvers/pyvrp/solver.py) | Travel **distance** + vehicle `fixed_cost` + prizes of skipped jobs + `unit_overtime_cost`; duration only drives time feasibility |
| [`VroomSolver`](vrp_model/solvers/vroom/solver.py) | Travel **duration** (VROOM's default per-hour cost) + vehicle fixed cost |
| [`NextrouteSolver`](vrp_model/solvers/nextroute/solver.py) | Travel **duration** (Nextroute's default objective) + vehicle `activation_penalty` (fixed cost) |

## Model assumptions and travel

**Unified nodes:** The model stores one append-only list of nodes. Each row has a [`NodeKind`](vrp_model/core/kinds.py) (`DEPOT` or `JOB`). **`node_id`** is the row index—shared across depots and jobs in creation order. Use **`Depot.node_id`** and **`Job.node_id`** as keys in `(from_id, to_id)` travel maps.

**Locations:** Depot and job **`location`** are optional for *construction*, but feasibility validation requires every job to have coordinates **unless** you supply a non-empty sparse travel map (see below). Solvers may still synthesize coordinates internally when a location is missing (e.g. PyVRP).

**Sparse travel:** Travel is stored as `(from_id, to_id) → `[`TravelEdgeAttrs`](vrp_model/core/travel_edges.py) with optional **`distance`** and **`duration`** (`int` or `None`). At least one of distance or duration must be set on each stored edge. Model-level routing helpers treat a missing field on a stored edge as infinite cost; [`TRAVEL_COST_INF`](vrp_model/core/travel_edges.py) is the large sentinel (aligned with PyVRP’s `MAX_VALUE` scale).

- If **`travel_edges`** is **empty**, leg distance and duration fall back to **integer Euclidean** distances between planar coordinates for **all** pairs (depots and jobs). Validation then requires **every job** to have a **`location`**.
- If **`travel_edges`** is **non-empty**, the model uses **matrix-only** semantics: any directed pair not present in the map has infinite distance and duration (no Euclidean fallback for missing arcs).

Use **`set_travel_edges`**, **`update_travel_edge`**, and **`clear_travel_edges`** on the model; read the current map via **`model.travel_edges`** (a shallow snapshot). **`validate()`** checks node ids, forbids self-loops, and rejects negative costs. When **time windows** are active (`Feature.TIME_WINDOWS`), any stored edge with **`distance`** must also set **`duration`**. Pickup–delivery pairs are registered with **`add_pickup_delivery`** and read via **`model.pickup_deliveries`**.

**PyVRP pickup–delivery:** Pairs registered with **`add_pickup_delivery`** map to PyVRP **shipments** (`add_shipment`), so PyVRP itself enforces precedence and same-vehicle service; the shipment carries the pickup job’s demand (falling back to the delivery job’s when the pickup demand is all zeros), and is skippable only when **both** jobs have a `prize`.

**PyVRP forbidden arcs:** Each PyVRP matrix fills forbidden arcs on its own. The distance matrix uses **`missing_arc_distance`** and the duration matrix uses **`missing_arc_duration`**. When an override is unset, arcs the model can't reach fall back to the package sentinel, and arcs into jobs a vehicle lacks the skills for fall back to **`skill_incompatible_cost`**. All values are capped at PyVRP’s maximum. By default, an edge with only one finite component keeps that component. Pass **`omit_unreachable_arcs: true`** to fill the whole edge instead. Matrix solvers (OR-Tools, VROOM, Nextroute) ignore **`omit_unreachable_arcs`**.


## Solving and solutions

[`Solver.solve`](vrp_model/solvers/base.py) validates the model, checks capabilities, runs the backend, and attaches a [`Solution`](vrp_model/core/solution.py) to **`model.solution`**. The return value is [`SolutionStatus`](vrp_model/solvers/status.py) (mapped status, timing, stop reason, solver cost, etc.).

Metrics on the attached solution:

- **`model.solution_cost()`**: the canonical objective (see [Objective function](#objective-function))
- **`model.solution_travel_distance()`**: total leg distance only
- **`model.unassigned_jobs()`** / **`model.mandatory_unassigned_jobs()`**: jobs left unvisited, all of them or only the mandatory ones
- **`model.is_solution_feasible()`**: checks, independently of the solver, that routes start and end at their vehicles' depots, no job is visited twice, every mandatory job is visited, and capacity, skills, hard time windows, route limits, pickup–delivery pairs, job groups, vehicle groups and job compatibility all hold

These raise **`SolutionUnavailableError`** if no solution is attached.

## VRPLIB (`vrplib`)

[`read_model`](vrp_model/io/vrplib_io.py) and [`vrplib_dict_to_model`](vrp_model/io/vrplib_io.py) build a `Model` **without** calling **`validate()`**. Call **`model.validate()`** before relying on consistency, or use **`Solver.solve`**, which validates first. [`write_vrplib_instance`](vrp_model/io/vrplib_io.py) / [`write_vrplib_solution`](vrp_model/io/vrplib_io.py) export instances and routes.

## Example

```python
from vrp_model import Model
from vrp_model.solvers.pyvrp import PyVRPSolver

model = Model()
depot = model.add_depot(location=(0.0, 0.0), label="hub")
vehicle = model.add_vehicle(10, depot, label="truck1")
job = model.add_job(3, location=(1.0, 2.0))

result = PyVRPSolver({"time_limit": 2.0, "msg": False}).solve(model)
solution = model.solution
assert result.mapped_status.name == "FEASIBLE"
```

With OR-Tools installed: `from vrp_model.solvers.ortools import ORToolsSolver` and `ORToolsSolver({"time_limit": 5.0}).solve(model)`.

## Development

```bash
uv sync --all-extras --group dev     # same set as CI
uv run python -m unittest discover -s tests
uv run ruff check vrp_model tests && uv run ruff format vrp_model tests --check
uv run ty check vrp_model
```

[CI](.github/workflows/ci.yml) runs these checks with every solver extra installed, on Ubuntu, Windows and macOS with Python 3.12 and 3.13. Locally, tests for backends that aren't installed are skipped, so install all extras for full coverage.
