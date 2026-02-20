from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], repo_path: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or "").strip() or f"git {' '.join(args)} failed"
        raise RuntimeError(err)
    return result.stdout


def ensure_agent_branch(run_id: str, repo_path: str | Path) -> str:
    repo = Path(repo_path)
    branch_name = f"agent/{run_id}"
    _run_git(["rev-parse", "--is-inside-work-tree"], repo)

    exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=repo,
        check=False,
    )
    if exists.returncode == 0:
        _run_git(["checkout", branch_name], repo)
        return branch_name

    _run_git(["checkout", "-b", branch_name], repo)
    return branch_name


def get_current_diff(repo_path: str | Path) -> str:
    return _run_git(["diff"], Path(repo_path))


def get_status_porcelain(repo_path: str | Path) -> str:
    return _run_git(["status", "--porcelain"], Path(repo_path))
