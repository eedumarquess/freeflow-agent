from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from featureflow.storage import (
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_FINALIZED,
    STATUS_PLANNED,
    STATUS_TESTS_FAILED,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
)


class InputsState(BaseModel):
    story: str = ""
    diff_path: str | None = None
    branch: str | None = None
    base_branch: str | None = None


class PlanState(BaseModel):
    change_request_md: str = ""
    test_plan_md: str = ""
    done_criteria: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class ContextState(BaseModel):
    repo_tree: list[str] = Field(default_factory=list)
    repo_files_index: list[str] = Field(default_factory=list)
    tests_summary: str = ""
    highlight_dirs: list[str] = Field(default_factory=list)
    key_files: dict[str, str] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    current_diff: str = ""


class ProposedStep(BaseModel):
    id: str
    file: str
    intent: str
    reason: str


class EditsState(BaseModel):
    proposed_steps: list[ProposedStep] = Field(default_factory=list)
    selected_step_id: str | None = None
    applied_files: list[str] = Field(default_factory=list)
    patch_text: str = ""
    branch_name: str = ""


class TestsState(BaseModel):
    commands: list[list[str]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    duration_sec: float = 0.0
    failures: list[str] = Field(default_factory=list)
    last_stdout: str = ""
    last_stderr: str = ""


class RiskState(BaseModel):
    impacted_paths: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)
    regression_level: str = "unknown"


class ApprovalsState(BaseModel):
    pending_gate: str | None = None
    approved: bool = False
    approvals_log: list[dict[str, Any]] = Field(default_factory=list)


class LimitsState(BaseModel):
    max_iters: int = 3
    max_runtime_sec: int = 600
    max_files_changed: int = 20
    max_diff_lines: int = 800


class StatusMeta(BaseModel):
    stage: str = ""
    ok: bool = True
    message: str = ""
    last_node: str = ""


class ArtifactState(BaseModel):
    change_request_path: str = ""
    test_plan_path: str = ""
    run_report_path: str = ""
    risk_report_path: str = ""
    pr_comment_path: str = ""


class RunGraphState(BaseModel):
    run_id: str
    repo_path: str
    inputs: InputsState = Field(default_factory=InputsState)
    plan: PlanState = Field(default_factory=PlanState)
    context: ContextState = Field(default_factory=ContextState)
    edits: EditsState = Field(default_factory=EditsState)
    tests: TestsState = Field(default_factory=TestsState)
    risk: RiskState = Field(default_factory=RiskState)
    approvals: ApprovalsState = Field(default_factory=ApprovalsState)
    limits: LimitsState = Field(default_factory=LimitsState)
    status: str = STATUS_CREATED
    status_meta: StatusMeta = Field(default_factory=StatusMeta)
    loop_iters: int = 0
    commands: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: ArtifactState = Field(default_factory=ArtifactState)


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _limits_from_cfg(cfg: dict[str, Any]) -> LimitsState:
    runs_cfg = cfg.get("runs", {}) if isinstance(cfg, dict) else {}
    sec_cfg = cfg.get("security", {}) if isinstance(cfg, dict) else {}
    fs_cfg = sec_cfg.get("fs_ops", {}) if isinstance(sec_cfg, dict) else {}
    return LimitsState(
        max_iters=_coerce_int(runs_cfg.get("max_iters"), 3),
        max_runtime_sec=_coerce_int(runs_cfg.get("timeout_seconds"), 600),
        max_files_changed=_coerce_int(fs_cfg.get("max_files_changed"), 20),
        max_diff_lines=_coerce_int(fs_cfg.get("max_diff_lines"), 800),
    )


def _artifact_paths(outputs_dir: str, run_id: str) -> ArtifactState:
    run_dir = Path(outputs_dir) / run_id
    return ArtifactState(
        change_request_path=str(run_dir / "change-request.md"),
        test_plan_path=str(run_dir / "test-plan.md"),
        run_report_path=str(run_dir / "run-report.md"),
        risk_report_path=str(run_dir / "risk-report.md"),
        pr_comment_path=str(run_dir / "pr-comment.md"),
    )


