"""Persistent sources, workflow state and AI run history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_sources_project_id", "paper_sources", ["project_id"])
    op.create_table(
        "research_workspaces",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("paper_sources.id")),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("approved_plan", sa.String(36)),
        sa.Column("active_run", sa.String(36)),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("workspace_version", sa.Integer(), nullable=False),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), unique=True, nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])


def downgrade():
    op.drop_table("agent_runs")
    op.drop_table("research_workspaces")
    op.drop_table("paper_sources")
