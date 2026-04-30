# vrp-model

Solver-agnostic vehicle routing: a canonical [`Model`](vrp_model/core/model.py), layered **validation**, automatic **feature detection**, and pluggable backends. Entities reference each other via view objects (`Depot`, `Vehicle`, `Job`) on the same model. Optional **`label`** is for display/export only.

**Python:** 3.11+ · **Core dependency:** [`vrplib`](https://pypi.org/project/vrplib/) (instance I/O).

## Installation

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

Placeholder packages under `vrp_model/solvers/` (e.g. jsprit, vrpy) are **not** implemented; they are reserved for future work.

### What is modeled (VRP in this package)

Vehicle routing here means assigning jobs to vehicles (routes), respecting travel between unified **node ids** (depots and jobs), optional **capacity** dimensions, **time** logic (service durations, windows, and caps), **pickup–delivery** pairs, depot topology, and fleet diversity. The canonical [`Model`](vrp_model/core/model.py) holds jobs, vehicles, optional pickup–delivery links, and sparse **travel** overrides; [`Feature`](vrp_model/core/model.py) summarizes which constraint families appear so solvers can declare compatibility.

**Detection vs. adapters.** [`Model.detect_features()`](vrp_model/core/model.py) sets [`Feature`](vrp_model/core/model.py) from stored fields (e.g. any positive demand or non-empty vehicle capacity → `CAPACITY`; job or vehicle time windows → `TIME_WINDOWS`; soft penalties in [`TimeWindowFlex`](vrp_model/core/time_window_flex.py) → `FLEXIBLE_TIME_WINDOWS`). Other behavior—**service times**, Euclidean vs matrix travel, **primary optimization emphasis** (distance vs duration)—is not a `Feature` flag but is still passed through each solver adapter where the backend supports it.

### Solver capability matrix

Before solving, [`Solver.solve`](vrp_model/solvers/base.py) runs [`Model.validate()`](vrp_model/core/model.py) and [`Model.check_solver_compatibility(solver)`](vrp_model/core/model.py), which raises [`SolverCapabilityError`](vrp_model/core/errors.py) if a declared [`Feature`](vrp_model/core/model.py) is missing from the solver’s `supported_features`. One row per modeled capability:

| Feature | pyvrp | ortools | nextroute | vroom |
|---------------|:-----:|:-------:|:---------:|:-----:|
| Capacity (one or more resource dimensions; demands on jobs, caps on vehicles) | ✓ | ✓ | ✓ | ✓ |
| Hard time windows at jobs | ✓ | ✓ | ✓ | ✓ |
| Hard time windows at vehicles (shift / availability) | ✓ | ✓ | ✓ | ✓ |
| Pickup–delivery pairs (precedence and same vehicle) | ✓ | ✓ | ✓ | ✓ |
| Multi-depot (vehicles may start/end at different depots) | ✓ | ✓ | ✓ | ✓ |
| Heterogeneous fleet (distinct vehicle definitions) | ✓ | ✓ | ✓ | ✓ |
| Skills (jobs require a subset of vehicle skills) | ✗ | ✓ | ✓ | ✓ |
| Optional jobs / prize-collecting (mandatory vs skip penalty via `prize`) | ✓ | ✓ | ✗ | ✗ |
| Flexible time windows (linear soft penalties via `TimeWindowFlex`) | ✗ | ✓ | ✗ | ✗ |
| Vehicle fixed use cost (activation / fixed cost per route) | ✓ | ✓ | ✓ | ✓ |
| Maximum route distance per vehicle | ✓ | ✓ | ✓ | ✓ |
| Maximum route duration / shift length per vehicle | ✓ | ✓ | ✓ | ✓ |
| Route overtime (extra duration allowed + unit penalty on overage) | ✓ | ✓ | ✗ | ✗ |
| Maximum wait / time slack at nodes (`max_slack_time` on vehicles) | ✗ | ✓ | ✗ | ✗ |
| Service time at jobs (added into time accounting) | ✓ | ✓ | ✓ | ✓ |

**What each backend minimizes (not a `Feature` flag):** [`ORToolsSolver`](vrp_model/solvers/ortools/solver.py) minimizes total **travel distance** (arc cost from the distance matrix; time is a separate dimension). [`PyVRPSolver`](vrp_model/solvers/pyvrp/solver.py) minimizes PyVRP’s objective on the edge costs it receives as distance, with duration driving time feasibility. [`VroomSolver`](vrp_model/solvers/vroom/solver.py) passes duration and distance matrices; VROOM’s default behavior is **duration**-oriented for optimization. [`NextrouteSolver`](vrp_model/solvers/nextroute/solver.py) uses the Nextroute engine’s objective on the constructed instance.

## Model assumptions and travel

**Unified nodes:** The model stores one append-only list of nodes. Each row has a [`NodeKind`](vrp_model/core/kinds.py) (`DEPOT` or `JOB`). **`node_id`** is the row index—shared across depots and jobs in creation order. Use **`Depot.node_id`** and **`Job.node_id`** as keys in `(from_id, to_id)` travel maps.

**Locations:** Depot and job **`location`** are optional for *construction*, but feasibility validation requires every job to have coordinates **unless** you supply a non-empty sparse travel map (see below). Solvers may still synthesize coordinates internally when a location is missing (e.g. PyVRP).

**Sparse travel:** Travel is stored as `(from_id, to_id) → `[`TravelEdgeAttrs`](vrp_model/core/travel_edges.py) with optional **`distance`** and **`duration`** (`int` or `None`). At least one of distance or duration must be set on each stored edge. Model-level routing helpers treat a missing field on a stored edge as infinite cost; [`TRAVEL_COST_INF`](vrp_model/core/travel_edges.py) is the large sentinel (aligned with PyVRP’s `MAX_VALUE` scale).

- If **`travel_edges`** is **empty**, leg distance and duration fall back to **integer Euclidean** distances between planar coordinates for **all** pairs (depots and jobs). Validation then requires **every job** to have a **`location`**.
- If **`travel_edges`** is **non-empty**, the model uses **matrix-only** semantics: any directed pair not present in the map has infinite distance and duration (no Euclidean fallback for missing arcs).

Use **`set_travel_edges`**, **`update_travel_edge`**, and **`clear_travel_edges`** on the model; **`validate()`** checks node ids, forbids self-loops, and rejects negative costs.


## Solving and solutions

[`Solver.solve`](vrp_model/solvers/base.py) validates the model, checks capabilities, runs the backend, and attaches a [`Solution`](vrp_model/core/solution.py) to **`model.solution`**. The return value is [`SolutionStatus`](vrp_model/solvers/status.py) (mapped status, timing, stop reason, solver cost, etc.).

Use **`model.solution_cost()`**, **`model.is_solution_feasible()`**, and **`model.unassigned_jobs()`** for metrics; these raise **`SolutionUnavailableError`** if no solution is attached.

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
uv sync --group dev --extra pyvrp    # CI uses this set
uv run python -m unittest discover -s tests
uv run ruff check vrp_model tests && uv run ruff format vrp_model tests --check
uv run ty check vrp_model
```

Full solver coverage in tests requires installing the extras you care about (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml); default CI only adds `pyvrp`). Some tests skip backends that are not installed.
