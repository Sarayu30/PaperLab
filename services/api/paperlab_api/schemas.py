from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ReproductionMode(StrEnum):
    RUN = "run"
    RETRAIN = "retrain"
    REIMPLEMENT = "reimplement"


class ControlMode(StrEnum):
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"


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
    max_gpu_hours: float = Field(ge=0, le=10000)
    max_llm_cost_usd: float = Field(ge=0, le=100000)
    hardware: ShortText = "To be confirmed"


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
