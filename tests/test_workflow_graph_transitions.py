from __future__ import annotations

from featureflow.storage import (
    STATUS_APPROVED_PATCH,
    STATUS_APPROVED_PLAN,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_FINALIZED,
    STATUS_PATCH_PROPOSED,
    STATUS_TESTS_FAILED,
    STATUS_TESTS_PASSED,
    STATUS_TESTS_RUNNING,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
)
from featureflow.workflow.graph import (
    END,
    route_after_await,
    route_after_fix_loop,
    route_after_tests,
    route_from_status,
)


def test_route_from_status_maps_core_states() -> None:
    assert route_from_status({"status": STATUS_CREATED}) == "LOAD_CONTEXT"
    assert route_from_status({"status": STATUS_APPROVED_PLAN}) == "PROPOSE_CHANGES"
    assert route_from_status({"status": STATUS_APPROVED_PATCH}) == "APPLY_CHANGES"
    assert route_from_status({"status": STATUS_TESTS_RUNNING}) == "RUN_TESTS"
    assert route_from_status({"status": STATUS_TESTS_FAILED}) == "DIAGNOSE"
    assert route_from_status({"status": STATUS_TESTS_PASSED}) == "REGRESSION_RISK"
    assert route_from_status({"status": STATUS_FINALIZED}) == "FINALIZE"
    assert route_from_status({"status": STATUS_FAILED}) == END


def test_route_after_await_respects_pause_points() -> None:
    assert route_after_await({"status": STATUS_WAITING_APPROVAL_PLAN}) == END
    assert route_after_await({"status": STATUS_WAITING_APPROVAL_PATCH}) == END
    assert route_after_await({"status": STATUS_WAITING_APPROVAL_FINAL}) == END
    assert route_after_await({"status": STATUS_APPROVED_PLAN}) == "PROPOSE_CHANGES"
    assert route_after_await({"status": STATUS_APPROVED_PATCH}) == "APPLY_CHANGES"


def test_route_after_tests_and_fix_loop() -> None:
    assert route_after_tests({"status": STATUS_TESTS_PASSED}) == "REGRESSION_RISK"
    assert route_after_tests({"status": STATUS_TESTS_FAILED}) == "DIAGNOSE"
    assert route_after_tests({"status": STATUS_PATCH_PROPOSED}) == END

    assert route_after_fix_loop({"status": STATUS_PATCH_PROPOSED}) == "PROPOSE_CHANGES"
    assert route_after_fix_loop({"status": STATUS_FAILED}) == END
