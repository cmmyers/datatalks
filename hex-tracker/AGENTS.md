# Agent instructions — Hex Tracker

## Project layout

```
backend/      # FastAPI application and its tests
docs/         # supporting documentation (product spec, etc.)
frontend/     # React + TanStack Router SPA
openapi.yaml  # API contract — the source of truth between frontend and backend
```

`openapi.yaml` is authoritative. Frontend and backend code should conform to
it, not the other way around — if a change requires a different request or
response shape, update the contract first, then bring both sides in line.

See [docs/SPEC.md](docs/SPEC.md) for the product spec (user stories,
acceptance criteria, non-goals).

## Frontend

```sh
cd frontend
npm install
npm run dev
```

## Backend

Dependency management uses [uv](https://docs.astral.sh/uv/):

```sh
cd backend
uv sync                    # install dependencies
uv add <package-name>      # add a dependency
uv run python <file.py>    # run a script inside the project's venv
```

## Git

Regularly commit code to git — small, focused commits over large batches.
