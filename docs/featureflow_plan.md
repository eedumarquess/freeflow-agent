# FEATUREFLOW AGENT — Plan and Documentation (v1)

## Vision

A local agent for Python repositories that helps implement features with quality:

- Understands a story, diff, or branch
- Creates a change contract and test plan
- Modifies code automatically (with step-by-step human approval)
- Runs the full test suite (`pytest`)
- Diagnoses failures and fixes them in a controlled loop
- Analyzes regression risk
- Generates artifacts: `change-request.md`, `test-plan.md`, `run-report.md`, `risk-report.md`, `pr-comment.md`

**Interface:** CLI + Web UI (FastAPI + React)  
**Orchestration:** LangGraph (state + gates + loops)  
**LLM:** OpenAI (Codex for now), pluggable design

---

## MVP Objectives (must exist)

1. A functional CLI to run a "run" on your Python repo and produce artifacts.
2. A workflow with gates:
   - Strict command allowlist
   - Human approval before:
     - Applying code changes (or before each change step)
     - Running expensive commands (docker/test)
     - Finalizing the run
3. Test execution: run everything with `pytest` (up to 10 min; timeout + partial report).
4. Automatic fix loop when tests fail (with iteration limit).
5. Clear, traceable reports (run ID, logs, diffs, commands, results).
6. Minimal Web UI for listing and inspecting runs and approving steps.

## Non-Goals (for now)

- Impact-based intelligent test selection (future).
- Full monorepo / multi-project support (future).
- Automatic deploy / CI/CD (out of scope; focus is local).

---

## Supported Inputs

- **Story (text):** describes a feature, bug, or change.
- **Diff:** existing patch (optional).
- **Branch:** comparison against a base branch (e.g., `main`) to generate context and risk.

---

## Outputs (artifacts per run)

Stored in `outputs/runs/<run_id>/`:

| Artifact | Contents |
|---|---|
| `change-request.md` | Objective (1 sentence), scope/out-of-scope, likely files, business rules, done criteria, risks |
| `test-plan.md` | How to validate; existing tests; new tests to be created; fixtures/test data |
| `run-report.md` | Steps executed, decisions made, commands run (allowlist), timing, failures, fixes, final status |
| `risk-report.md` | Impacted areas (modules/folders), regression surface, scenarios, extra test recommendations |
| `pr-comment.md` *(optional)* | Concise summary of what changed, how to test, and risks |

---

## Architecture (High Level)

### Components

1. **Orchestrator (LangGraph)** — Nodes and conditional edges; maintains a single shared state.
2. **Tools (agent tools)**
   - *FS tool:* controlled read/write with path filters
   - *Git tool:* status, diff, branch compare, commit
   - *Shell tool:* allowlist executor with timeout
3. **Run persistence** — JSON or SQLite + `outputs/` directory with logs and artifacts
4. **Interface**
   - *CLI:* create runs, show status, generate artifacts
   - *Web API (FastAPI):* list runs, return details, receive approvals
   - *React UI:* simple dashboard + detail view + approval buttons

---

## LangGraph Workflow

### State (example fields)

```python
run_id: str
repo_path: str
inputs: { story, diff_path, branch, base_branch }
plan: { change_request_md, test_plan_md }
context: { repo_tree, key_files, constraints, current_diff }
edits: { proposed_steps, applied_commits, patches }
tests: { commands, results, duration, failures }
risk: { impacted_paths, notes, suggested_tests }
approvals: { pending_step, approved: bool, approvals_log }
limits: { max_iters, max_files_changed, max_diff_lines, max_runtime_sec }
status: { stage, ok, message }
```

### Nodes (MVP)

| # | Node | Description |
|---|---|---|
| 1 | `LOAD_CONTEXT` | Reads repo structure; detects configs (`pyproject`, `setup.cfg`, `requirements`); detects test setup (`pytest.ini`); reads relevant files |
| 2 | `PLAN` | Generates `change-request.md` + `test-plan.md` based on story/diff/branch |
| 3 | `PROPOSE_CHANGES` | Generates small change steps: list of files and intent |
| 4 | `AWAIT_APPROVAL` *(gate)* | Pauses until human approves the next step |
| 5 | `APPLY_CHANGES` | Edits files (small changes) + commits to branch `agent/<run_id>` |
| 6 | `RUN_TESTS` *(gate)* | Executes allowlisted commands (`pytest`, `docker compose`) with timeout |
| 7 | `DIAGNOSE` | Interprets failures; decides whether to fix code or adjust tests |
| 8 | `FIX_LOOP` | Returns to `PROPOSE_CHANGES` / `APPLY_CHANGES` until tests pass, `max_iters` is exceeded, or `max_runtime` is hit |
| 9 | `REGRESSION_RISK` | Analyzes risk based on diff: touched areas, likely dependencies, break scenarios |
| 10 | `REVIEW` | Checks scope adherence, test quality, minimal style compliance |
| 11 | `FINALIZE` | Generates `run-report.md`, `risk-report.md`, `pr-comment.md`; marks final status |

---

## Security Rules and Controls

### Command Allowlist (initial)

```
pytest -q
pytest
python -m pytest
docker compose up -d
docker compose down
# optional: ruff check . / mypy .
```

