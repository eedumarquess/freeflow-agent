from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from featureflow.artifacts import create_run_artifacts
from featureflow.config import get_allowed_write_roots
from featureflow.contracts import validate_change_request
from featureflow.fs_ops import apply_patch, configure_run_logging
from featureflow.git_ops import ensure_agent_branch, get_current_diff, get_status_porcelain
from featureflow.shell import run_command
from featureflow.storage import (
    STATUS_FAILED,
    STATUS_FINALIZED,
    STATUS_PATCH_PROPOSED,
    STATUS_PLANNED,
    STATUS_TESTS_FAILED,
    STATUS_TESTS_PASSED,
    STATUS_TESTS_RUNNING,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
    read_run,
    write_run,
)

from .state import ProposedStep, RunGraphState, build_graph_state, merge_state_into_run_data


@dataclass
class NodeContext:
    cfg: dict[str, Any]
    repo_root: Path
    outputs_dir: str
    allowed_roots: list[str]


def _run_dir(state: RunGraphState) -> Path:
    return Path(state.artifacts.run_report_path).parent


def _append_markdown(path: Path, title: str, body: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    line = f"\n## {title}\n{body.rstrip()}\n"
    path.write_text(existing + line, encoding="utf-8")


def _list_repo_files(root: Path, max_entries: int = 250) -> list[str]:
    items: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".pytest_cache", "__pycache__", ".cursor"}]
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            items.append(rel)
            if len(items) >= max_entries:
                return items
    return items


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_state(data: dict[str, Any], ctx: NodeContext) -> RunGraphState:
    return build_graph_state(data, ctx.cfg, ctx.repo_root, ctx.outputs_dir)


def _persist_state(state: RunGraphState, ctx: NodeContext) -> None:
    run_data = read_run(state.run_id, ctx.outputs_dir)
    merged = merge_state_into_run_data(state, run_data)
    write_run(state.run_id, ctx.outputs_dir, merged, ctx.allowed_roots)


def _sync_commands(state: RunGraphState, ctx: NodeContext) -> None:
    data = read_run(state.run_id, ctx.outputs_dir)
    commands = data.get("commands")
    if isinstance(commands, list):
        state.commands = commands
    approvals = data.get("approvals")
    if isinstance(approvals, list):
        state.approvals.approvals_log = approvals


def load_context_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "LOAD_CONTEXT"
    state.status_meta.stage = "context_loaded"

    key_files = {}
    for name in ("pyproject.toml", "featureflow.yaml", "pytest.ini"):
        content = _read_if_exists(ctx.repo_root / name)
        if content:
            key_files[name] = content[:12000]

    try:
        current_diff = get_current_diff(ctx.repo_root)
    except RuntimeError as exc:
        current_diff = ""
        state.status_meta.message = f"git diff unavailable: {exc}"

    state.context.repo_tree = _list_repo_files(ctx.repo_root)
    state.context.key_files = key_files
    state.context.constraints = {
        "allowed_write_roots": get_allowed_write_roots(ctx.cfg),
        "allowed_commands": ctx.cfg.get("security", {}).get("allowed_commands", []),
    }
    state.context.current_diff = current_diff
    state.status = STATUS_PLANNED
    _append_markdown(Path(state.artifacts.run_report_path), "Node LOAD_CONTEXT", "Context and repository metadata loaded.")
    _persist_state(state, ctx)
    return state.model_dump()


def plan_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "PLAN"
    state.status_meta.stage = "planned"

    create_run_artifacts(state.run_id, ctx.outputs_dir, ctx.allowed_roots)
    run_dir = _run_dir(state)
    change_request_path = run_dir / "change-request.md"
    test_plan_path = run_dir / "test-plan.md"
    state.plan.change_request_md = _read_if_exists(change_request_path)
    state.plan.test_plan_md = _read_if_exists(test_plan_path)

    if state.inputs.story:
        state.plan.done_criteria = [
            "changes aligned with story",
            "pytest executed via allowlist",
        ]
    state.status_meta.message = "Plan artifacts are ready."
    _append_markdown(Path(state.artifacts.run_report_path), "Node PLAN", "Plan artifacts synced into graph state.")
    _persist_state(state, ctx)
    return state.model_dump()


