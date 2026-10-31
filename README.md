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

- Import paper text from a PDF, a supported paper URL, or pasted text.
- Use Groq for analysis, experiment planning, code drafts, static review, results commentary,
  extension proposals, reports and paper chat.
- Approve the exact plan in Guided mode; apply feedback to regenerate affected stages.
- Retain source versions, run history, usage estimates and previous outputs across refreshes.
- Stop an AI step, reject stale outputs, and enforce estimated assistant budgets before calls.
- Export code, a Colab/Kaggle handoff notebook, source provenance and a Markdown report.

This is a local AI research workspace. Generated code is a **draft**, checked for required files
and Python syntax but not executed by PaperLab. Training, sandbox workers, direct Kaggle/Colab
execution, independent metric verification, authentication, and multi-process orchestration are
still planned. The current controller uses explicit stages and scoped Groq prompts; LangGraph,
Deep Agents and MCP execution adapters are not installed.

## Run the Angular app

Requirements: Node.js 24.15 or newer in the 24.x line, npm, and uv with Python 3.12.

```sh
uv sync
npm --prefix apps/web ci
npm run dev
```

Keep `GROQ_API_KEY` in the repository-root `.env`. It is loaded by FastAPI and ignored by Git;
never put it in Angular configuration. The default model is `openai/gpt-oss-120b`, selected after
live code-generation checks. Set `GROQ_MODEL` to override it, then restart the API. Project setup
works without a key; AI requests require one. The UI's configured indicator confirms a key is
present, not that the provider has accepted it.

Open http://127.0.0.1:4200. The launcher applies database migrations and starts Angular and
FastAPI together. Ctrl+C stops both. Projects are stored in `.data/paperlab.db` across restarts.
The Angular development proxy forwards `/api` requests to FastAPI on port 8000.
Override ports with `PAPERLAB_WEB_PORT` and `PAPERLAB_API_PORT` when needed.

The home route is a working research overview. It displays the latest three saved briefs, a
resource explorer using the actual setup catalogue, and a source-linked architecture explorer.
The original `[p.] PaperLab` wordmark is retained. Choosing a workload opens a new brief with
that workload preselected; it never invents resource values or saves a project automatically.
The interface retains the dark research theme and anonymous illustrative paper preview.
**Your notebook** opens `/projects`; **Start a research brief** opens `/projects/new`.
Open a saved brief and choose **Open research workspace** to use the AI stages.

## Local API

Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.12 (uv can install Python).

```sh
uv sync
uv run alembic upgrade head
uv run uvicorn paperlab_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs to try the API. The database defaults to `.data/paperlab.db`.
It survives restarts and is excluded from Git. Set `PAPERLAB_DATABASE_URL` in `.env` or the process
environment to use a different database; process values take precedence. `.env.example` documents
available settings. SQLite is the tested local default; PostgreSQL is supported by the storage configuration
but requires a running server and separate integration validation.

Run one API process on loopback only. Authentication and multi-user access are not implemented.
URL import supports HTTPS arXiv, CVF and OpenReview; redirects are checked against the same
allowlist. PDF upload accepts text-based documents up to 10 MB and 80 pages. Scanned pages and
figures are not interpreted. Inspect extracted text before starting analysis.

An AI call sends selected paper excerpts, the saved brief, feedback, relevant earlier artifacts
and any submitted metrics to Groq. The provider key stays on the server. A request already sent
may incur usage even if cancelled. Interrupted requests are never retried automatically.

## Checks

```sh
uv run pytest
uv run ruff check .
npm run build
npm run test:ui
```

Tests use temporary databases and the real migrations. They check persistence, revision history,
invalid input, stale edits, simultaneous edits, transaction rollback, approval gates, feedback,
late cancellation, interrupted requests, source citation matching, budget rejection, safe export
paths and incomplete code rejection. Provider calls are mocked in the automated suite.

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

## Try the AI workflow

1. Create or open a brief. Set a positive **assistant budget** if you want a cap; zero blocks AI
   calls, while leaving it unspecified does not set a dollar cap. Compute limits are separate.
2. Open **Research workspace**, then import a paper URL, upload a PDF, or paste at least 100
   characters of source text. Check the extracted source pages.
3. Run **Understand the paper**, then **Plan the experiment**. In Guided mode, **Draft the code**
   stays blocked until you approve the current plan.
4. Approve the plan, generate code and run the static review. Download the project ZIP and
   review the files before running them yourself in VS Code, Colab or Kaggle.
5. Apply feedback to the plan: “Use CPU only and report macro F1.” The analysis should remain;
   the old plan approval and downstream code/review should become stale. Review and approve
   the regenerated plan before coding again.
6. Use **Ask about the paper** for explanations. Chat does not silently modify the plan; use
   the feedback form for changes.
7. After an actual external run, enter numeric metrics, hardware and the run command. Result
   analysis labels this evidence as self-reported. Generate extension proposals and a report.
8. Refresh: saved sources, outputs and history remain. If a provider rate limit occurs, wait
   and click **Run this step** again; PaperLab does not retry paid calls automatically.

Autonomous mode continues eligible AI stages while the tab stays open. It skips result analysis
until metrics exist, stops on failures or human changes, and does not launch training. Closing
the tab stops future dispatch; an already accepted backend step can finish. API restarts mark
unfinished requests interrupted and require an explicit retry.

See [AI workflow architecture and limits](docs/ai-workflow.md).

## Check project setup and revision history

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
