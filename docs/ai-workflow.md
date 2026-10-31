# Groq research workflow

Implemented 31 October 2026. Angular presents a persistent FastAPI workflow backed by SQLAlchemy
and Alembic. It is a local, single-user workspace, not a hosted training service.

## Model connection

FastAPI loads the root `.env` without overriding process environment variables. `GROQ_API_KEY`
is used only in the provider Authorization header. `GET /ai/status` exposes the configured
boolean and model name, never the key. Restart after changing the key or model.

The default is `openai/gpt-oss-120b`. GPT-OSS calls use a strict structural JSON schema and low
reasoning effort; other configured models use JSON-object mode. All responses undergo local
Pydantic validation, duplicate-key rejection, task dependency checks and path validation.
Code drafts must contain a README, Python source and a dependency file; Python is parsed for
syntax without execution. These checks do not establish functional or scientific correctness.

Groq references: [structured outputs](https://console.groq.com/docs/structured-outputs),
[reasoning settings](https://console.groq.com/docs/reasoning),
[OpenAI-compatible endpoint](https://console.groq.com/docs/openai).

## Roles and prerequisites

| Stage | Role | Required input | Output |
| --- | --- | --- | --- |
| Analysis | Research analyst | Saved brief and paper source | Method, evidence, ambiguities and feasibility discussion |
| Plan | Experiment planner | Analysis | Tasks, dependencies and acceptance criteria |
| Implementation | Code author | Plan; exact-plan approval in Guided mode | Python starter files and setup instructions |
| Review | Methodology reviewer | Code draft | Static findings; no claim that tests passed |
| Results | Results analyst | Review and submitted metrics | Comparison with explicit self-reported provenance |
| Extensions | Research analyst | Analysis | Proposed controlled experiments |
| Report | Documentation author | Review | Draft report with limitations and available evidence |
| Chat | Learning assistant | Paper and current context | Explanation; no state-changing tools |

These roles use separate prompts and stored calls, currently with the same configured model.
“Independent reviewer” means a separate review role, not an independent model or execution grader.
Run, Retrain and Reimplement affect planning instructions, not available execution capabilities.

## State and human feedback

`paper_sources` stores immutable extracted text versions and SHA-256 digests. `agent_runs` stores
the input snapshot, source identity, output, status, error and usage. `research_workspaces` stores
the active source, artifact IDs, approved plan, feedback, evidence and workspace version.

Each mutation supplies `expected_version`; stale revisions receive HTTP 409. Every run has an
idempotency UUID. One run is active per project, with at most two provider requests across the
single API process. A process-local lock serializes workflow mutations. Do not use multiple API
workers; a shared queue and transactional worker claims are a later milestone.

Feedback invalidates the selected stage and later pipeline stages. Feedback affecting analysis,
planning or code also clears submitted result evidence. Plan changes revoke approval. Changes
to the brief invalidate all current AI artifacts. Replacing a source also clears accumulated
feedback; historical runs and sources remain stored. Each call receives the cumulative feedback.
Contradictory feedback may still require clarification; model adherence is not guaranteed.

Cancellation detaches the active run immediately. An in-flight provider call can still finish
and be billed, but its output cannot become a current artifact. Startup marks unfinished calls
interrupted without automatic retries. Autonomous dispatch is browser-driven and pauses when
the tab closes; the current backend call survives browser refresh.

## Evidence and budgets

The context selector includes the first page and keyword-ranked excerpts: up to 22,000
characters total and 5,000 per page. It does not perform OCR, figure understanding or exhaustive
full-paper analysis. Quotes are matched against the supplied excerpts; unmatched citations are
removed and flagged. A matching quote does not prove the surrounding interpretation is correct.

Assistant budgets use estimated Groq list prices for GPT-OSS 20B/120B, with a conservative
pre-call reservation and post-call usage accounting. Failed calls with uncertain usage retain
their reservation. A zero-dollar cap blocks calls. A positive dollar cap requires a priced
model and known prior cost estimates. Unspecified budgets have no dollar cap, but a project is
limited to 50 submitted AI requests per UTC day. Provider account quotas can stop calls earlier.
These estimates are not invoices or a provider-side billing guarantee. Compute, experiment API
spend and GPU-hour limits remain recorded requirements, not enforced runtime controls.

No generated code is executed. Submitted numeric metrics are explicitly self-reported and
linked to the current code artifact when one exists. The app cannot certify a reproduced result.

## API and exports

The Angular proxy adds `/api`; the FastAPI paths below do not include that prefix.

| Method | Path under `/projects/{id}/research` | Purpose |
| --- | --- | --- |
| GET | `/` (without trailing slash) | Current source, artifacts and latest 100 runs |
| POST | `/source/text`, `/source/url`, `/source/pdf` | Attach paper text |
| POST | `/runs` | Queue one scoped AI step |
| POST | `/feedback`, `/approve`, `/cancel` | Human steering |
| POST | `/evidence` | Record externally produced metrics |
| GET | `/export` | Download workspace ZIP |

The ZIP includes `project/` generated files and `paperlab/` contract, source versions, current
state/recent history, Markdown report and a notebook. The notebook materializes project files;
it does not install dependencies or start training. Review the exported README, then run the
project yourself. Direct Colab/Kaggle submission, VS Code extensions and MCP adapters are planned.

## Validation

The backend suite includes approval, feedback, source parsing, citation matching, cancellation,
restart recovery, idempotency, budget and export checks. Browser tests cover the research UI
using controlled provider responses; existing brief tests use a real local API. Live Groq
checks use an isolated database and a clearly fictional small methodology, not a real benchmark.
Synthetic metrics in that check test data flow only and must not be treated as experimental evidence.

Validation on 31 October 2026:

- 53 backend tests passed; Ruff passed and the locked dependency sync succeeded.
- The existing eight browser scenarios and four research-workspace scenarios passed. Research
  scenarios use controlled API responses to test guided approval, feedback, cancellation,
  missing-key behavior, mobile layout and provider-error retry.
- The Angular production build passed with the existing landing CSS size warning.
- A live isolated Groq walkthrough completed all eight role types, plan regeneration after
  feedback, exact-plan approval, code syntax validation and ZIP export. GPT-OSS 20B returned
  incomplete code in early checks; GPT-OSS 120B completed the small starter project and is now
  the default. This is a connectivity/integration check, not evidence of broad model reliability.
- Live provider failures exposed malformed output, incomplete files, account rate limits and
  oversized context. Validation, focused stage context and actionable error messages cover
  those cases. Large or ambiguous papers can still require a narrower scope or manual fixes.
- No generated training code was executed and no real paper result was reproduced in this check.

Next work: sandboxed execution, real data/environment checks, persisted autonomous dispatch,
independent evaluation, full-paper retrieval and authenticated multi-user operation. The original
LangGraph/Deep Agents architecture remains a roadmap, not a description of installed infrastructure.
