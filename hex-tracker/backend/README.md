# Hex Tracker — Backend

FastAPI application implementing the contract in
[`../openapi.yaml`](../openapi.yaml): boards and cards, stored behind a
`BoardRepository` interface ([`app/repository.py`](app/repository.py)) with
two interchangeable implementations:

- `InMemoryBoardRepository` — a process-local dict, used by the test suite.
- `SqlBoardRepository` — SQLAlchemy-backed, used at runtime. Defaults to a
  local SQLite file (`hex_tracker.db`), but uses no SQLite-specific types or
  features, so pointing `DATABASE_URL` at Postgres instead is a config
  change, not a rewrite.

Dependency management uses [uv](https://docs.astral.sh/uv/) — see
[`../AGENTS.md`](../AGENTS.md) for the command reference.

## Development

```sh
uv sync
uv run uvicorn app.main:app --reload
```

Set `DATABASE_URL` to point at a different database (e.g.
`postgresql://user:password@host/dbname`); it defaults to
`sqlite:///./hex_tracker.db`.

## Tests

```sh
uv run pytest
```

Every test runs against both `InMemoryBoardRepository` and an in-memory
SQLite-backed `SqlBoardRepository` (see `tests/conftest.py`), so passing
tests demonstrate the API contract holds regardless of storage backend.
