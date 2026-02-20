from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from featureflow.storage import (
    STATUS_APPROVED_PATCH,
    STATUS_APPROVED_PLAN,
    STATUS_CREATED,
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
)

from .nodes import NodeContext, get_node_handlers

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - covered by fallback tests
    END = "__END__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


NODE_NAMES = (
    "LOAD_CONTEXT",
    "PLAN",
    "PROPOSE_CHANGES",
    "AWAIT_APPROVAL",
    "APPLY_CHANGES",
    "RUN_TESTS",
    "DIAGNOSE",
    "FIX_LOOP",
    "REGRESSION_RISK",
    "REVIEW",
    "FINALIZE",
)


def route_from_status(state: dict[str, Any]) -> str:
    status = str(state.get("status", ""))
    if status in {STATUS_CREATED, STATUS_PLANNED}:
        return "LOAD_CONTEXT"
    if status in {
        STATUS_WAITING_APPROVAL_PLAN,
        STATUS_WAITING_APPROVAL_PATCH,
        STATUS_WAITING_APPROVAL_FINAL,
    }:
        return "AWAIT_APPROVAL"
    if status == STATUS_APPROVED_PLAN:
        return "PROPOSE_CHANGES"
    if status == STATUS_PATCH_PROPOSED:
        return "AWAIT_APPROVAL"
    if status == STATUS_APPROVED_PATCH:
        return "APPLY_CHANGES"
    if status == STATUS_TESTS_RUNNING:
        return "RUN_TESTS"
    if status == STATUS_TESTS_FAILED:
        return "DIAGNOSE"
    if status == STATUS_TESTS_PASSED:
        return "REGRESSION_RISK"
    if status == STATUS_FINALIZED:
        return "FINALIZE"
    if status == STATUS_FAILED:
        return END
    return END


def route_after_await(state: dict[str, Any]) -> str:
    status = str(state.get("status", ""))
    if status in {
        STATUS_WAITING_APPROVAL_PLAN,
        STATUS_WAITING_APPROVAL_PATCH,
        STATUS_WAITING_APPROVAL_FINAL,
    }:
        return END
    if status == STATUS_APPROVED_PLAN:
        return "PROPOSE_CHANGES"
    if status == STATUS_APPROVED_PATCH:
        return "APPLY_CHANGES"
    if status == STATUS_FINALIZED:
        return "FINALIZE"
    return END


def route_after_tests(state: dict[str, Any]) -> str:
    status = str(state.get("status", ""))
    if status == STATUS_TESTS_PASSED:
        return "REGRESSION_RISK"
    if status == STATUS_TESTS_FAILED:
        return "DIAGNOSE"
    return END


def route_after_fix_loop(state: dict[str, Any]) -> str:
    status = str(state.get("status", ""))
    if status == STATUS_PATCH_PROPOSED:
        return "PROPOSE_CHANGES"
    if status == STATUS_FAILED:
        return END
    return END


@dataclass
class _FallbackCompiledGraph:
    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]

    def invoke(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        state = dict(initial_state)
        step = route_from_status(state)
        hop_count = 0
        while step != END:
            hop_count += 1
            if hop_count > 100:
                state["status"] = STATUS_FAILED
                state.setdefault("status_meta", {})
                state["status_meta"]["message"] = "Workflow exceeded max graph hops."
                return state
            state = self.handlers[step](state)
            if step == "LOAD_CONTEXT":
                step = "PLAN"
            elif step == "PLAN":
                step = "AWAIT_APPROVAL"
            elif step == "PROPOSE_CHANGES":
                step = "AWAIT_APPROVAL"
            elif step == "AWAIT_APPROVAL":
                step = route_after_await(state)
            elif step == "APPLY_CHANGES":
                step = "RUN_TESTS"
            elif step == "RUN_TESTS":
                step = route_after_tests(state)
            elif step == "DIAGNOSE":
                step = "FIX_LOOP"
            elif step == "FIX_LOOP":
                step = route_after_fix_loop(state)
            elif step == "REGRESSION_RISK":
                step = "REVIEW"
            elif step == "REVIEW":
                step = "AWAIT_APPROVAL"
            elif step == "FINALIZE":
                step = END
            else:
                step = END
        return state


def build_graph(ctx: NodeContext) -> Any:
    handlers = get_node_handlers(ctx)
    if not LANGGRAPH_AVAILABLE:
        return _FallbackCompiledGraph(handlers)

    builder = StateGraph(dict)
    builder.add_node("ROUTER", lambda state: state)
    for node_name in NODE_NAMES:
        builder.add_node(node_name, handlers[node_name])

    builder.set_entry_point("ROUTER")
    builder.add_conditional_edges("ROUTER", route_from_status)
    builder.add_edge("LOAD_CONTEXT", "PLAN")
    builder.add_edge("PLAN", "AWAIT_APPROVAL")
    builder.add_edge("PROPOSE_CHANGES", "AWAIT_APPROVAL")
    builder.add_edge("APPLY_CHANGES", "RUN_TESTS")
    builder.add_conditional_edges("RUN_TESTS", route_after_tests)
    builder.add_edge("DIAGNOSE", "FIX_LOOP")
    builder.add_conditional_edges("FIX_LOOP", route_after_fix_loop)
    builder.add_edge("REGRESSION_RISK", "REVIEW")
    builder.add_edge("REVIEW", "AWAIT_APPROVAL")
    builder.add_conditional_edges("AWAIT_APPROVAL", route_after_await)
    builder.add_edge("FINALIZE", END)
    return builder.compile()
