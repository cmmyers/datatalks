# Hex Tracker — Backend

FastAPI application implementing the contract in
[`../openapi.yaml`](../openapi.yaml): boards and cards, backed by an
in-memory mock store behind a `BoardRepository` interface
([`app/repository.py`](app/repository.py)) so a SQLite (and later Postgres)
implementation can replace it without changing the routes.

Dependency management uses [uv](https://docs.astral.sh/uv/) — see
[`../AGENTS.md`](../AGENTS.md) for the command reference.

## Development

```sh
uv sync
uv run uvicorn app.main:app --reload
```

## Tests

```sh
uv run pytest
```
