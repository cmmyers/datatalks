# Chore Tracker

A web-based tool for managing shared household chores. See
[`_docs/plan.md`](_docs/plan.md) for the full spec (features, stack, data
model, open questions).

## Status

Project scaffolding only — Django project (`choretracker`) and app
(`chores`) are wired up, but no models, views, or templates have been built
yet.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open `http://127.0.0.1:8000/`.
