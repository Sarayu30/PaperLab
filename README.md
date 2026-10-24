# PaperLab

Human-guided workflows for reproducing machine learning research.

## Implemented so far

- Create a project with a paper URL, target result, dataset and metric.
- Choose Run, Retrain or Reimplement; Guided or Autonomous; and optional Learning support.
- Record GPU-hour and model-spending limits.
- Save setup changes as revisions with a human explanation.
- Preserve revision history and reject edits based on an older revision.

This is the project-setup milestone. Paper reading, agent execution, training, budget enforcement,
and Kaggle/Colab execution are planned. All projects remain drafts. Mode and budget fields are saved
configuration; they do not start agents or spend money.

## Local API

Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.12 (uv can install Python).

```sh
uv sync
uv run alembic upgrade head
uv run uvicorn paperlab_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs to try the API. The database defaults to `.data/paperlab.db`.
It survives restarts and is excluded from Git. Set `PAPERLAB_DATABASE_URL` in the process environment
to use a different database. `.env.example` documents available settings; files are not loaded
automatically. SQLite is the tested local default; PostgreSQL is supported by the storage configuration
but requires a running server and separate integration validation.

Run this milestone on loopback only. Authentication and multi-user access are not implemented.
Recorded paper URLs are not fetched yet. PDF upload and paper parsing come in the next milestone.

## Checks

```sh
uv run pytest
uv run ruff check .
```

Tests use temporary databases and the real migration. They check persistence after an app restart,
revision history, invalid input, stale edits, simultaneous edits and transaction rollback.

## Manual test for this milestone

1. In `/docs`, create a project with `POST /projects`.
2. Retrieve it and confirm the settings you entered.
3. Add a revision with `POST /projects/{id}/revisions`, its current revision number and a reason.
4. Repeat the old revision request: it should return 409 rather than overwrite your newer setup.
5. Restart the API and confirm your project and both revisions are still present.

## Plan

Read [the implementation plan](PaperLab_Implementation_Plan.md) or open
`PaperLab_Implementation_Plan.html` in a browser. Regenerate the HTML with `node build_plan.cjs`.