def propose_changes_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "PROPOSE_CHANGES"
    state.status_meta.stage = "changes_proposed"

    proposed: list[ProposedStep] = []
    if state.edits.applied_files:
        for idx, file_path in enumerate(state.edits.applied_files, start=1):
            proposed.append(
                ProposedStep(
                    id=f"manual-{idx}",
                    file=file_path,
                    intent="review-manual-patch",
                    reason="Patch was already applied manually via python -m cli.main apply.",
                )
            )
    else:
        guessed_file = "tests/"
        if state.context.current_diff:
            match = re.search(r"^\+\+\+ b/(.+)$", state.context.current_diff, flags=re.MULTILINE)
            if match:
                guessed_file = match.group(1)
        proposed.append(
            ProposedStep(
                id="step-1",
                file=guessed_file,
                intent="implement-story-change",
                reason="Deterministic MVP proposal derived from current context.",
            )
        )

    state.edits.proposed_steps = proposed
    state.edits.selected_step_id = proposed[0].id
    state.status = STATUS_PATCH_PROPOSED
    _append_markdown(
        Path(state.artifacts.run_report_path),
        "Node PROPOSE_CHANGES",
        "\n".join(f"- `{step.file}`: {step.intent}" for step in proposed),
    )
    _persist_state(state, ctx)
    return state.model_dump()


def await_approval_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "AWAIT_APPROVAL"
    state.status_meta.stage = "await_approval"
    state.approvals.approved = False

    if state.status in {STATUS_PLANNED}:
        state.approvals.pending_gate = "plan"
        state.status = STATUS_WAITING_APPROVAL_PLAN
        state.status_meta.message = "Waiting for PLAN approval."
    elif state.status == STATUS_PATCH_PROPOSED:
        state.approvals.pending_gate = "patch"
        state.status = STATUS_WAITING_APPROVAL_PATCH
        state.status_meta.message = "Waiting for PATCH approval."
    elif state.status in {STATUS_TESTS_PASSED}:
        state.approvals.pending_gate = "final"
        state.status = STATUS_WAITING_APPROVAL_FINAL
        state.status_meta.message = "Waiting for FINAL approval."
    elif state.status == STATUS_WAITING_APPROVAL_PLAN:
        state.approvals.pending_gate = "plan"
    elif state.status == STATUS_WAITING_APPROVAL_PATCH:
        state.approvals.pending_gate = "patch"
    elif state.status == STATUS_WAITING_APPROVAL_FINAL:
        state.approvals.pending_gate = "final"

    _persist_state(state, ctx)
    return state.model_dump()


def apply_changes_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "APPLY_CHANGES"
    state.status_meta.stage = "applying_changes"

    try:
        branch_name = ensure_agent_branch(state.run_id, ctx.repo_root)
        state.edits.branch_name = branch_name
    except RuntimeError as exc:
        state.status = STATUS_FAILED
        state.status_meta.ok = False
        state.status_meta.message = f"Failed to ensure agent branch: {exc}"
        _persist_state(state, ctx)
        return state.model_dump()

    if state.edits.patch_text.strip():
        configure_run_logging(state.run_id, ctx.outputs_dir, allowed_write_roots=ctx.allowed_roots)
        try:
            changed = apply_patch(ctx.repo_root, state.edits.patch_text)
            state.edits.applied_files = changed
        except Exception as exc:
            state.status = STATUS_FAILED
            state.status_meta.ok = False
            state.status_meta.message = f"Patch application failed: {exc}"
            _persist_state(state, ctx)
            return state.model_dump()

    state.status = STATUS_TESTS_RUNNING
    _append_markdown(
        Path(state.artifacts.run_report_path),
        "Node APPLY_CHANGES",
        f"Branch: `{state.edits.branch_name}`\nApplied files: {', '.join(state.edits.applied_files) or '(none)'}",
    )
    _persist_state(state, ctx)
    return state.model_dump()


