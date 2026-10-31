"""A local, durable workflow with revision guards and bounded background model calls.

Run one API process. Generated code is never executed by the API process.
"""

import ast
import io
import json
import re
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .config import groq_settings
from .groq_client import GroqClient, ModelError
from .models import AgentRun, ContractRevision, PaperSource, Project, ResearchWorkspace
from .paper_intake import MAX_BYTES, digest, fetch_pdf, pages_from_pdf, source_context
from .research_prompts import BASE, PROMPTS
from .research_schemas import (
    PIPELINE,
    AgentOutput,
    ApprovalRequest,
    EvidenceRequest,
    FeedbackRequest,
    RunRequest,
    TextSource,
    VersionRequest,
)
from .schemas import ProjectSetup


def now():
    return datetime.now(UTC)


def run_view(run):
    return {
        "id": run.id,
        "stage": run.stage,
        "status": run.status,
        "workspace_version": run.workspace_version,
        "project_revision": run.project_revision,
        "output": run.output,
        "usage": run.usage,
        "error": run.error,
        "message": run.context.get("message", ""),
        "feedback": run.context.get("human_feedback", ""),
        "source_id": run.context.get("source_id"),
        "source_digest": run.context.get("source_digest"),
        "included_pages": [p["page"] for p in run.context.get("source_pages", [])],
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


class ResearchService:
    def __init__(self, engine, provider=None):
        self.engine = engine
        self.provider = provider or GroqClient()
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="paperlab-ai")

    def recover(self):
        try:
            with Session(self.engine) as session, session.begin():
                for run in session.scalars(
                    select(AgentRun).where(AgentRun.status.in_(["queued", "running"]))
                ):
                    run.status = "interrupted"
                    run.error = (
                        "API restarted during this request. Retry explicitly; no automatic spend."
                    )
                    run.finished_at = now()
                for workspace in session.scalars(select(ResearchWorkspace)):
                    workspace.active_run = None
        except SQLAlchemyError:
            # Health endpoint reports missing migrations without preventing startup.
            pass

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

    def workspace(self, session, project_id):
        project = session.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        workspace = session.get(ResearchWorkspace, project_id)
        if workspace is None:
            workspace = ResearchWorkspace(
                project_id=project_id,
                version=1,
                project_revision=project.revision,
                artifacts={},
                feedback="",
                evidence={},
            )
            session.add(workspace)
            session.flush()
        if workspace.project_revision != project.revision:
            self.invalidate(session, workspace, "analysis")
            workspace.project_revision = project.revision
            workspace.evidence = {}
        return project, workspace

    def checked(self, session, project_id, expected):
        project, workspace = self.workspace(session, project_id)
        if workspace.version != expected:
            raise HTTPException(409, "The workspace changed. Refresh before continuing.")
        return project, workspace

    def invalidate(self, session, workspace, stage):
        if workspace.active_run:
            run = session.get(AgentRun, workspace.active_run)
            if run and run.status in {"queued", "running"}:
                run.status, run.finished_at = "cancelled", now()
                run.error = (
                    "Superseded by a human change. In-flight provider usage may still apply."
                )
        workspace.active_run = None
        workspace.version += 1
        index = PIPELINE.index(stage)
        workspace.artifacts = {
            key: value for key, value in workspace.artifacts.items() if key in PIPELINE[:index]
        }
        if index <= PIPELINE.index("plan"):
            workspace.approved_plan = None
        if index <= PIPELINE.index("implementation"):
            workspace.evidence = {}

    def snapshot(self, project_id):
        with self.lock, Session(self.engine) as session, session.begin():
            project, workspace = self.workspace(session, project_id)
            source = session.get(PaperSource, workspace.source_id) if workspace.source_id else None
            runs = list(
                session.scalars(
                    select(AgentRun)
                    .where(AgentRun.project_id == project_id)
                    .order_by(AgentRun.created_at.desc())
                    .limit(100)
                )
            )
            artifacts = {
                stage: run_view(session.get(AgentRun, run_id))
                for stage, run_id in workspace.artifacts.items()
            }
            return {
                "version": workspace.version,
                "project_revision": project.revision,
                "source": {
                    "id": source.id,
                    "name": source.name,
                    "digest": source.digest,
                    "pages": source.pages,
                }
                if source
                else None,
                "artifacts": artifacts,
                "approved_plan": workspace.approved_plan,
                "active_run": workspace.active_run,
                "feedback": workspace.feedback,
                "evidence": workspace.evidence,
                "runs": [run_view(run) for run in runs],
                "total_tokens": sum(run.usage.get("total_tokens", 0) for run in runs),
                "cost_note": "List-price estimates, not provider invoices. "
                "Uncertain calls retain their reservation.",
            }

    def attach(self, project_id, expected, name, pages):
        with self.lock, Session(self.engine) as session, session.begin():
            _, workspace = self.checked(session, project_id, expected)
            self.invalidate(session, workspace, "analysis")
            source = PaperSource(
                id=str(uuid4()),
                project_id=project_id,
                name=name[:200],
                digest=digest(pages),
                pages=pages,
                created_at=now(),
            )
            session.add(source)
            session.flush()
            workspace.source_id = source.id
            workspace.feedback, workspace.evidence = "", {}
        return self.snapshot(project_id)

    def feedback(self, project_id, request):
        if request.stage == "chat":
            raise HTTPException(422, "Choose the workflow stage to revise, not chat.")
        with self.lock, Session(self.engine) as session, session.begin():
            _, workspace = self.checked(session, project_id, request.expected_version)
            combined = workspace.feedback + f"\n[{request.stage}] {request.message.strip()}"
            if len(combined) > 20000:
                raise HTTPException(
                    422, "Feedback history is full. Start a new brief for a different scope."
                )
            self.invalidate(session, workspace, request.stage)
            workspace.feedback = combined
        return self.snapshot(project_id)

    def approve(self, project_id, request):
        with self.lock, Session(self.engine) as session, session.begin():
            _, workspace = self.checked(session, project_id, request.expected_version)
            if workspace.artifacts.get("plan") != str(request.plan_id) or workspace.active_run:
                raise HTTPException(409, "Only the current, idle plan can be approved.")
            workspace.approved_plan = str(request.plan_id)
        return self.snapshot(project_id)

    def evidence(self, project_id, request):
        with self.lock, Session(self.engine) as session, session.begin():
            _, workspace = self.checked(session, project_id, request.expected_version)
            self.invalidate(session, workspace, "results")
            workspace.evidence = {
                **request.model_dump(exclude={"expected_version"}),
                "provenance": "self-reported",
                "recorded_at": now().isoformat(),
                "implementation_id": workspace.artifacts.get("implementation"),
            }
        return self.snapshot(project_id)

    def start(self, project_id, request):
        with self.lock, Session(self.engine) as session, session.begin():
            duplicate = session.scalar(
                select(AgentRun).where(AgentRun.request_id == str(request.request_id))
            )
            if duplicate:
                if (
                    duplicate.project_id != project_id
                    or duplicate.stage != request.stage
                    or duplicate.context.get("message", "") != request.message
                    or duplicate.workspace_version != request.expected_version
                ):
                    raise HTTPException(409, "Request ID already belongs to another request.")
                return run_view(duplicate)
            project, workspace = self.checked(session, project_id, request.expected_version)
            if workspace.active_run:
                raise HTTPException(409, "An AI step is already running. Wait or cancel it.")
            if not workspace.source_id:
                raise HTTPException(422, "Attach a paper before running AI steps.")
            stage = request.stage
            requirements = {
                "plan": "analysis",
                "implementation": "plan",
                "review": "implementation",
                "results": "review",
                "extensions": "analysis",
                "report": "review",
            }
            if requirements.get(stage) and requirements[stage] not in workspace.artifacts:
                raise HTTPException(422, f"Complete {requirements[stage]} first.")
            if stage in workspace.artifacts:
                raise HTTPException(
                    409, "Apply feedback to invalidate this step before regenerating it."
                )
            setup = ProjectSetup.model_validate(
                session.get(ContractRevision, (project_id, project.revision)).setup
            ).model_dump(mode="json")
            if stage == "implementation":
                if (
                    setup["control_mode"] == "guided"
                    and workspace.approved_plan != workspace.artifacts["plan"]
                ):
                    raise HTTPException(
                        409, "Review and approve the current plan before generating code."
                    )
            if stage == "results" and not workspace.evidence:
                raise HTTPException(422, "Record real run metrics before analyzing results.")
            if stage == "chat" and not request.message.strip():
                raise HTTPException(422, "Enter a question.")
            key, model = groq_settings()
            if not key:
                raise HTTPException(503, "GROQ_API_KEY is missing from the backend .env.")
            source = session.get(PaperSource, workspace.source_id)
            context = {
                "contract": setup,
                "paper_name": source.name,
                "source_id": source.id,
                "source_digest": source.digest,
                "source_pages": source_context(
                    source.pages, setup["target_result"] + request.message
                ),
                "total_paper_pages": len(source.pages),
                "human_feedback": workspace.feedback,
                "message": request.message,
                "self_reported_evidence": workspace.evidence,
                "prior_artifacts": {},
            }
            for name, run_id in workspace.artifacts.items():
                previous = session.get(AgentRun, run_id).output
                # Keep full generated code for review; other stages get concise summaries.
                context["prior_artifacts"][name] = (
                    previous
                    if name in {"plan", "implementation"}
                    else {
                        "summary": previous.get("summary"),
                        "warnings": previous.get("warnings", []),
                    }
                )
            if stage == "chat":
                recent_chat = list(
                    session.scalars(
                        select(AgentRun)
                        .where(
                            AgentRun.project_id == project_id,
                            AgentRun.stage == "chat",
                            AgentRun.status == "completed",
                            AgentRun.workspace_version == workspace.version,
                        )
                        .order_by(AgentRun.created_at.desc())
                        .limit(4)
                    )
                )
                context["conversation"] = [
                    {"question": r.context.get("message"), "answer": r.output.get("summary")}
                    for r in reversed(recent_chat)
                ]
            if len(json.dumps(context)) > 150000:
                raise HTTPException(
                    422, "Context is too large. Narrow the implementation or start a focused brief."
                )
            all_runs = list(
                session.scalars(select(AgentRun).where(AgentRun.project_id == project_id))
            )
            if sum(r.created_at.date() == now().date() for r in all_runs) >= 50:
                raise HTTPException(429, "This project reached its 50 AI requests/day safety cap.")
            budget = next(
                (
                    row["value"]
                    for row in setup["resource_plan"]["requirements"]
                    if row["kind"] == "assistant_budget"
                ),
                setup.get("max_llm_cost_usd"),
            )
            # Published Groq list prices verified 2026-10-29; unknown models cannot use a USD cap.
            prices = {"openai/gpt-oss-20b": (0.075, 0.30), "openai/gpt-oss-120b": (0.15, 0.60)}
            rates = prices.get(model)
            reservation = None
            if rates:
                # One token cannot encode less than one byte; add room for schema/chat framing.
                input_bound = len((BASE + PROMPTS[stage] + json.dumps(context)).encode()) + 15000
                reservation = (input_bound * rates[0] + 6000 * rates[1]) / 1_000_000
            if budget is not None:
                if budget == 0 or rates is None:
                    raise HTTPException(
                        422,
                        "Assistant budget blocks this call. "
                        "Use a positive budget and a priced GPT-OSS model.",
                    )
                if any(r.usage.get("reserved_usd") is None for r in all_runs):
                    raise HTTPException(
                        422,
                        "Earlier calls have unknown cost. "
                        "Start a new budgeted brief to enforce a USD cap.",
                    )
                spent = sum(
                    r.usage.get("estimated_usd", r.usage.get("reserved_usd", 0)) or 0
                    for r in all_runs
                )
                if spent + reservation > budget:
                    raise HTTPException(
                        422, "The next model call would exceed the recorded assistant budget."
                    )
            run = AgentRun(
                id=str(uuid4()),
                project_id=project_id,
                workspace_version=workspace.version,
                project_revision=project.revision,
                request_id=str(request.request_id),
                stage=stage,
                status="queued",
                context=context,
                output={},
                error="",
                usage={"reserved_usd": reservation, "rates": rates, "model": model},
                created_at=now(),
            )
            workspace.active_run = run.id
            session.add(run)
            session.flush()
            result = run_view(run)
        self.pool.submit(self.execute, result["id"])
        return result

    def execute(self, run_id):
        with self.lock, Session(self.engine) as session, session.begin():
            run = session.get(AgentRun, run_id)
            if run.status != "queued":
                return
            run.status = "running"
            context, stage = run.context, run.stage
        try:
            output, usage = self.provider.generate(BASE + PROMPTS[stage], context, AgentOutput)
            output = AgentOutput.model_validate(output).model_dump(mode="json")
            if stage == "plan" and not output["tasks"]:
                raise ModelError(
                    "The plan contained no actionable tasks. Retry with a clearer target."
                )
            if stage == "implementation" and not output["files"]:
                raise ModelError(
                    "The implementation contained no files. Add missing details and retry."
                )
            if stage == "implementation":
                files = {file["path"]: file["content"] for file in output["files"]}
                if (
                    not files.get("README.md", "").strip()
                    or not any(
                        files.get(name, "").strip()
                        for name in ("requirements.txt", "pyproject.toml")
                    )
                    or not any(
                        name.endswith(".py") and content.strip() for name, content in files.items()
                    )
                ):
                    raise ModelError(
                        "The code draft is incomplete: README.md, Python source and a dependency "
                        "file are required. Narrow the scope and retry; no artifact was accepted."
                    )
                for name, content in files.items():
                    if name.endswith(".py"):
                        try:
                            ast.parse(content, filename=name)
                        except SyntaxError as exc:
                            raise ModelError(
                                "The generated Python failed syntax validation. "
                                "Retry this step; no code was executed."
                            ) from exc
            if stage != "implementation":
                output["files"] = []
            valid_citations = []
            pages = {
                p["page"]: re.sub(r"\s+", " ", p["text"]).strip() for p in context["source_pages"]
            }
            for citation in output["citations"]:
                quote = re.sub(r"\s+", " ", citation["quote"]).strip()
                if quote in pages.get(citation["page"], ""):
                    valid_citations.append(citation)
            if len(valid_citations) != len(output["citations"]):
                output["warnings"].append(
                    "Some model citations failed exact source matching and were removed."
                )
            output["citations"] = valid_citations
            if not valid_citations:
                output["warnings"].append(
                    "No source quote was verified for this output. Check claims against the paper."
                )
            output["warnings"].append(
                "AI draft based on selected text excerpts; figures and omitted text may be missing."
            )
            failure = ""
        except ModelError as exc:
            output, usage, failure = {}, {}, str(exc)
        except Exception:
            output, usage, failure = (
                {},
                {},
                "The AI step failed validation. No artifact was accepted. "
                "Retry after reviewing the input.",
            )
        with self.lock, Session(self.engine) as session, session.begin():
            run = session.get(AgentRun, run_id)
            rates = run.usage.get("rates")
            if usage and rates:
                usage["estimated_usd"] = (
                    usage.get("prompt_tokens", 0) * rates[0]
                    + usage.get("completion_tokens", 0) * rates[1]
                ) / 1_000_000
            run.usage = {**run.usage, **usage}
            run.output, run.finished_at = output, now()
            project, workspace = self.workspace(session, run.project_id)
            if (
                workspace.active_run != run.id
                or workspace.version != run.workspace_version
                or project.revision != run.project_revision
                or run.status == "cancelled"
            ):
                if run.status != "cancelled":
                    run.status = "superseded"
                return
            workspace.active_run = None
            run.status, run.error = ("failed", failure) if failure else ("completed", "")
            if not failure and stage != "chat":
                workspace.artifacts = {**workspace.artifacts, stage: run.id}

    def cancel(self, project_id, expected):
        with self.lock, Session(self.engine) as session, session.begin():
            _, workspace = self.checked(session, project_id, expected)
            if workspace.active_run:
                run = session.get(AgentRun, workspace.active_run)
                run.status, run.finished_at = "cancelled", now()
                run.error = "Cancelled. A request already sent to Groq may still incur usage."
                workspace.active_run = None
                workspace.version += 1
        return self.snapshot(project_id)

    def export(self, project_id):
        snapshot = self.snapshot(project_id)
        with Session(self.engine) as session:
            project = session.get(Project, project_id)
            contract = session.get(ContractRevision, (project_id, project.revision)).setup
            sources = [
                {
                    "id": source.id,
                    "name": source.name,
                    "digest": source.digest,
                    "pages": source.pages,
                }
                for source in session.scalars(
                    select(PaperSource).where(PaperSource.project_id == project_id)
                )
            ]
        output = io.BytesIO()
        files = snapshot["artifacts"].get("implementation", {}).get("output", {}).get("files", [])
        files = AgentOutput(title="Export", summary="", files=files).files
        report = [
            f"# {contract['name']}",
            "AI-assisted research workspace export.",
            "Generated code has not been executed by PaperLab. Review it before running.",
            "Submitted results are self-reported, not independently verified.",
        ]
        for stage, run in snapshot["artifacts"].items():
            artifact = run["output"]
            report.extend([f"## {stage.title()}", artifact["summary"]])
            for section in artifact.get("sections", []):
                report.extend([f"### {section['heading']}", section["body"]])
            for warning in artifact.get("warnings", []):
                report.append(f"- {warning}")
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}
            },
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# PaperLab export\nReview the generated files before execution. "
                        "This notebook only writes the project into ./paperlab-project. "
                        "Use the generated README for install and run steps. "
                        "No training has been performed. "
                        "Upload this notebook to Colab or Kaggle manually."
                    ],
                },
                {
                    "cell_type": "code",
                    "metadata": {},
                    "execution_count": None,
                    "outputs": [],
                    "source": [
                        "from pathlib import Path\nimport json\n",
                        "files = json.loads("
                        + repr(json.dumps([f.model_dump() for f in files]))
                        + ")\n",
                        "root = Path('paperlab-project')\n",
                        "for item in files:\n"
                        "    path = root / item['path']\n"
                        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
                        "    path.write_text(item['content'], encoding='utf-8')\n",
                        "print('Project files written. Review README before running code.')\n",
                    ],
                },
            ],
        }
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("paperlab/contract.json", json.dumps(contract, indent=2))
            archive.writestr("paperlab/sources.json", json.dumps(sources, indent=2))
            archive.writestr(
                "paperlab/provenance.json", json.dumps(snapshot, indent=2, default=str)
            )
            archive.writestr("paperlab/report.md", "\n\n".join(report))
            archive.writestr("paperlab/notebook.ipynb", json.dumps(notebook, indent=2))
            for file in files:
                archive.writestr("project/" + file.path, file.content)
        return output.getvalue()


