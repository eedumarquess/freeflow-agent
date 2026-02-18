from __future__ import annotations

import tempfile

import pytest

from featureflow.storage import init_run, read_run


def test_creates_run_directory_and_writes_run_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test_run"
        outputs_dir = tmpdir
        allowed_roots = [tmpdir]

        data = init_run(run_id, {"story": "test"}, outputs_dir, allowed_roots)
        assert data["run_id"] == run_id

        loaded = read_run(run_id, outputs_dir)
        assert loaded["run_id"] == run_id
        assert loaded["inputs"]["story"] == "test"


def test_does_not_overwrite_existing_run() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test_run"
        outputs_dir = tmpdir
        allowed_roots = [tmpdir]

        init_run(run_id, {"story": "test"}, outputs_dir, allowed_roots)
        with pytest.raises(FileExistsError):
            init_run(run_id, {"story": "test"}, outputs_dir, allowed_roots)