def run_tests_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "RUN_TESTS"
    state.status_meta.stage = "tests_running"
    state.status = STATUS_TESTS_RUNNING
    _persist_state(state, ctx)

    allowed_commands = ctx.cfg.get("security", {}).get("allowed_commands", [])
    timeout_seconds = int(ctx.cfg.get("runs", {}).get("timeout_seconds", 600))
    # Prefer cross-platform "python -m pytest -q" when allowed (Windows often lacks pytest on PATH)
    pytest_cmd = ["python", "-m", "pytest", "-q"]
    if pytest_cmd not in allowed_commands:
        pytest_cmd = ["pytest", "-q"]
    if pytest_cmd not in allowed_commands:
        pytest_cmd = allowed_commands[0] if allowed_commands else ["pytest", "-q"]
    started = time.time()
    try:
        result = run_command(
            pytest_cmd,
            allowed_commands,
            state.run_id,
            ctx.outputs_dir,
            timeout_seconds,
            cwd=ctx.repo_root,
            allowed_write_roots=ctx.allowed_roots,
        )
    except PermissionError as exc:
        result = {
            "command": pytest_cmd,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Command not allowed: {exc}",
        }
    state.tests.duration_sec = max(0.0, time.time() - started)
    state.tests.last_stdout = str(result.get("stdout", ""))
    state.tests.last_stderr = str(result.get("stderr", ""))
    state.tests.results.append(
        {
            "command": result.get("command", pytest_cmd),
            "exit_code": result.get("exit_code"),
            "stdout": state.tests.last_stdout,
            "stderr": state.tests.last_stderr,
        }
    )
    exit_code = result.get("exit_code")
    state.status = STATUS_TESTS_PASSED if exit_code == 0 else STATUS_TESTS_FAILED
    _sync_commands(state, ctx)

    _append_markdown(
        Path(state.artifacts.run_report_path),
        "Node RUN_TESTS",
        f"Exit code: {exit_code}\nStdout:\n{state.tests.last_stdout}\nStderr:\n{state.tests.last_stderr}",
    )
    _persist_state(state, ctx)
    return state.model_dump()


def diagnose_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "DIAGNOSE"
    state.status_meta.stage = "diagnosed"

    failures: list[str] = []
    for line in state.tests.last_stdout.splitlines():
        if "FAILED" in line or "ERROR" in line:
            failures.append(line.strip())
    if not failures and state.tests.last_stderr:
        failures.append(state.tests.last_stderr.splitlines()[0].strip())
    if not failures:
        failures.append("No explicit pytest failure parsed.")

    state.tests.failures = failures
    state.status_meta.message = "Test failures diagnosed."
    _append_markdown(
        Path(state.artifacts.run_report_path),
        "Node DIAGNOSE",
        "\n".join(f"- {item}" for item in failures),
    )
    _persist_state(state, ctx)
    return state.model_dump()


def fix_loop_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "FIX_LOOP"
    state.status_meta.stage = "fix_loop"

    next_iter = state.loop_iters + 1
    if next_iter > state.limits.max_iters:
        state.status = STATUS_FAILED
        state.status_meta.ok = False
        state.status_meta.message = "Max iterations exceeded"
        run_data = read_run(state.run_id, ctx.outputs_dir)
        run_data["failure_reason"] = "Max iterations exceeded"
        write_run(state.run_id, ctx.outputs_dir, run_data, ctx.allowed_roots)
    else:
        state.loop_iters = next_iter
        state.status = STATUS_PATCH_PROPOSED
        state.status_meta.message = f"Retrying change proposal ({next_iter}/{state.limits.max_iters})."
    _persist_state(state, ctx)
    return state.model_dump()


