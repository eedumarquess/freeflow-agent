from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    WAITING_APPROVAL_PLAN = "WAITING_APPROVAL_PLAN"
    APPROVED_PLAN = "APPROVED_PLAN"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    WAITING_APPROVAL_PATCH = "WAITING_APPROVAL_PATCH"
    APPROVED_PATCH = "APPROVED_PATCH"
    TESTS_RUNNING = "TESTS_RUNNING"
    TESTS_FAILED = "TESTS_FAILED"
    TESTS_PASSED = "TESTS_PASSED"
    WAITING_APPROVAL_FINAL = "WAITING_APPROVAL_FINAL"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"


VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.PLANNED},
    RunStatus.PLANNED: {RunStatus.WAITING_APPROVAL_PLAN},
    RunStatus.WAITING_APPROVAL_PLAN: {RunStatus.APPROVED_PLAN},
    RunStatus.APPROVED_PLAN: {RunStatus.PATCH_PROPOSED},
    RunStatus.PATCH_PROPOSED: {RunStatus.WAITING_APPROVAL_PATCH},
    RunStatus.WAITING_APPROVAL_PATCH: {RunStatus.APPROVED_PATCH},
    RunStatus.APPROVED_PATCH: {RunStatus.TESTS_RUNNING},
    RunStatus.TESTS_RUNNING: {RunStatus.TESTS_PASSED, RunStatus.TESTS_FAILED},
    RunStatus.TESTS_FAILED: {RunStatus.PATCH_PROPOSED},
    RunStatus.TESTS_PASSED: {RunStatus.WAITING_APPROVAL_FINAL},
    RunStatus.WAITING_APPROVAL_FINAL: {RunStatus.FINALIZED},
    RunStatus.FINALIZED: set(),
    RunStatus.FAILED: set(),
}


def coerce_status(value: str | RunStatus) -> RunStatus:
    if isinstance(value, RunStatus):
        return value
    if isinstance(value, str):
        return RunStatus(value)
    raise TypeError(f"Invalid status type: {type(value).__name__}")


def is_valid_transition(current: RunStatus, next_status: RunStatus) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, set())
