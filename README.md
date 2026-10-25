# PaperLab

Human-guided workflows for reproducing machine learning research.

## Implemented so far

- Create a project with a paper URL, target result, dataset and metric.
- Choose Run, Retrain or Reimplement; Guided or Autonomous; and optional Learning support.
- Build an optional resource checklist for CPU, training, inference, API, simulation or mixed work.
- Add/remove suggested fields, leave unknowns blank, or record custom requirements.
- Search your experiment index by title, dataset, target or metric.
- Save setup changes as revisions with a human explanation.
- Preserve revision history and reject edits based on an older revision.

This is the project-setup milestone. Paper reading, agent execution, training, budget enforcement,
and Kaggle/Colab execution are planned. All projects remain drafts. Mode and resource fields are saved
configuration; they do not start agents or spend money.

## Run the Angular app

Requirements: Node.js 24.15 or newer in the 24.x line, npm, and uv with Python 3.12.

```sh
uv sync
npm --prefix apps/web ci
npm run dev
```

Open http://127.0.0.1:4200. The launcher applies database migrations and starts Angular and
FastAPI together. Ctrl+C stops both. Projects are stored in `.data/paperlab.db` across restarts.
The Angular development proxy forwards `/api` requests to FastAPI on port 8000.
Override ports with `PAPERLAB_WEB_PORT` and `PAPERLAB_API_PORT` when needed.

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
npm run build
npm run test:ui
```

Tests use temporary databases and the real migration. They check persistence after an app restart,
revision history, invalid input, stale edits, simultaneous edits and transaction rollback.

Before the first UI test, install Chromium into the workspace cache (PowerShell):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.cache/ms-playwright'
node apps/web/node_modules/@playwright/test/cli.js install chromium
```

UI tests start their own servers on ports 4201/8001 and use a separate SQLite database in
`.cache/e2e`. They cover project creation, persistence after refresh, revisions, competing edits,
validation, API failure recovery and mobile layout. Test screenshots are in `apps/web/test-results`.
When debugging with separately launched test servers, set `PAPERLAB_E2E_EXTERNAL_SERVER=1` to
skip the test runner's server launcher. Use a fresh, dedicated test database on port 8001 and
an Angular server on port 4201 configured with `PAPERLAB_API_PORT=8001`; never point this mode
at your working project database.
The Vite dependency override pins the compatible 8.3.3 security patch until Angular updates its pin.

## Manual test for this milestone

1. Open the Angular app and select **New project**, then **Use sample setup**.
2. Choose your modes and limits, then **Create project**. Refresh: your setup should remain.
3. Select **Revise setup**, change the metric, and enter the reason. Save the revision.
4. Confirm Revision 2 is current and Revision 1 still shows the original metric under **View saved setup**.
5. Open the edit form in two tabs. Save a change in one, then submit the other. It should ask you
   to reload the latest setup instead of overwriting the newer revision.

## Plan

Read [the implementation plan](PaperLab_Implementation_Plan.md) or open
`PaperLab_Implementation_Plan.html` in a browser. Regenerate the HTML with `node build_plan.cjs`.


## Adaptive resources (25 October 2026)

The resource section starts empty. Pick a workload to see suggested fields, then add only what
applies. Available capacity, runtime ceilings, API quotas, experiment spend and assistant spend
have separate fields and explicit units. Blank values are unknown; zero remains zero. Switching
workload keeps existing rows. Planned locations are preferences, not connected runtimes.

Try **CPU / classical ML**, add RAM, then switch to **Hosted API experiment**: RAM stays, and
API suggestions appear. Add a zero-dollar API budget, leave a request quota blank, and add a
custom license requirement. Save and refresh; each value should retain its meaning. Remove a
field in a revision; the previous revision should still contain it. Old v0.1 projects load through
backward-compatible resource normalization without rewriting historical JSON.

See [resource design and sources](docs/resource-design.md). Per-experiment extraction, feasibility
estimation and enforcement belong to the later execution stage.