def regression_risk_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "REGRESSION_RISK"
    state.status_meta.stage = "risk_analysis"

    impacted = list(state.edits.applied_files)
    if not impacted:
        try:
            diff = get_current_diff(ctx.repo_root)
            impacted = re.findall(r"^\+\+\+ b/(.+)$", diff, flags=re.MULTILINE)
        except RuntimeError:
            impacted = []
    impacted = sorted(set(impacted))
    state.risk.impacted_paths = impacted
    if not impacted:
        state.risk.regression_level = "low"
        state.risk.notes = ["No changed paths detected in current diff."]
    elif len(impacted) <= 3:
        state.risk.regression_level = "medium"
        state.risk.notes = ["Small surface changed; verify related modules."]
    else:
        state.risk.regression_level = "high"
        state.risk.notes = ["Multiple files changed; broad regression surface."]
    state.risk.suggested_tests = ["python -m pytest -q"]

    _append_markdown(
        Path(state.artifacts.risk_report_path),
        "Regression Risk",
        "\n".join(
            [
                f"- Level: {state.risk.regression_level}",
                f"- Impacted paths: {', '.join(state.risk.impacted_paths) or '(none)'}",
                f"- Suggested tests: {', '.join(state.risk.suggested_tests)}",
            ]
        ),
    )
    _persist_state(state, ctx)
    return state.model_dump()


def review_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "REVIEW"
    state.status_meta.stage = "review"

    change_request = Path(state.artifacts.change_request_path)
    ok, issues = validate_change_request(change_request)
    state.status = STATUS_TESTS_PASSED
    if not ok:
        state.status_meta.ok = True
        state.status_meta.message = "Review completed with contract warnings."
        notes = [f"Contract warning: {issue}" for issue in issues]
        state.risk.notes = sorted(set([*state.risk.notes, *notes]))
    else:
        state.status_meta.message = "Review passed; waiting for final approval."
    _persist_state(state, ctx)
    return state.model_dump()


def finalize_node(data: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
    state = _load_state(data, ctx)
    state.status_meta.last_node = "FINALIZE"
    state.status_meta.stage = "finalized"
    state.status = STATUS_FINALIZED

    report_lines = [
        f"- Final status: `{state.status}`",
        f"- Loop iterations: `{state.loop_iters}`",
        f"- Applied files: {', '.join(state.edits.applied_files) or '(none)'}",
        f"- Risk level: `{state.risk.regression_level}`",
    ]
    _append_markdown(Path(state.artifacts.run_report_path), "Final Summary", "\n".join(report_lines))

    pr_comment = Path(state.artifacts.pr_comment_path)
    pr_comment.write_text(
        "\n".join(
            [
                "# PR Comment",
                "",
                "## Summary",
                f"- Story: {state.inputs.story or '(not provided)'}",
                f"- Status: {state.status}",
                f"- Changed files: {', '.join(state.edits.applied_files) or '(none)'}",
                "",
                "## Validation",
                f"- Last test result: {'passed' if state.status_meta.ok else 'check run-report.md'}",
                "",
                "## Risk",
                f"- Level: {state.risk.regression_level}",
                f"- Impacted paths: {', '.join(state.risk.impacted_paths) or '(none)'}",
            ]
        ),
        encoding="utf-8",
    )
    _persist_state(state, ctx)
    return state.model_dump()


def get_node_handlers(ctx: NodeContext) -> dict[str, Any]:
    return {
        "LOAD_CONTEXT": lambda data: load_context_node(data, ctx),
        "PLAN": lambda data: plan_node(data, ctx),
        "PROPOSE_CHANGES": lambda data: propose_changes_node(data, ctx),
        "AWAIT_APPROVAL": lambda data: await_approval_node(data, ctx),
        "APPLY_CHANGES": lambda data: apply_changes_node(data, ctx),
        "RUN_TESTS": lambda data: run_tests_node(data, ctx),
        "DIAGNOSE": lambda data: diagnose_node(data, ctx),
        "FIX_LOOP": lambda data: fix_loop_node(data, ctx),
        "REGRESSION_RISK": lambda data: regression_risk_node(data, ctx),
        "REVIEW": lambda data: review_node(data, ctx),
        "FINALIZE": lambda data: finalize_node(data, ctx),
    }


def safe_git_status(repo_root: Path) -> str:
    try:
        return get_status_porcelain(repo_root)
    except RuntimeError:
        return ""
