import math
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ReproductionMode(StrEnum):
    RUN = "run"
    RETRAIN = "retrain"
    REIMPLEMENT = "reimplement"


class ControlMode(StrEnum):
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"


ResourceKind = Literal[
    "cpu_cores",
    "ram_gb",
    "storage_gb",
    "vram_gb",
    "gpu_hours",
    "wall_hours",
    "experiment_budget",
    "assistant_budget",
    "requests_per_minute",
    "tokens_per_minute",
    "hardware",
    "software",
    "data_access",
    "network",
    "custom",
]
TEXT_RESOURCES = {"hardware", "software", "data_access", "network", "custom"}
COUNT_RESOURCES = {"cpu_cores", "requests_per_minute", "tokens_per_minute"}


class ResourceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    kind: ResourceKind
    label: ShortText
    value: (
        Annotated[float, Field(strict=True)]
        | Annotated[str, StringConstraints(max_length=1000)]
        | None
    ) = None

    @model_validator(mode="after")
    def valid_value(self):
        if self.value is None:
            return self
        if self.kind in TEXT_RESOURCES:
            if not isinstance(self.value, str) or not self.value:
                raise ValueError("Use nonempty text, or null when this requirement is unknown")
        else:
            if (
                not isinstance(self.value, (int, float))
                or not math.isfinite(self.value)
                or self.value < 0
            ):
                raise ValueError("Use a finite nonnegative number, or null when unknown")
            if self.kind in COUNT_RESOURCES and not float(self.value).is_integer():
                raise ValueError("Counts must be whole numbers")
        return self


class ResourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workload: Literal["undecided", "cpu", "training", "inference", "api", "simulation", "other"] = (
        "undecided"
    )
    environment: Literal["undecided", "local", "colab", "kaggle", "remote", "other"] = "undecided"
    requirements: list[ResourceRequirement] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_requirements(self):
        keys = [
            r.kind if r.kind != "custom" else f"custom:{r.label.casefold()}"
            for r in self.requirements
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Each resource kind and custom label must be unique")
        return self


class ProjectSetup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    paper_url: HttpUrl = Field(max_length=2048)
    target_result: Annotated[str, StringConstraints(min_length=3, max_length=1000)]
    dataset: ShortText
    metric: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    reproduction_mode: ReproductionMode = ReproductionMode.REIMPLEMENT
    control_mode: ControlMode = ControlMode.GUIDED
    learning_mode: bool = True
    # Retained for compatibility with the first API and its stored revisions.
    max_gpu_hours: float | None = Field(default=None, ge=0, le=10000, deprecated=True)
    max_llm_cost_usd: float | None = Field(default=None, ge=0, le=100000, deprecated=True)
    hardware: ShortText | None = Field(default=None, deprecated=True)
    resource_plan: ResourcePlan = Field(default_factory=ResourcePlan)

    @model_validator(mode="before")
    @classmethod
    def read_legacy_resources(cls, value):
        if not isinstance(value, dict) or "resource_plan" in value:
            return value
        value = dict(value)
        requirements = []
        for old, kind, label in [
            ("max_gpu_hours", "gpu_hours", "GPU time ceiling"),
            ("max_llm_cost_usd", "assistant_budget", "PaperLab assistant budget"),
            ("hardware", "hardware", "Hardware details"),
        ]:
            if value.get(old) is not None:
                requirements.append({"kind": kind, "label": label, "value": value[old]})
        value["resource_plan"] = {"requirements": requirements}
        return value


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    setup: ProjectSetup
    note: Annotated[str, StringConstraints(min_length=3, max_length=2000)]


class ProjectView(BaseModel):
    id: str
    revision: int
    status: Literal["draft"] = "draft"
    setup: ProjectSetup
    created_at: datetime
    updated_at: datetime


class RevisionView(BaseModel):
    revision: int
    setup: ProjectSetup
    note: str
    created_at: datetime
