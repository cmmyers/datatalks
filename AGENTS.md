# AGENTS.md

Instructions for AI coding agents working in this repo.

## Project

Household Chore Tracker — a local-only Django web app for managing shared
chores across households, with point-based accountability instead of
enforcement. Full spec (features, data model, decisions): see
[`_docs/plan.md`](_docs/plan.md). Task-by-task build plan: see
[`_docs/tasks.md`](_docs/tasks.md) — work through it in order unless told
otherwise, and read the relevant task's description before starting it since
each is scoped to be self-contained.

## Documents

- `_docs/process.md` - how work is organized

## Stack

- Django (project `choretracker`, app `chores`), SQLite via the ORM.
- Plain Django templates for pages; `fetch` calls to Django views (returning
  JSON) for dynamic interactions. No JS framework, no Node/npm build step.
- Identity is session-based (`django.contrib.sessions`), not
  `django.contrib.auth` — there are no passwords/accounts. A session holds
  the current `User.id` it's "acting as."
- Local only — no deployment/hosting concerns, no auth hardening beyond what
  the spec calls for.

## Commands

```bash
source .venv/bin/activate
python manage.py test          # run the test suite
python manage.py runserver     # run the dev server (http://127.0.0.1:8000/)
python manage.py makemigrations && python manage.py migrate
```

## Conventions

- Every model/view change that has behavior worth asserting should come with
  a test using Django's test client — the backlog tasks each specify what to
  cover; match that scope, don't under- or over-test.
- Household data must stay isolated: any query for chores, members, or
  points must be scoped to the active household. Tests for list/board views
  should assert other households' data is excluded.
- Names are unique **within** a household (case-insensitive), never
  globally — don't add cross-household name matching or identity merging.
- Chores are recurring: completing one resets it to `open` rather than
  deleting it. `WeeklyCompletion` is the append-only source of truth for both
  the current points board and history.
- Weeks run Monday–Sunday, server local time — hardcoded, not configurable.
- Keep the frontend plain HTML/CSS/JS rendered through Django templates; do
  not introduce a JS framework, bundler, or DRF unless explicitly asked.