### Blocks

- No deploy, migrations, external `curl` calls, `rm -rf`, etc.
- Write paths restricted to the repo and defined folders.

### Human Approval Required Before

- `APPLY_CHANGES`
- `RUN_TESTS` (when docker/pytest may take a long time)
- `FINALIZE`

### Limits

- Max runtime: ~10 minutes
- `max_iters`: 3–5
- `max_files_changed` and `max_diff_lines` per iteration

---

## Technologies

**Backend (agent + API):**
- Python 3.11+
- `langchain` + `langgraph`
- `FastAPI` + `Uvicorn`
- SQLite (or JSON) for run history
- Git CLI + `pytest`

**Frontend:**
- React (Vite) — REST calls to FastAPI

---

## Suggested Directory Structure

```
featureflow/
├── app/
│   ├── main.py            # CLI entry
│   ├── graph.py           # LangGraph graph builder
│   ├── state.py           # State models (Pydantic)
│   ├── config.py          # YAML loader + defaults
│   ├── approvals.py       # Approval gates + persistence
│   └── tools/
│       ├── fs_tool.py     # Read/write with path filters
│       ├── git_tool.py    # git status/diff/checkout/commit
│       └── shell_tool.py  # Allowlist executor + timeout
│   └── prompts/
│       ├── planner.md
│       ├── proposer.md
│       ├── implementer.md
│       ├── diagnoser.md
│       ├── reviewer.md
│       └── risk_analyst.md
├── server/
│   ├── api.py             # FastAPI routes (runs, approvals)
│   └── db.py              # SQLite repo
├── ui/                    # React app
├── outputs/
│   └── runs/<run_id>/
├── config/
│   └── featureflow.yaml
└── README.md
```

---

## Config (`featureflow.yaml`) — Example

```yaml
repo_path: "/path/to/repo"
base_branch: "main"
allowlist:
  - "pytest"
  - "python -m pytest"
  - "docker compose up -d"
  - "docker compose down"
limits:
  max_runtime_sec: 600
  max_iters: 4
  max_files_changed: 8
  max_diff_lines: 400
approvals:
  require_for_apply: true
  require_for_tests: true
  require_for_finalize: true
```

---

## CLI Commands

```bash
# Create and run a run
featureflow run --story "..." [--branch feature/x] [--diff path.patch]

# Show run status
featureflow status <run_id>

# Approve a step
featureflow approve <run_id> --step APPLY_CHANGES
featureflow approve <run_id> --step RUN_TESTS

# Start the web UI
featureflow serve   # starts FastAPI + React
```

---

## API Endpoints (FastAPI — Minimal)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/runs` | List all runs |
| `GET` | `/runs/{run_id}` | Get run details |
| `POST` | `/runs/{run_id}/approve` | Approve/reject a step (`step`, `approved`, `note`) |
| `GET` | `/runs/{run_id}/artifacts/{name}` | Download an artifact |

---

## Implementation Roadmap (MVP)

### Phase 0 — Bootstrap *(1 day)*
- Create repo structure, YAML config, `outputs/runs/`
- Implement `fs_tool` (read/write + path filter)
- Implement `shell_tool` (allowlist + timeout)
- Implement `git_tool` (status/diff/branch compare/commit)

### Phase 1 — CLI + Run Engine *(1–2 days)*
- CLI with `click`/`typer`
- `run_id` creation + persistence (JSON or SQLite)
- Dry pipeline: `LOAD_CONTEXT` → `PLAN` → `FINALIZE` (no code edits yet)

### Phase 2 — Full LangGraph *(2–4 days)*
- Build Pydantic state
- Implement nodes: `PROPOSE_CHANGES`, `AWAIT_APPROVAL`, `APPLY_CHANGES`, `RUN_TESTS`, `DIAGNOSE`, `FIX_LOOP`
- Enforce limits (iters/runtime) and per-step logs

### Phase 3 — Artifacts and Quality *(1–2 days)*
- Markdown templates (change-request, test-plan, run-report, risk-report)
- Capture stdout/stderr and attach to run-report
- "Small diff" and "scope" enforcement rules

### Phase 4 — Web API + React UI *(2–5 days)*
- FastAPI: list runs, view details, approve steps, download artifacts
- React: dashboard + detail view + approval buttons + markdown/diff viewer
- *(Optional)* display graph as step status

### Phase 5 — Telemetry *(1–2 days)*
- Per-run metrics: duration per node, loop count, failures
- Local export: JSON + UI view

---

## MVP Done Criteria

Running `featureflow run --story ...` on a real Python repo:
- Generates `change-request.md` and `test-plan.md`
- Proposes changes, waits for approval, applies changes
- Runs `pytest`, fixes if it fails (up to the limit)
- Finalizes with `run-report.md` and `risk-report.md`

Hard requirements:
- Never executes a command outside the allowlist
- Never writes outside permitted paths
- UI allows approving/rejecting steps and viewing run history

---

## Extensions (post-MVP)

- **Impact-based test selection** — dependency map + coverage
- **GitHub PR integration** — auto-create branch/PR + comment
- **Quality plugins** — `ruff`, `mypy`
- **Cheap/premium mode** — fewer/more LLM calls
