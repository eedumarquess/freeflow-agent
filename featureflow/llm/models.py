from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TouchedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ProposedEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    is_new: bool = False


class ExistingTestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    why_relevant: str = Field(min_length=1)


class NewTestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    what_it_validates: str = Field(min_length=1)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    excerpt_or_reason: str = Field(min_length=1)


class PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    touched_files: list[TouchedFile] = Field(default_factory=list)
    proposed_edits: list[ProposedEdit] = Field(default_factory=list)
    existing_tests: list[ExistingTestItem] = Field(default_factory=list)
    new_tests: list[NewTestItem] = Field(default_factory=list)
    commands_to_run: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class RefusalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing: list[str] = Field(default_factory=list)
    inspected_paths: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_request_md: str = Field(min_length=1)
    test_plan_md: str = Field(min_length=1)
    plan: PlanPayload | None = None
    refusal: RefusalPayload | None = None

    @model_validator(mode="after")
    def _validate_plan_xor_refusal(self) -> "PlannerOutput":
        has_plan = self.plan is not None
        has_refusal = self.refusal is not None
        if has_plan == has_refusal:
            raise ValueError("Exactly one of 'plan' or 'refusal' must be provided")
        return self


class ProposedStepOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    file: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ProposerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ProposedStepOutput] = Field(default_factory=list)
