from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_request_md: str = Field(min_length=1)
    test_plan_md: str = Field(min_length=1)


class ProposedStepOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    file: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ProposerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ProposedStepOutput] = Field(default_factory=list)
