# FREEFLOW / FEATUREFLOW — Getting Started (Kickoff Guide)
*Based on "FEATUREFLOW AGENT — Plan and Documentation (v1)"*

## Kickoff Goal (1–2 sessions)

By the end of this, you'll have: a ready project structure + a CLI that creates a run ID, writes initial artifacts, and executes commands via allowlist — no LLM yet.

---

## 1. Create the Repository and Minimum Structure

### 1.1 Folder Layout (create exactly as shown)

```
freeflow/
├── featureflow/               # Python package
│   ├── __init__.py
│   ├── config.py              # Loads YAML + defaults
│   ├── ids.py                 # Generates run_id
│   ├── storage.py             # Saves/reads runs
│   ├── shell.py               # Executor with allowlist + timeout
│   ├── git_ops.py             # Simple git helpers: get diff, current branch
│   ├── artifacts.py           # Generates run .md files
│   └── workflow/              # LangGraph (added later)
├── cli/
│   ├── __init__.py
│   └── main.py                # CLI entrypoint
├── web/
│   └── api.py                 # Minimal FastAPI
├── outputs/
│   └── runs/                  # Each run writes its files here
├── tests/
│   ├── test_shell_allowlist.py
│   └── test_storage_runs.py
├── featureflow.yaml.example
├── pyproject.toml
└── README.md
```

### 1.2 Toolchain: Poetry

Use **Poetry** for dependency management and packaging. The goal is to run `pytest` and package the CLI. This guide uses Poetry commands (`poetry add`, `poetry run pytest`, etc.).

---

## 2. MVP Dependencies (minimal)

Install with Poetry:

```bash
poetry add pyyaml pydantic typer fastapi uvicorn pytest
```

(Use `pydantic-settings` instead of `pydantic` if you prefer. LangGraph comes later, once the core run engine exists.)

---

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

---

## 4. Core Implementations (no LLM yet)

### 4.1 run_id + storage

- **`ids.py`**: `run_id = YYYYMMDD_HHMMSS_<random4>`
- **`storage.py`**:
  - Creates `outputs/runs/<run_id>/`
  - Creates a `run.json` with: status, timestamps, inputs, executed commands, test results

### 4.2 artifacts.py (initial files)

When a run starts, generate:

- `change-request.md` (template)
- `test-plan.md` (template)
- `run-report.md` (filled in progressively)
- `risk-report.md` (placeholder: "not yet calculated")

**Short templates:**

`change-request.md`:
- Objective (1 sentence)
- Scope / Out-of-scope
- Likely files
- Business rules
- Done criteria (includes tests)
- Risks

`test-plan.md`:
- How to validate manually
- Which tests already exist
- Which new tests will be created (if any)

### 4.3 shell.py (real allowlist + timeout)

- Receives a command as a list: `["pytest", "-q"]`
- Checks if it matches an entry in `allowed_commands`
- Executes with timeout (via `subprocess`)
- Captures stdout, stderr, and exit code
- Logs the result to `run.json`

### 4.4 Path filters (safe writes)

Before saving or modifying any file (even artifacts), validate:
- Normalized path
- Root is within `allowed_write_roots`

Set this up now even though writes are currently limited to `outputs/` and project files.

---

## 5. Minimal CLI (Typer)

**MVP commands** (use `ff <subcomando> [argumentos]`; ex.: `ff run "minha story"`, `ff test <run_id>`):

**`ff init`**
- Copies `featureflow.yaml.example` → `featureflow.yaml` (if it doesn't exist)
- Creates `outputs/runs/`

**`ff run <story>`**
- Story é argumento posicional (ex.: `ff run teste` ou `ff run "minha história"`)
- Creates a `run_id`
- Writes inputs to `run.json`
- Generates artifact templates
- Runs `git status` + `git diff` (optional) and saves output to `run-report.md`
- Does **not** modify any code yet

**`ff test <run_id>`**
- Runs `pytest` via allowlist (run_id posicional; ex.: `ff test 20260218_180959_xxxx`)
- Saves results to `run-report.md` and `run.json`

---

## 6. Tests (pytest) to Close the Loop

Create these small unit tests (required at kickoff):

**`test_shell_allowlist.py`**:
- An allowed command executes successfully
- A disallowed command fails with a clear error

**`test_storage_runs.py`**:
- Creates the run directory
- Writes and reads `run.json`
- Does not accidentally overwrite an existing run

---

## 7. Minimal Web UI (API only for now)

`web/api.py`:
- `GET /runs` — lists runs (by reading `outputs/runs/*/run.json`)
- `GET /runs/{run_id}` — returns run details

The React UI comes later. Prove the backend first.

Run with:
```bash
poetry run uvicorn web.api:app --reload
```

---

## 8. Next Step After Kickoff

Once the above is running, add the **LangGraph workflow** with gates:

- Node: `PLAN` — generates improved change-request + test-plan
- Gate: `APPROVE_PLAN`
- Node: `APPLY_CHANGES` — LLM writes the patch
- Gate: `APPROVE_PATCH`
- Node: `RUN_TESTS`
- Loop: `FIX_TESTS` (up to `max_iters`)
- Gate: `APPROVE_FINALIZE`
- Node: `FINALIZE` — run-report + pr-comment

---

## Kickoff Done Checklist

- [x] `ff init` works
- [x] `ff run` creates a run ID and artifacts under `outputs/runs/<id>/`
- [x] `ff test` runs `pytest` via allowlist with timeout
- [x] `run.json` records commands and their outputs  
  **Como verificar:** (1) Rode `ff run teste` (ou `ff run "sua story"`) e anote o `run_id` impresso. (2) Rode `ff test <run_id>`. (3) Abra `outputs/runs/<run_id>/run.json`: o array `commands` deve ter entradas com `command`, `stdout`, `stderr`, `exit_code`, `started_at`, `finished_at` (ex.: `git status`, `git diff`, `pytest -q`). O objeto `test_results` deve ter saída do pytest.
- [x] The project's own `pytest` suite passes
- [x] API lists runs and returns details
