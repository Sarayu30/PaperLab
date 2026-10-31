from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContractRevision(Base):
    __tablename__ = "contract_revisions"

    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperSource(Base):
    __tablename__ = "paper_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    pages: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchWorkspace(Base):
    __tablename__ = "research_workspaces"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    project_revision: Mapped[int] = mapped_column(Integer)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("paper_sources.id"), nullable=True)
    artifacts: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_plan: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_run: Mapped[str | None] = mapped_column(String(36), nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    workspace_version: Mapped[int] = mapped_column(Integer)
    project_revision: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    stage: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    context: Mapped[dict] = mapped_column(JSON)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