def build_graph_state(
    run_data: dict[str, Any],
    cfg: dict[str, Any],
    repo_path: Path,
    outputs_dir: str,
) -> RunGraphState:
    run_id = str(run_data.get("run_id", ""))
    inputs_raw = run_data.get("inputs") if isinstance(run_data.get("inputs"), dict) else {}
    plan_raw = run_data.get("plan") if isinstance(run_data.get("plan"), dict) else {}
    context_raw = run_data.get("context") if isinstance(run_data.get("context"), dict) else {}
    edits_raw = run_data.get("edits") if isinstance(run_data.get("edits"), dict) else {}
    tests_raw = run_data.get("tests") if isinstance(run_data.get("tests"), dict) else {}
    risk_raw = run_data.get("risk") if isinstance(run_data.get("risk"), dict) else {}
    approvals_raw = run_data.get("approvals_state") if isinstance(run_data.get("approvals_state"), dict) else {}
    status_meta_raw = run_data.get("status_meta") if isinstance(run_data.get("status_meta"), dict) else {}
    artifacts_raw = run_data.get("artifacts") if isinstance(run_data.get("artifacts"), dict) else {}

    approvals_log = run_data.get("approvals")
    if not isinstance(approvals_log, list):
        approvals_log = []

    commands = run_data.get("commands")
    if not isinstance(commands, list):
        commands = []

    loop_iters = _coerce_int(run_data.get("loop_iters"), 0)

    tests = TestsState.model_validate(tests_raw)
    test_results = run_data.get("test_results")
    if isinstance(test_results, dict):
        tests.last_stdout = str(test_results.get("stdout", tests.last_stdout))
        tests.last_stderr = str(test_results.get("stderr", tests.last_stderr))
        if test_results:
            tests.results = [test_results]

    state = RunGraphState(
        run_id=run_id,
        repo_path=str(repo_path),
        inputs=InputsState.model_validate(inputs_raw),
        plan=PlanState.model_validate(plan_raw),
        context=ContextState.model_validate(context_raw),
        edits=EditsState.model_validate(edits_raw),
        tests=tests,
        risk=RiskState.model_validate(risk_raw),
        approvals=ApprovalsState(
            pending_gate=approvals_raw.get("pending_gate"),
            approved=bool(approvals_raw.get("approved", False)),
            approvals_log=approvals_log,
        ),
        limits=_limits_from_cfg(cfg),
        status=str(run_data.get("status", STATUS_CREATED)),
        status_meta=StatusMeta.model_validate(status_meta_raw),
        loop_iters=loop_iters,
        commands=commands,
        artifacts=ArtifactState.model_validate(artifacts_raw) if artifacts_raw else _artifact_paths(outputs_dir, run_id),
    )
    return state


def merge_state_into_run_data(state: RunGraphState, run_data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(run_data)
    merged["status"] = state.status
    merged["loop_iters"] = state.loop_iters
    merged["plan"] = state.plan.model_dump()
    merged["context"] = state.context.model_dump()
    merged["edits"] = state.edits.model_dump()
    merged["tests"] = state.tests.model_dump()
    merged["risk"] = state.risk.model_dump()
    merged["limits"] = state.limits.model_dump()
    merged["status_meta"] = state.status_meta.model_dump()
    merged["approvals_state"] = {
        "pending_gate": state.approvals.pending_gate,
        "approved": state.approvals.approved,
    }
    merged["artifacts"] = state.artifacts.model_dump()

    if state.approvals.approvals_log:
        merged["approvals"] = state.approvals.approvals_log
    if state.commands:
        merged["commands"] = state.commands

    if state.tests.results:
        last_result = state.tests.results[-1]
        merged["test_results"] = {
            "exit_code": last_result.get("exit_code"),
            "stdout": last_result.get("stdout", ""),
            "stderr": last_result.get("stderr", ""),
        }
    elif state.status in {
        STATUS_CREATED,
        STATUS_PLANNED,
        STATUS_WAITING_APPROVAL_PLAN,
        STATUS_WAITING_APPROVAL_PATCH,
        STATUS_WAITING_APPROVAL_FINAL,
        STATUS_FINALIZED,
        STATUS_FAILED,
    }:
        merged.setdefault("test_results", None)

    merged["applied_files"] = state.edits.applied_files
    return merged
