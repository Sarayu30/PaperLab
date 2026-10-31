import re
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Stage = Literal[
    "analysis", "plan", "implementation", "review", "results", "extensions", "report", "chat"
]
PIPELINE = ["analysis", "plan", "implementation", "review", "results", "extensions", "report"]


class Section(BaseModel):
    heading: str = Field(max_length=200)
    body: str = Field(max_length=20000)


class Citation(BaseModel):
    page: int = Field(ge=1)
    quote: str = Field(min_length=8, max_length=500)


class Task(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    title: str = Field(max_length=200)
    description: str = Field(max_length=3000)
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    acceptance: str = Field(max_length=2000)


class GeneratedFile(BaseModel):
    path: str = Field(max_length=200)
    content: str = Field(max_length=90000)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value):
        path = PurePosixPath(value)
        if (
            not re.fullmatch(r"[A-Za-z0-9_./-]+", value)
            or path.is_absolute()
            or any(p in ("", ".", "..") or p.startswith(".") for p in value.split("/"))
            or any(
                p.endswith(".")
                or p.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *[f"COM{i}" for i in range(1, 10)],
                    *[f"LPT{i}" for i in range(1, 10)],
                }
                for p in value.split("/")
            )
            or path.suffix
            not in {".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".ipynb"}
        ):
            raise ValueError("Generated files must have safe relative project paths")
        return value


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=200)
    summary: str = Field(max_length=6000)
    sections: list[Section] = Field(default_factory=list, max_length=20)
    citations: list[Citation] = Field(default_factory=list, max_length=30)
    tasks: list[Task] = Field(default_factory=list, max_length=30)
    files: list[GeneratedFile] = Field(default_factory=list, max_length=16)
    warnings: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_graph(self):
        tasks = {task.id: task for task in self.tasks}
        if len(tasks) != len(self.tasks):
            raise ValueError("Duplicate task IDs")
        visited, visiting = set(), set()

        def visit(key):
            if key in visiting or key not in tasks:
                raise ValueError("Invalid task dependency graph")
            if key in visited:
                return
            visiting.add(key)
            for dependency in tasks[key].depends_on:
                visit(dependency)
            visiting.remove(key)
            visited.add(key)

        for key in tasks:
            visit(key)
        paths = [file.path.casefold() for file in self.files]
        if len(paths) != len(set(paths)) or sum(len(f.content) for f in self.files) > 300000:
            raise ValueError("Duplicate or oversized generated files")
        return self


class VersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class TextSource(VersionRequest):
    name: str = Field(default="Pasted paper", min_length=1, max_length=200)
    text: str = Field(min_length=100, max_length=200000)


class RunRequest(VersionRequest):
    stage: Stage
    request_id: UUID
    message: str = Field(default="", max_length=5000)


class FeedbackRequest(VersionRequest):
    model_config = ConfigDict(str_strip_whitespace=True)
    stage: Stage
    message: str = Field(min_length=3, max_length=5000)


class ApprovalRequest(VersionRequest):
    plan_id: UUID


class EvidenceRequest(VersionRequest):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    metrics: dict[str, float] = Field(max_length=40)
    hardware: str = Field(min_length=1, max_length=500)
    command: str = Field(min_length=1, max_length=2000)
    notes: str = Field(default="", max_length=10000)

    @field_validator("metrics")
    @classmethod
    def finite_metrics(cls, values):
        import math

        if not values or any(not math.isfinite(v) or len(k) > 100 for k, v in values.items()):
            raise ValueError("Provide finite named metrics")
        return values
