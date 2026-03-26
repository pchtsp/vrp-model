# vrp-model

Solver-agnostic vehicle routing problem (VRP) modeling: canonical `Model`, validation, feature detection, and pluggable solvers (PyVRP, more to come).

Entities reference each other via **view objects** (`Depot`, `Vehicle`, `Job`) from the same model. Optional **`label`** is for display/export only. **Depot and job `location`** are optional; PyVRP synthesizes coordinates when missing.

### Unified nodes and sparse travel costs

The model keeps a single append-only list of nodes. Each row has a **`NodeKind`** (`DEPOT` or **`JOB`**). **`node_id`** is the index of that row in the internal list—shared across depots and jobs, in creation order (so ids can interleave if you add a job between two depots). Use **`Depot.node_id`** and **`Job.node_id`** in `(from_id, to_id)` keys.

Travel is stored as a **sparse** map **`(from_id, to_id) → TravelEdgeAttrs`**, where **`TravelEdgeAttrs`** is a dataclass with optional **`distance`** and **`duration`** (`int` or `None`). At least one field must be set per stored edge. A field left **`None`** is sent to PyVRP as **infinite** cost (`TRAVEL_COST_INF`, aligned with **`pyvrp.constants.MAX_VALUE`**).

If **`travel_edges`** is **non-empty**, PyVRP treats **every** arc as matrix-only: any directed pair **not** in the map also gets infinite distance and duration (no Euclidean fallback). If **`travel_edges`** is **empty**, PyVRP uses **Euclidean** legs for all pairs, and **`validate()`** requires **every job** to have a **`location`** (no coordinates-only depot-only shortcuts).

Use **`set_travel_edges(...)`** (values may be **`TravelEdgeAttrs`** or mappings with optional `distance` / `duration` keys), **`update_travel_edge(...)`** to merge one arc, and **`clear_travel_edges()`** to remove overrides. **`validate()`** also rejects invalid node ids, self-loops, negative values, unknown mapping keys, and jobs without locations when the travel map is empty.

PyVRP’s internal location order is **all depots** (by ascending `node_id`), then **all jobs** (by ascending `node_id`); the adapter maps that to your unified ids when reading solutions.

### VRPLIB (`vrplib`)

`read_model` and `vrplib_dict_to_model` construct a `Model` **without** calling `validate()`. Call `model.validate()` when you need full consistency checks, or rely on `Solver.solve`, which validates before solving. Use `write_vrplib_instance` to write instances and `write_vrplib_solution` for solution files.

## Example

```python
from vrp_model import Model
from vrp_model.solvers.pyvrp import PyVRPSolver

model = Model()
depot = model.add_depot(location=(0.0, 0.0), label="hub")
vehicle = model.add_vehicle(10, depot, label="truck1")
job = model.add_job(3, location=(1.0, 2.0))

status = PyVRPSolver({"time_limit": 2.0, "msg": False}).solve(model)
solution = model.solution
```

## Development

```bash
uv sync --group dev --extra pyvrp
uv run python -m unittest discover -s tests
uv run ruff check vrp_model tests && uv run ruff format vrp_model tests --check
uv run ty check vrp_model
```
