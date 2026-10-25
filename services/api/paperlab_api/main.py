from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import database_url, make_engine
from .models import ContractRevision, Project
from .schemas import ProjectSetup, ProjectView, RevisionRequest, RevisionView


def utc(value: datetime) -> datetime:
    # SQLite does not retain a DateTime column's timezone information.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def view(project: Project, contract: ContractRevision) -> ProjectView:
    return ProjectView(
        id=project.id,
        revision=project.revision,
        setup=contract.setup,
        created_at=utc(project.created_at),
        updated_at=utc(project.updated_at),
    )


def create_app(url: str | None = None) -> FastAPI:
    engine = make_engine(url or database_url())

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(
        title="PaperLab API",
        version="0.1.0",
        description="Local project setup and revision history. Experiments are not executed yet.",
        lifespan=lifespan,
    )
    app.state.engine = engine

    @app.get("/health")
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM projects LIMIT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(
                503, "Database unavailable. Apply migrations before starting."
            ) from exc
        return {"status": "ok", "feature": "project_setup"}

    @app.post("/projects", response_model=ProjectView, status_code=201)
    def create_project(setup: ProjectSetup):
        now = datetime.now(UTC)
        project = Project(id=str(uuid4()), revision=1, created_at=now, updated_at=now)
        contract = ContractRevision(
            project_id=project.id,
            revision=1,
            setup=setup.model_dump(mode="json"),
            note="Project created",
            created_at=now,
        )
        with Session(engine) as session, session.begin():
            session.add(project)
            session.flush()
            session.add(contract)
            result = view(project, contract)
        return result

    @app.get("/projects", response_model=list[ProjectView])
    def list_projects(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        with Session(engine) as session:
            rows = session.execute(
                select(Project, ContractRevision)
                .join(
                    ContractRevision,
                    (ContractRevision.project_id == Project.id)
                    & (ContractRevision.revision == Project.revision),
                )
                .order_by(Project.created_at.desc(), Project.id)
                .offset(offset)
                .limit(limit)
            ).all()
            return [view(project, contract) for project, contract in rows]

    @app.get("/projects/{project_id}", response_model=ProjectView)
    def get_project(project_id: UUID):
        with Session(engine) as session:
            project = session.get(Project, str(project_id))
            if project is None:
                raise HTTPException(404, "Project not found")
            contract = session.get(ContractRevision, (project.id, project.revision))
            return view(project, contract)

    @app.get("/projects/{project_id}/revisions", response_model=list[RevisionView])
    def list_revisions(project_id: UUID):
        with Session(engine) as session:
            if session.get(Project, str(project_id)) is None:
                raise HTTPException(404, "Project not found")
            contracts = session.scalars(
                select(ContractRevision)
                .where(ContractRevision.project_id == str(project_id))
                .order_by(ContractRevision.revision.desc())
            )
            return [
                RevisionView(
                    revision=c.revision, setup=c.setup, note=c.note, created_at=utc(c.created_at)
                )
                for c in contracts
            ]

    @app.post("/projects/{project_id}/revisions", response_model=ProjectView, status_code=201)
    def revise_project(project_id: UUID, request: RevisionRequest):
        now = datetime.now(UTC)
        next_revision = request.expected_revision + 1
        with Session(engine) as session, session.begin():
            # Compare-and-swap: only one writer can advance this exact revision.
            changed = session.execute(
                update(Project)
                .where(Project.id == str(project_id), Project.revision == request.expected_revision)
                .values(revision=next_revision, updated_at=now)
            )
            if changed.rowcount != 1:
                current = session.get(Project, str(project_id))
                if current is None:
                    raise HTTPException(404, "Project not found")
                raise HTTPException(
                    409,
                    {
                        "message": "This project changed. Reload before saving your revision.",
                        "current_revision": current.revision,
                    },
                )
            previous = session.get(ContractRevision, (str(project_id), request.expected_revision))
            payload = request.setup.model_dump(mode="json")
            if ProjectSetup.model_validate(previous.setup).model_dump(mode="json") == payload:
                raise HTTPException(
                    422, "Change at least one setup field before saving a revision."
                )
            contract = ContractRevision(
                project_id=str(project_id),
                revision=next_revision,
                setup=payload,
                note=request.note,
                created_at=now,
            )
            session.add(contract)
            project = session.get(Project, str(project_id))
            result = view(project, contract)
        return result

    return app