def research_router(service):
    router = APIRouter(prefix="/projects/{project_id}/research")

    @router.get("")
    def read(project_id: UUID):
        return service.snapshot(str(project_id))

    @router.post("/source/text")
    def text_source(project_id: UUID, request: TextSource):
        if len(request.text.strip()) < 100:
            raise HTTPException(422, "Paste at least 100 characters of paper text.")
        pages = [{"page": i + 1, "text": text} for i, text in enumerate(request.text.split("\f"))]
        return service.attach(str(project_id), request.expected_version, request.name, pages)

    @router.post("/source/url")
    def url_source(project_id: UUID, request: VersionRequest):
        with Session(service.engine) as session:
            project = session.get(Project, str(project_id))
            if not project:
                raise HTTPException(404, "Project not found")
            url = session.get(ContractRevision, (project.id, project.revision)).setup["paper_url"]
        return service.attach(str(project_id), request.expected_version, url, fetch_pdf(url))

    @router.post("/source/pdf")
    async def pdf_source(project_id: UUID, expected_version: int, file: UploadFile):
        data = await file.read(MAX_BYTES + 1)
        await file.close()
        pages = await run_in_threadpool(pages_from_pdf, data)
        return await run_in_threadpool(
            service.attach, str(project_id), expected_version, file.filename or "paper.pdf", pages
        )

    @router.post("/runs", status_code=202)
    def run(project_id: UUID, request: RunRequest):
        return service.start(str(project_id), request)

    @router.post("/feedback")
    def feedback(project_id: UUID, request: FeedbackRequest):
        return service.feedback(str(project_id), request)

    @router.post("/approve")
    def approve(project_id: UUID, request: ApprovalRequest):
        return service.approve(str(project_id), request)

    @router.post("/cancel")
    def cancel(project_id: UUID, request: VersionRequest):
        return service.cancel(str(project_id), request.expected_version)

    @router.post("/evidence")
    def evidence(project_id: UUID, request: EvidenceRequest):
        return service.evidence(str(project_id), request)

    @router.get("/export")
    def export(project_id: UUID):
        return Response(
            service.export(str(project_id)),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="paperlab-project.zip"'},
        )

    return router
