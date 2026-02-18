# AGENTS.md — Freeflow / Featureflow

## What Is This Project

Freeflow (Featureflow) is a local agent designed to help implement features with quality in a Python repository, following a guided workflow:

1. Receives a story (and repo context)
2. Generates a plan and artifacts (e.g., `change-request.md`, `test-plan.md`)
3. Applies changes upon approval
4. Runs tests (`pytest`) in a correction loop until they pass or limits are reached
5. Logs everything in a versioned run under `outputs/runs/<run_id>/`

The focus is on **productivity and safety**: controlled changes, restricted commands, full logs, and human-approval gates.

---

## How to Work in This Repo

### Recommended Mental Model

1. **Understand the goal** — story or bug.
2. **Plan before coding** — generate or update `change-request.md` and `test-plan.md`.
3. **Keep changes small and reviewable** — short diffs, clear commits.
4. **Always test** — run `pytest` and fix issues in short cycles.
5. **Record evidence** — update `run-report.md` with what changed and why.

---

## Security Rules and Best Practices

### 1. Never run commands outside the allowlist
The project uses a shell executor with an allowlist. Do not add powerful commands (e.g., `rm`, `shutdown`, `curl | bash`, `deploy`). Prefer deterministic, local commands such as `pytest`, `git diff`, and `git status`.

### 2. Respect path filters and write roots
File changes must stay within allowed roots: `featureflow/`, `cli/`, `web/`, `tests/`, `outputs/`. Never touch machine configs, files outside the repo, or credentials.

### 3. Keep gates real
When the workflow requires human approval, respect every gate:
- Before `APPLY_CHANGES` (patch)
- Before `RUN_TESTS` (cost/time)
- Before `FINALIZE` (delivery)

Do not skip gates for convenience when implementing something new.

### 4. Always produce clear artifacts per run
Every run must include at minimum:
- `change-request.md` — objective, scope/out-of-scope, done criteria
- `test-plan.md`
- `run-report.md`
- `risk-report.md` (even if just an initial placeholder)

These form the **auditable history** of what was done.

### 5. Make minimal but complete changes
- Prefer small PRs/runs.
- Do not refactor as a side effect unless necessary.
- If a refactor is unavoidable, document it in `change-request.md` as a risk/impact item.

---

## Quality Standards (Python)

- Tests written with `pytest`.
- Avoid heavy dependencies without a clear reason.
- Errors must be explicit with clear messages.
- Logging: record important run events — commands, stdout/stderr, status, and timing.

---

## Project Conventions

| Concern | Location |
|---|---|
| Run outputs | `outputs/runs/<run_id>/` |
| Config | `featureflow.yaml` (base: `featureflow.yaml.example`) |
| CLI | `cli/main.py` |
| Minimal API | `web/api.py` |

---

## Common Commands (Windows)

```bash
# Run tests
python -m pytest -q

# Start API
uvicorn web.api:app --reload

# Check diff / status
git status --porcelain
git diff
```

---

## Pre-Finalization Checklist

- [ ] `change-request.md` is consistent with what was done
- [ ] `test-plan.md` covers minimum validation
- [ ] `pytest` passes
- [ ] `run-report.md` includes: commands run, results, and a diff summary
- [ ] No sensitive or out-of-scope files were touched

---

## Note for Agents / Automation

Before modifying anything, explicitly list:
- Modules involved
- Affected flow
- Central files
- Where tests live and how they are run

Only then propose a patch.