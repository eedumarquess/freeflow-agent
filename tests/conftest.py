from __future__ import annotations

import pytest

import featureflow.fs_ops as fs_ops


@pytest.fixture(autouse=True)
def _reset_fs_ops_run_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs_ops, "_RUN_LOGGING", None, raising=False)

