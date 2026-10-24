# PaperLab Implementation Plan

Human guided agents for reproducing machine learning research

Prepared for the project owner · 24 October 2026 · Version 1.0

## 1 Purpose and recommended approach

PaperLab will turn a machine learning paper into a runnable implementation, recorded experiments, a comparison with the published results, one controlled extension, and a documented repository. The user remains able to correct, pause, redirect, or stop the work throughout the project.

**Human in the loop is a core control mechanism.** Feedback must change the saved project state and the work agents perform. A chat acknowledgment alone does not count as applying feedback. The interface must show the interpreted request, affected work, revised plan, and evidence that the change was carried out.

We will use an explicit workflow controller built with LangGraph, specialist Deep Agents for reasoning and coding, and isolated workers for actual training and evaluation. Start with one paper, one target result, and one compute worker. Expand the number of agents and supported research domains only after this complete path works reliably.

This document describes the proposed product, architecture, agent types, feedback behavior, implementation sequence, and acceptance criteria. The scenarios are illustrative product walkthroughs, not experiments that have already been run. Example scores and budgets are fictional.

### Product boundaries

- Support papers with accessible data and feasible compute first. Dataset access, missing implementation details, and hardware availability are explicit feasibility checks.
- Distinguish running released weights, retraining released code, and independently reimplementing a method.
- Report reproduced, partially reproduced, not reproduced under tested conditions, or inconclusive outcomes against a predefined target.
- Preserve the original experiment when adding extensions. A method change creates a separate branch of investigation.
- Prepare publication artifacts automatically. Publish externally when the user has authorized the destination, visibility, and content scope.

