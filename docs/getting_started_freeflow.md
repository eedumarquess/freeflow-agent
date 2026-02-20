# FREEFLOW / FEATUREFLOW - Getting Started (Kickoff Guide)

## Kickoff Goal (1-2 sessions)

By the end of this, you will have a ready project structure plus a CLI that creates a run ID,
writes initial artifacts, and executes commands via allowlist.

## 1. Create the Repository and Minimum Structure

```text
freeflow/
|-- featureflow/               # Python package
|   |-- __init__.py
|   |-- config.py              # Loads YAML + defaults
|   |-- ids.py                 # Generates run_id
|   |-- storage.py             # Saves/reads runs
|   |-- shell.py               # Executor with allowlist + timeout
|   |-- git_ops.py             # Simple git helpers
|   |-- artifacts.py           # Generates run .md files
|   `-- workflow/              # LangGraph
|-- cli/
|   |-- __init__.py
|   `-- main.py                # CLI entrypoint
|-- web/
|   `-- api.py                 # Minimal FastAPI
|-- outputs/
|   `-- runs/
|-- tests/
|-- featureflow.yaml.example
|-- pyproject.toml
`-- README.md
```

## 2. Setup Toolchain (pip + pyproject)

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# Linux/macOS
# source .venv/bin/activate

python -m pip install -U pip
python -m pip install -e .
```

## 3. Configuration File (YAML)

Create `featureflow.yaml.example` with these fields (minimum viable):

```yaml
project:
  base_branch: "master"
runs:
  outputs_dir: "outputs/runs"
  max_iters: 3
  timeout_seconds: 600
security:
  allowed_commands:
    - ["pytest", "-q"]
    - ["python", "-m", "pytest", "-q"]
    - ["git", "diff"]
    - ["git", "status", "--porcelain"]
  allowed_write_roots:
    - "featureflow"
    - "tests"
    - "web"
    - "cli"
```

## 4. Minimal CLI (Typer)

Use `python -m cli.main <subcommand> [args]`.

### `python -m cli.main init`
- Copies `featureflow.yaml.example` -> `featureflow.yaml` (if it does not exist)
- Creates `outputs/runs/`

### `python -m cli.main run <story>`
- Story is positional (example: `python -m cli.main run "minha historia"`)
- Creates a `run_id`
- Writes inputs to `run.json`
- Generates artifact templates

### `python -m cli.main test <run_id>`
- Runs `pytest` via allowlist
- Saves results to `run-report.md` and `run.json`

## 5. Tests

Run all tests:

```bash
python -m pytest -q
```

## 6. Minimal Web API

Run API locally:

```bash
python -m uvicorn web.api:app --reload
```

## Kickoff Done Checklist

- [x] `python -m cli.main init` works
- [x] `python -m cli.main run` creates run artifacts under `outputs/runs/<id>/`
- [x] `python -m cli.main test` runs `pytest` via allowlist with timeout
- [x] `run.json` records command outputs
- [x] Project `pytest` suite passes
- [x] API lists runs and returns details
