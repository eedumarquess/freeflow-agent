from __future__ import annotations

from pathlib import Path

from featureflow.config import get_allowed_write_roots, get_project_root, load_config
from featureflow.storage import read_run, write_run

from .graph import build_graph
from .nodes import NodeContext
from .state import RunGraphState, build_graph_state, merge_state_into_run_data


def advance_until_pause_or_end(
    run_id: str,
    cfg: dict | None = None,
    root: Path | None = None,
) -> RunGraphState:
    config = cfg or load_config()
    repo_root = root or get_project_root()
    outputs_dir = str(repo_root / config["runs"]["outputs_dir"])
    allowed_roots = get_allowed_write_roots(config)

    run_data = read_run(run_id, outputs_dir)
    state = build_graph_state(run_data, config, repo_root, outputs_dir)

    ctx = NodeContext(
        cfg=config,
        repo_root=repo_root,
        outputs_dir=outputs_dir,
        allowed_roots=allowed_roots,
    )
    graph = build_graph(ctx)
    out = graph.invoke(state.model_dump())
    final_state = RunGraphState.model_validate(out)

    latest = read_run(run_id, outputs_dir)
    merged = merge_state_into_run_data(final_state, latest)
    write_run(run_id, outputs_dir, merged, allowed_roots)
    return final_state
