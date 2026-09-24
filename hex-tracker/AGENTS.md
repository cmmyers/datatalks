# Agent instructions — Hex Tracker

## Project layout

```
backend/            # FastAPI application and its tests
deploy/             # AWS deployment — CloudFormation, prod compose file, Caddyfile (see deploy/README.md)
docs/               # supporting documentation (product spec, etc.)
e2e/                # Playwright tests against the docker-compose stack
frontend/           # React + TanStack Router SPA
Dockerfile          # multi-stage build: backend serves the built frontend
docker-compose.yaml # app + Postgres, for local runs and the e2e suite
openapi.yaml        # API contract — the source of truth between frontend and backend
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

## End-to-end tests

Run against the real container image + Postgres via docker-compose.yaml,
not a dev server — see docs/WEBSOCKETS.md for what they're covering (live
updates across sessions).

```sh
docker compose up --build -d   # from the repo root
cd e2e
npm install
npx playwright install chromium
BASE_URL=http://localhost:8100 npx playwright test
docker compose down -v         # from the repo root, once done
```

`playwright.config.ts` defaults `BASE_URL` to `http://localhost:8100`
(docker-compose.yaml's mapped port), so the env var above is only needed if
that's been changed. Tests run serially (`workers: 1`) — they all share one
app container, not an isolated fixture per test, so parallel workers just
contend with each other rather than speeding anything up.

## Git

Regularly commit code to git — small, focused commits over large batches.