The September 2026 RECLAIM benchmark separates Run, Retrain, and Reimplement settings. Its evaluation shows that successful reproduction remains difficult and that generated implementations often lack numerical verification. This supports our focus on narrow targets and execution evidence. [RECLAIM](https://arxiv.org/abs/2609.28850)

## 2 User journey and features

The user creates a project with a PDF or paper URL, or asks for a shortlist on a topic. They enter available hardware, a compute limit, an LLM spending limit, and the desired reproduction mode. The product presents a feasibility assessment and a concrete target before beginning expensive work.

The main workspace contains a workflow view, feedback panel, experiment view, and evidence view. Each task displays its owner, current status, dependencies, artifact links, and any decision needed from the user. Progress comes from task and worker events rather than an invented percentage.

| Feature | First usable release | Later expansion |
| --- | --- | --- |
| Paper intake | PDF or URL, appendix and repository links, source citations | Topic discovery and ranked paper shortlists |
| Paper understanding | Method summary, target result extraction, missing details | Comparison across related papers |
| Reproduction contract | Dataset, split, metric, seeds, success rule, budget | Multiple claims and experiments per paper |
| Implementation | Task dependencies, code changes, tests, isolated execution | Parallel work in separate branches |
| Human feedback | Chat, artifact comments, approve, edit, reject, pause, stop | Team roles and review assignments |
| Experiment tracking | Logs, configurations, metrics, checkpoints, cost | Multiple GPU providers and experiment scheduling |
| Verification | Method checks, metric comparison, rerun from a clean environment | Broader paper-specific evaluation libraries |
| Extensions | One controlled ablation after the baseline | Multiple datasets and competing hypotheses |
| Learning support | Explain code and methodology on demand | Guided questions and interview preparation |
| Delivery | Repository export, README, report, reproduction command | Authorized GitHub publishing and Notion summaries |
| External workspaces | Open the project in VS Code and export a runnable Colab notebook | Submit and track Kaggle runs through its supported command line tools |

### Modes of operation

**Guided mode:** review the reproduction contract, important methodology decisions, and the extension plan. Routine work proceeds inside the accepted scope.

**Autonomous within limits:** the user authorizes a scope and resource envelope once. Agents continue until a decision exceeds those limits, a material ambiguity blocks progress, the target completes, or the user intervenes.

**Learning mode:** add short explanations and understanding checks at milestones. These are a configurable teaching feature and do not change the scientific verification requirements.

## 3 Agent roles and responsibilities

An agent is a model that reasons and calls tools. A worker is a process that executes code. A controller is application code that enforces state transitions and permissions. These responsibilities remain separate so that a model cannot bypass project limits by changing its plan.

The initial release has four configured agent roles: a research analyst, a planner, an implementation agent, and an independent verifier. Analysis and writing initially run as scoped tasks under the analyst. The full design separates them when their workload warrants it.

| Role and type | Inputs and tools | Output and authority |
| --- | --- | --- |
| Research analyst — research agent | Paper, appendices, search, source extraction, repository inspection | Cited summary, feasibility assessment, ambiguities; cannot invent missing parameters |
| Experiment planner — planning agent | Accepted target, budgets, dependencies, feedback | Versioned contract and task graph; proposes changes but cannot grant new spending authority |
| Implementation agent — coding agent | One task, relevant paper sections, repository, sandbox tools | Code commit, tests, implementation notes; cannot edit protected evaluation rules |
| Verification agent — reviewer agent | Paper, contract, code, immutable run evidence | Fidelity findings and claim verdicts; no authority to rewrite recorded results |
| Analysis agent — scientific analysis agent | Validated metrics, configurations, failed runs | Comparisons, uncertainty, discrepancy hypotheses, extension design |
| Documentation agent — writing agent | Verified evidence, accepted limitations, implementation notes | README and report with claim-to-evidence links; cannot create numerical results |
| Learning coach — optional teaching agent | Verified explanations, user questions, selected code | Explanations and understanding checks; cannot change experiment settings |

**Feedback interpretation is a planner capability, not another always-running agent.** An LLM may translate a comment into a proposed structured change. Application code validates that change against permissions, scientific constraints, and the current project revision.

**The workflow controller, job scheduler, budget service, artifact store, and publication service are deterministic services.** They handle transitions and execution regardless of what an agent says. The workflow controller is the final authority on which task may run next.

Use a reasoning-capable model for planning and verification, a coding-capable model for implementation, and a lower-cost model where extraction or formatting evaluations support it. Select actual models through project evaluations; record model, prompt, tool, and framework versions with every run.

### Delegation rules

- Give each task an objective, relevant sources, allowed tools, expected output schema, acceptance criteria, and resource limit.
- Parallelize independent reading, dataset inspection, or experiments. Coordinate dependent implementation changes through one repository owner or separate branches.
- Cap active subagents and nesting depth. Begin with at most two concurrent reasoning tasks and one compute job; tune from measurements.
- Pass compact context and artifact references. Store full logs and papers outside the conversation window.
- Share verified conclusions and explicit hypotheses separately. Do not promote an agent guess into durable factual memory.

These choices follow the context isolation and selective delegation patterns described in [Anthropic's multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) and [context engineering guidance](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents).

## 4 System architecture

The browser communicates with a Python API. The API stores user actions, streams progress, and invokes the workflow. Long-running training jobs execute outside web requests and outside LLM conversations.

```text
User workspace
  | feedback, approvals, pause and stop
  v
API and event stream
  |
  +--> Feedback service --> change validation --> revised plan
  |
  +--> LangGraph workflow controller
         | checkpoints, task dependencies, policy checks
         +--> Deep Agents for research, planning, coding and review
         +--> Job scheduler --> isolated CPU or GPU workers
         +--> Evidence registry --> results and report generation

Shared storage
  PostgreSQL: projects, revisions, feedback, approvals, tasks and jobs
  Artifact storage: papers, datasets or references, logs and checkpoints
  Git: code history                  MLflow: experiment records
```

| Component | Proposed implementation | Reason |
| --- | --- | --- |
| User interface | Angular with TypeScript | Workflow, artifact review, feedback, experiment comparison; typed reactive forms and signals for local view state |
| API | Python with FastAPI | Typed project endpoints and Python ML integration |
| Workflow | LangGraph with PostgreSQL checkpoints | Resumable stages and explicit routing |
| Reasoning tasks | Deep Agents with pinned dependencies | Tools, filesystem context, focused delegation and steering |
| Job execution | Separate worker service and durable PostgreSQL job table | Recoverable job submission without an extra queue in the MVP |
| Worker isolation | Containers on a dedicated worker host; stronger isolation for public multi-user use | Separate generated code from application credentials and host files |
| Metadata | PostgreSQL | Transactions, revisions, feedback history, leases and permissions |
| Experiment tracking | MLflow | Parameters, metrics, artifacts and run comparisons |
| Artifact storage | Local project storage initially; object storage for deployment | Large files remain outside checkpoint state |
| Source control | Git workspaces per project and revision | Trace implementation changes to experiments |
| Observability | Structured logs and trace records | Task, feedback and experiment IDs across services |

LangGraph checkpointers support thread state recovery; persistent stores serve longer-lived information. Use durable storage in deployment rather than an in-memory checkpointer. [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

Deep Agents supplies agent execution capabilities, but the application still owns budgets, job cancellation, scientific validity, and feedback impact analysis. Configure planning explicitly and pin a tested release because defaults change. [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)

MLflow provides the experiment record and comparison layer. The evidence registry links those records to source claims and plan revisions. [MLflow tracking](https://mlflow.org/docs/latest/tracking/)

### Coding and compute in VS Code Kaggle and Colab

PaperLab keeps the project in a normal Git repository with scripts, configuration, tests, and an optional notebook. The user chooses a workspace and a compute destination for each experiment. The same experiment configuration and run ID travel with the job, so results can be compared across platforms without losing their origin. User edits in an external workspace return as a commit or imported notebook revision; the verifier checks them before a revised experiment is accepted.

| Platform | What the user does there | PaperLab integration and practical boundary |
| --- | --- | --- |
| VS Code | Review and edit code, run tests, debug and use the terminal or notebooks | Open the repository, include documented tasks and environment setup, and sync Git changes. Local, remote SSH, and container development are options according to available compute. This is the preferred coding workspace. |
| Kaggle | Run a notebook or script where Kaggle data and eligible accelerators are available | Package a versioned Kaggle kernel, submit it through the official CLI, check status, fetch outputs, and attach them to the project run. Accelerator availability and runtime limits must be checked for that account and workload. |
| Google Colab | Open a generated notebook, select a runtime, execute cells and inspect outputs | Generate a self-contained notebook that installs dependencies, loads permitted data, resumes checkpoints where possible, and writes metrics and artifacts. For ordinary managed Colab, the user starts and supervises the notebook. Full unattended runtime control is a separate integration and is not assumed. |

The coding agent works against the Git repository in an authorized execution environment. If the user makes a change in VS Code or a notebook, PaperLab imports that change and reevaluates dependent tasks. If a job runs on Kaggle, the job adapter submits the code and retrieves results. Colab acts as a user-operated execution surface in the initial release. Google's Colab runtime API is beta and allowlist based; free managed runtimes are subject to changing limits and restrictions on remote control. We should not promise unattended multi-day training there. [Kaggle CLI](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md) · [Colab API](https://developers.google.com/colab/api/reference/rest) · [Colab FAQ](https://research.google.com/colaboratory/faq.html)

For long training, write checkpoints and metrics outside the disposable runtime, then resume on a suitable worker when supported. VS Code can connect to that worker for development; Kaggle is useful for bounded submissions; a persistent dedicated worker is the appropriate default when uninterrupted, multi-day execution is required. The experiment record captures the platform, hardware, image or package lockfile, dataset version, commit, seed, and artifact hashes.

## 5 End to end workflow

| Stage | Main work | Exit condition and human involvement |
| --- | --- | --- |
| Intake and feasibility | Inspect paper, data, code, licenses and compute needs | Select a feasible target or explain the blocker |
| Read and extract | Recover equations, algorithms, tables and evaluation details | Sources attached; unresolved assumptions visible |
| Define the contract | Fix mode, target result, protocol, success rule and budget | User accepts scope in guided mode; policy validates existing authorization |
| Plan | Create dependency graph and task acceptance checks | Tasks are executable within available tools and resources |
| Implement | Build data path, baseline, model, loss and evaluation incrementally | Component checks and methodology review pass |
| Smoke test | Tiny-data training, shape and gradient checks, metric checks | Data path and model run before full compute is spent |
| Run experiments | Submit configuration-bound jobs and capture outputs | Planned jobs complete or a bounded failure path is recorded |
| Verify and analyze | Compare implementation and measured results to the paper | Claim verdict supported by evidence; repair if justified and affordable |
| Extend | Test one accepted ablation or additional hypothesis | Separate experiment and comparison against the retained baseline |
| Package | Generate setup instructions, results, limitations and report | Clean-environment rerun checked; export or authorized publication |

Review happens throughout implementation, with a consolidated audit after experiments. A failed check returns to the smallest affected task. A change to preprocessing may invalidate all downstream training; a README wording change should not trigger a training rerun.

The reproduction contract stores the paper and target table row, task mode, dataset version and split, metric definition, preprocessing, training settings, seeds, hardware constraints, expected artifacts, numerical success criterion, missing details, approved deviations, and budgets. Select the success criterion before evaluating results, accounting for reported variability and available evidence. Do not choose a tolerance after seeing the outcome.

Maintain separate state fields for **workflow stage**, **execution status**, and **scientific outcome**. A completed workflow may legitimately produce an inconclusive scientific outcome.

```text
Execution status
READY -> RUNNING -> COMPLETED
             |-> WAITING_FOR_HUMAN -> READY
             |-> PAUSE_REQUESTED -> PAUSED -> READY
             |-> STOP_REQUESTED -> CANCELLED
             |-> FAILED -> bounded retry or user decision

Scientific outcome
UNASSESSED | REPRODUCED | PARTIALLY_REPRODUCED
NOT_REPRODUCED_UNDER_TESTED_CONDITIONS | INCONCLUSIVE
```

## 6 Human feedback at every stage

The earlier proposal included intervention points. This implementation makes human direction continuous: feedback can arrive during reading, planning, coding, training, analysis, or reporting. The system records it immediately and applies it at the earliest appropriate execution boundary.

### Feedback controls

The user can send a global instruction, comment on a paper passage or artifact, edit a configuration, reject a proposed action with a reason, approve a concrete change, pause and resume, stop a job, or branch an experiment. Every feedback entry has a visible status: received, interpreting, needs clarification, accepted, applying, applied, or unable to apply. An unable-to-apply status includes a reason and a next action.

| Feedback type | Example | Required behavior |
| --- | --- | --- |
| Preference | Explain the training loop more simply | Update explanations; leave scientific artifacts unchanged |
| Correction | Section 4 uses macro F1 | Check the cited section; update affected evaluation and reports |
| Constraint | Do not exceed two GPU hours | Enforce the remaining limit, stop new admissions, assess running work |
| Scope change | Use a different dataset | Create a revised contract or extension branch and identify invalidated results |
| Rejection | Do not use the authors' repository | Move to reimplementation, reassess feasibility and budget |
| Control | Pause now or stop all jobs | Prevent new dispatch immediately and request worker cancellation or checkpointing |
| Factual disagreement | This result proves the method is better | Examine evidence and revise conclusions only if supported |
| Conflicting instruction | Finish today and run every large experiment | Present the conflict and request a choice; continue independent work |

### How feedback is applied

1. **Record:** save the original text, actor, target, timestamp, current plan revision, and a unique feedback ID. Return an acknowledgment immediately.
2. **Interpret:** map the request to a typed change proposal with scope, urgency, rationale, and affected fields. Low-risk explicit edits can be parsed directly.
3. **Validate:** verify authorization, budget, allowed fields, scientific implications, and whether the target revision is still current. Do not execute an unvalidated model-generated patch.
4. **Find impact:** traverse task and artifact dependencies. Mark downstream results stale for the proposed revision, while preserving their history and the validity of unrelated work.
5. **Coordinate:** block affected task dispatch; request cancellation or a checkpoint for affected jobs. Show actual worker acknowledgments rather than claiming immediate cancellation.
6. **Revise:** atomically save the accepted contract and plan revision, the change diff, and the tasks to rerun. Invalidate approvals tied to superseded content.
7. **Resume:** send each affected agent a scoped task using the new revision. Reject stale writes from older tasks. Allow unaffected tasks to continue when safe.
8. **Verify and close:** rerun the relevant checks and attach the changed artifact links. Mark feedback applied only when its acceptance condition is satisfied.

**The user sees a change receipt:** “Applied your metric correction. Plan 4 replaces plan 3. Evaluation and results analysis will rerun; training remains valid because the metric did not affect checkpoint selection.” If checkpoint selection depended on the wrong metric, the receipt must include checkpoint reselection or retraining as appropriate.

### When to ask and when to continue

Apply clear, authorized feedback without asking the same question again. Pause for a precise clarification when ambiguity would materially change the experiment or cost. Ask before exceeding an existing resource limit, changing the accepted scientific target in a way the user has not specified, or publishing outside the accepted authorization.

Approval requests show the exact proposed action, affected artifacts, cost estimate, uncertainty, and scope. Bind approval to the action payload hash and plan revision. Silence never grants approval; expiry prevents execution. A clarification reply is not automatically permission for a separate costly action.

User instructions can change the research objective, but cannot make an unsupported numerical claim become true. If a requested methodological change creates an extension, retain that label even when the user prefers the new method.

### Running jobs and cancellation

The feedback API accepts input while jobs run. It does not mean arbitrary GPU code can pause instantly. The scheduler first blocks new affected jobs. Cooperative training jobs checkpoint at a batch or epoch boundary and report their stop state. After a configurable timeout, the worker may terminate the process tree, record an incomplete run, and release its lease. Unresponsive workers are isolated and their late outputs cannot update the active plan.

Set a target of under two seconds for feedback acknowledgment in the application. Cancellation latency is reported separately and depends on the worker. Hard compute limits require worker/provider enforcement; a natural-language instruction alone cannot guarantee a spending ceiling.

## 7 Implementation of feedback and state

Use LangGraph interrupts for planned human decision points. Resume a paused graph with the same thread ID and a structured decision. Node execution can restart on resume, so keep side effects in separate idempotent operations. [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

Configure tool-level approval through Deep Agents where useful. Its approval mechanism does not replace the application feedback service or worker cancellation. Background subagents can support steering, but changes still pass through the revision and policy checks. [Deep Agents human in the loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop) · [Async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents)

### Core records

| Record | Required fields |
| --- | --- |
| Project | Owner, paper, mode, execution status, active revision, limits |
| Contract revision | Target, protocol, success criteria, assumptions, deviations, parent revision |
| Task | Dependencies, agent role, input hashes, expected output, status, revision |
| Feedback | Actor, raw text, target, base revision, interpretation, status, resolution |
| Change proposal | Validated patch, impact set, cost effect, decision requirement |
| Approval | Actor, action hash, revision, decision, expiry, consumed status |
| Experiment run | Commit, configuration hash, dataset fingerprint, seed, hardware, metrics, logs, revision |
| Artifact | URI, content hash, producing task, input artifacts, validation status |
| Job | Worker lease, heartbeat, idempotency key, resource reservation, cancellation status |
| Event | Project sequence, event type, actor, revision, correlation IDs, timestamp |

PostgreSQL is the authority for accepted revisions. Apply each revision using an optimistic concurrency check on the expected version and a transaction. Use a transactional outbox to publish work only after the corresponding state commit. Scheduler deliveries may repeat; the worker deduplicates them with an idempotency key such as project, task, revision, and attempt.

A graph checkpoint does not roll back external GPU jobs or Git commits. Reconcile those resources explicitly when resuming or branching. Accept a job result into the active project only if its input hashes and revision still match; otherwise retain it as historical evidence.

### Feedback API outline

```text
POST /projects
POST /projects/{id}/feedback
POST /projects/{id}/decisions/{decision_id}
POST /projects/{id}/pause
POST /projects/{id}/resume
POST /projects/{id}/stop
GET  /projects/{id}/events          server sent events with replay cursor
GET  /projects/{id}/plan
GET  /projects/{id}/runs
GET  /projects/{id}/artifacts
```

Authenticate the actor and check project ownership on every endpoint. Feedback and decision requests carry an idempotency key and base revision. Stale approvals return a conflict with the current change preview. The event stream uses persisted sequence IDs so a reconnecting browser can recover missed updates.

### Example change record

```json
{
  "feedback_id": "fb_028",
  "project_id": "paperlab_demo",
  "base_revision": 3,
  "request": "Use macro F1 as specified in Section 4",
  "change_type": "methodology_correction",
  "patch": {"evaluation.metric": "macro_f1"},
  "impact": ["evaluation", "comparison", "report"],
  "new_revision": 4,
  "status": "applying"
}
```

The impact shown is valid only after checking whether the original metric affected model selection or training. The application computes that dependency; it is not assumed from the text alone.

## 8 Scientific reliability and execution controls

Every conclusion must resolve to a chain of evidence: paper claim, implementation task, code commit, experiment configuration, dataset version, run outputs, and verification verdict. Store original logs and raw metrics as immutable artifacts. Corrections create new records rather than silently replacing history.

The verifier combines executable checks with paper-specific review. Use schema checks, shape and gradient checks, tiny-data overfitting, metric fixture tests, split integrity checks, and a clean-environment execution. A reviewer model can inspect methodology but cannot replace measured results or independently establish correctness by agreeing with another model.

Predefine seeds and report the planned aggregate, variability, and failed runs. Use the validation split for repair and selection; keep the final test evaluation controlled. Avoid repeatedly tuning against the paper's test score. Protect the evaluator and final test artifacts from the implementation agent's write permissions.

Budget enforcement covers model calls, wall-clock time, CPU or GPU allocation, storage, retries, and concurrent jobs. Reserve estimated resources before admission and reconcile actual usage. Reject new jobs that cannot fit; stop running jobs when their hard limit is reached. Reuse valid artifacts by hashes rather than rerunning everything after each comment.

Generated code executes in project-specific isolation with restricted mounts and network access. Keep cloud credentials and publication tokens in narrowly scoped services outside the coding workspace. Treat text inside papers, repositories, and websites as research data, never as permission to change project policies.

Sakana AI's October 2026 Agentic Scientist uses executable research specifications, experimental evidence, and independent audits. Its evidence-linked approach informs this design, while PaperLab keeps reproduction and extensions distinct. [Agentic Scientist](https://pub.sakana.ai/agentic-scientist/)

## 9 Scenario walkthroughs

The following dialogues show intended live behavior. They use illustrative tasks and invented numbers to make state changes concrete.

### Scenario A Start a complete reproduction

**User:** “Reimplement this small image-classification paper. I have one 8 GB GPU and a four-hour compute limit. Reproduce the main table result and explain the code.”

**System:** checks the dataset, source details, model size, and likely runtime; presents the target metric, protocol, missing settings, and budget estimate. If feasibility is uncertain, it schedules an inexpensive pilot within the limit rather than promising completion.

**After scope acceptance:** the analyst extracts evidence, the planner creates dependencies, the coder implements and smoke-tests, and the worker trains. The verifier checks the implementation and experiment protocol. The learning coach explains selected components on request.

**Outcome:** a repository, measured comparison, explicit limitations, and a reproduction verdict. If compute is insufficient, the project finishes with an honest partial or inconclusive result and a clear continuation plan.

### Scenario B Correct the evaluation while training is running

**User:** “The paper uses macro F1, but your evaluator uses micro F1. Fix this.”

**System receipt:** “I will check the cited protocol, update the evaluator, and determine whether checkpoint selection is affected.”

The planner verifies the correction, creates a new revision, and marks evaluation and reporting stale. If training and checkpoint selection are independent of this metric, the current training can continue and retained predictions can be reevaluated. If checkpoint selection used micro F1, the system reassesses saved checkpoints or reruns necessary work.

**What the user sees:** the old and new metric definitions, affected tasks, updated scores, and the evidence that feedback was applied. Old results remain available with a superseded label.

### Scenario C Reduce cost mid experiment

**User:** “Stop after this seed and skip the remaining two seeds. I only have 30 minutes left.”

The controller prevents remaining seeds from starting and imposes the new time limit on the current job. It lets that seed finish only if it remains within the limit; otherwise the worker checkpoints and stops. The report switches from a planned three-seed aggregate to a clearly labeled single-seed observation.

**System receipt:** “Two queued runs were cancelled. The current run has a 30-minute cap. The final result will not support the originally planned across-seed uncertainty estimate.”

**Outcome:** reduced scope, preserved evidence, revised cost, and no false three-seed claim.

### Scenario D Change the method after seeing results

**User:** “AdamW might work better. Replace the paper's optimizer with it.”

The system treats the explicit request as authorization for a method change within the existing budget, while preserving the original reproduction run. It creates an extension branch and compares the new optimizer against the original under matched conditions. If this exceeds the budget, it asks for a specific scope or budget decision.

**System receipt:** “I created an optimizer extension. The original method and results remain the reproduction baseline.”

**Outcome:** a legitimate extension comparison; improved performance does not retroactively make the original reproduction successful.

### Scenario E Give ambiguous feedback or disagree with a conclusion

**User:** “Make it better and say we beat the paper.”

The system separates the ambiguous improvement request from the factual claim. It asks whether “better” means accuracy, runtime, memory, or clarity, and continues unaffected work. It explains that a superiority claim needs a comparable evaluation and supporting results.

If the observed score is 82.1 versus a paper score of 82.0, the system checks seeds, uncertainty, protocol, and comparability before interpreting the difference. It may report that the evidence is insufficient to establish improvement.

**Outcome:** the user's intended improvement becomes a concrete target; the report remains faithful to the evidence.

### Scenario F Resume after a crash and late feedback

The browser disconnects while a training worker continues. The user later reconnects and says, “Resume, but use the revised split file I uploaded.”

The API replays events, reconciles the worker job, validates the split, and creates a new revision. Existing runs retain their original split identity and cannot be counted toward the new contract. The planner reruns data validation and the necessary training and evaluation tasks.

If an older agent finishes after this change, its result is stored against the old revision and excluded from the active report. A duplicate resume request cannot launch a second copy of the same job.

**Outcome:** continuation from durable state, with stale work prevented from contaminating the revised experiment.

### Scenario G Review and publish

**User:** “The report is too technical. Shorten it, explain the limitations, and publish to my public portfolio repository.”

The writer revises the narrative without altering raw results. The application prepares the exact repository diff and publication preview, checks the destination and authorized scope, and executes only the publication covered by that authorization. Any new ambiguity about visibility, repository, or included material requires clarification.

**Outcome:** a readable portfolio artifact whose claims still link to experiments. The publication record identifies the exact commit and report version.

## 10 Implementation sequence

Build complete vertical slices so that each milestone demonstrates working behavior. The following six to eight week sequence is a planning estimate for one developer already comfortable with Python, web APIs, and ML tooling. It assumes accessible models and compute; it is not a delivery guarantee.

| Milestone | Implementation work | Acceptance gate |
| --- | --- | --- |
| 1 Foundation and specification | Project schema, contract schema, paper intake, one curated paper, protected evaluator and mock workers | A project and contract persist across restart; a small known experiment can be scored |
| 2 Execution and evidence | Worker isolation, durable jobs, logs, Git linkage, dataset fingerprints, MLflow and budget checks; VS Code setup and Colab export | One real experiment runs from a clean environment and produces traceable evidence |
| 3 Human feedback | Feedback API, interpretation, validation, revisions, approvals, pause, cancellation and event stream | A metric correction reruns affected work; a stale approval is rejected; duplicate feedback is harmless |
| 4 Agent workflow | Four initial roles, task schemas, scoped tools, smoke tests, bounded repair and review | One paper target travels from intake to verified report with visible human interventions |
| 5 Product and extension | Workflow UI, artifact comments, experiment comparison, one ablation, learning explanations, export and Kaggle run adapter | User can redirect work from the UI and inspect the before-and-after evidence |
| 6 Reliability and evaluation | Crash recovery, concurrent feedback tests, cost accounting, benchmark trials and documentation | No stale writes or duplicate jobs in the defined recovery tests; measured comparison with a baseline |

A useful first demonstration should arrive before the full interface: one curated paper, CLI or minimal UI, feedback during a run, and an evidence-linked report. Add topic discovery and multiple compute providers after the reproduction path is reliable.

### Repository organization

```text
paperlab/
  apps/web/                  workflow and feedback interface
  services/api/              authenticated project endpoints
  services/orchestrator/     graph, routing and revision handling
  services/worker/           sandbox lifecycle and job execution
  packages/contracts/       schemas for tasks, feedback and results
  packages/agents/           role prompts and tool definitions
  packages/skills/           reusable research procedures
  packages/evaluation/       protected checks and grading rubrics
  packages/storage/          revisions, events and artifact access
  migrations/               database schema changes
  tests/                    workflow, feedback and recovery tests
  examples/                 curated reproduction projects
  docs/                     architecture and operating instructions
```

Keep user research repositories outside the application source tree. A project workspace contains the paper, notes, implementation, configuration, data references, result references, and README. Large datasets and checkpoints belong in artifact storage rather than normal Git history.

## 11 Testing and release criteria

The most important tests verify behavior across agent, state, and worker boundaries. They should demonstrate that feedback changes execution and that scientific claims remain linked to valid evidence.

| Test | Expected behavior |
| --- | --- |
| Feedback before dispatch | New task receives revised inputs; old task is not started |
| Feedback during a job | Affected dispatch stops; cancellation or checkpoint status is visible |
| Old task finishes late | Output retained historically; active report stays on the current revision |
| Duplicate request | One feedback event or decision effect and one intended job |
| Conflicting edits | Stale base revision rejected or explicitly reconciled |
| Approval after plan change | Old approval cannot authorize the revised action |
| Controller crash | Checkpoint recovery reconciles existing jobs without duplicate launches |
| Budget exhaustion | No new work admitted; running work obeys enforced limits |
| Metric correction | Independent expected-value test passes and affected comparisons regenerate |
| Dataset or split change | Dependent runs become stale and cannot support the new target |
| Unsupported report statement | Publication package flags the claim until evidence or wording is corrected |
| Clean-environment rerun | Reproduction command recreates the declared evaluation within its defined tolerance |

Evaluate a small suite of feasible papers using comparable budgets. Compare a single coding-agent baseline, the proposed workflow, and versions without selected features such as independent verification. Run repeated trials where affordable and report the intervention policy used. Human-assisted and unattended results must be distinguishable.

Track verified target completion, false success claims, feedback application correctness, manual intervention time, cost per verified claim, elapsed time, duplicate jobs, and stale-result acceptance. Use executable graders for concrete outcomes and calibrated human review for methodology quality. [Agent evaluation guidance](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

### First release definition of done

- One selected paper completes the full path from contract to report using recorded execution evidence.
- A human can correct a metric, reduce the budget, pause, resume, and request an extension without restarting the whole project.
- Every feedback item has an auditable resolution, with changed artifacts or an explicit reason it could not be applied.
- Tests demonstrate no duplicate launches or stale-result promotion in the specified crash and concurrency cases.
- A fresh environment can execute the reproduction command; the result is judged against the accepted target.
- The exported repository includes setup, data instructions, results, deviations, limitations, one extension where feasible, and learning notes.

## 12 Decisions to settle before implementation

The architecture can begin with practical defaults: a single user, Python and PyTorch workloads, one Linux compute worker, one feasible paper, local artifact storage, and explicit GPU and model-call limits. These are proposed defaults, not assumptions about the user's existing hardware.

Before provisioning compute, choose the first paper, available GPU or CPU, LLM provider access, maximum spend, and whether the first task is Run, Retrain, or Reimplement. Before external publication, choose the repository destination and visibility. These decisions affect execution configuration rather than the overall feedback architecture.

The first implementation milestone is a demonstrable feedback loop: start a small experiment, receive a human correction, revise the saved plan, rerun only affected work, and show the corrected result with evidence.

## 13 Research references

Sources were consulted for the architecture proposal on 24 October 2026. Framework behavior should be verified against the pinned version during implementation. The feature choices, schemas, roadmap, and scenarios in this document are proposed application design.

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — durable workflow state and stores.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — human decision points, resumption and replay behavior.
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview) — agent tools, context management and delegation.
- [Deep Agents human in the loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop) — tool approval configuration.
- [Deep Agents async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents) — background tasks and steering.
- [MLflow tracking](https://mlflow.org/docs/latest/tracking/) — experiment metadata, metrics and artifacts.
- [RECLAIM](https://arxiv.org/abs/2609.28850) — reproduction modes and evaluation limitations.
- [The Agentic Scientist](https://pub.sakana.ai/agentic-scientist/) — executable research tasks and evidence-linked reporting.
- [Multi-agent research systems](https://www.anthropic.com/engineering/multi-agent-research-system) — delegation and coordination tradeoffs.
- [Context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) — focused context and persistent notes.
- [Agent evaluation guidance](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) — outcome-based agent evaluation.
- [Kaggle CLI kernels](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md) — submission, status and output retrieval.
- [Google Colab API](https://developers.google.com/colab/api/reference/rest) — current API availability.
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html) — runtime and usage limits.
- [VS Code remote development](https://code.visualstudio.com/docs/remote/remote-overview) — remote coding workflows.

The product workflow also incorporates the nine-step research-paper reproduction guide supplied by the project owner: find, read, create, plan, implement, reproduce, review, extend, and publish.
