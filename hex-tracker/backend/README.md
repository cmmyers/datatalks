# Hex Tracker — Backend

FastAPI application implementing the contract in
[`../openapi.yaml`](../openapi.yaml). Not yet implemented — starts with an
in-memory mock store and tests for the key endpoints, then swaps in SQLite
behind a repository interface so Postgres can replace it later without a
rewrite.

Dependency management uses [uv](https://docs.astral.sh/uv/) — see
[`../AGENTS.md`](../AGENTS.md) for the command reference.
