# Project Conventions

## Code style

- Follow **PEP 8** for layout, imports, spacing, line length, and general Python style.
- Use **snake_case** for **functions**, **methods**, and **module-level variables**; **PascalCase** for **classes**; **UPPER_SNAKE_CASE** for **module-level constants**.
- Prefer descriptive names; align with what **ruff** enforces in this repo (run `ruff check` / `ruff format` after edits).

## Testing

- Use `unittest` (not pytest) for writing and running unit tests.
- Run tests via: `uv run python -m unittest discover -s tests`

## Package Manager

- Always use `uv` for dependency management, package installation, and running tools.
- Do **not** manually activate the virtual environment; `uv run` handles it automatically.
- Install packages: `uv pip install <package>`
- Sync dependencies: `uv sync`
- Build the project: `uv build`

## Linting and formatting

- Use **ruff** for linting and formatting (not black).
- Run: `uv run ruff check vrp_model` and `uv run ruff format vrp_model` (or `ruff format vrp_model --check` to only check).

## Type checking

- Use **ty** for type checking (not mypy or pyright).
- Run type checks via: `uv run ty check vrp_model`



# No backward compatibility

When changing **vrp-model / vrpulp** (public APIs, module layout, type names, dict keys, config, or behavior):

- **Do not** keep deprecated aliases, compatibility shims, re-exports “for old code,” dual naming, or version branches whose only purpose is to avoid breaking callers.
- **Do not** hesitate to rename types, move modules, or change signatures because external or hypothetical users might rely on the old shape.
- Prefer **one clear name and one behavior**; update **all in-repo** imports, tests, and docs in the same change.
- If something must remain stable for a short internal transition, treat that as an explicit exception and remove it in a follow-up—do not add open-ended compatibility layers.

This project is allowed to break its own API freely until you decide otherwise; optimize for clarity and correctness, not migration ergonomy.



# Verify After Every Change

After making any code change to **vrp-model**, run all three checks before considering the task done:

1. **Unit tests**: `uv run --all-extras python -m unittest discover -s tests` — include every optional extra (`pyvrp`, `ortools`, `vroom`, `nextroute`) so solver-backed tests are not skipped for missing dependencies.
2. **Type checking**: `uv run ty check vrp_model`
3. **Linting and formatting**: `uv run ruff check vrp_model` and `uv run ruff format vrp_model --check`

If any check fails, fix the issues before proceeding.
