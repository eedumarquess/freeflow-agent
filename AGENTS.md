# AGENTS.md â€” Freeflow / Featureflow

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

1. **Understand the goal** â€” story or bug.
2. **Plan before coding** â€” generate or update `change-request.md` and `test-plan.md`.
3. **Keep changes small and reviewable** â€” short diffs, clear commits.
4. **Always test** â€” run `pytest` and fix issues in short cycles.
5. **Record evidence** â€” update `run-report.md` with what changed and why.

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
- `change-request.md` â€” objective, scope/out-of-scope, done criteria
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
- Logging: record important run events â€” commands, stdout/stderr, status, and timing.

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

**Comando facilitador (raiz do repo):** testa e constrÃ³i backend + UI juntos:

```bash
# Testes: backend (pytest) + frontend (Vitest)
npm test

# Build do frontend (backend Ã© Python, sem build)
npm run build
```

Outros scripts na raiz (`package.json`):

```bash
# SÃ³ testes backend
npm run test:backend

# SÃ³ testes frontend (ui/)
npm run test:frontend

# Subir API
npm run dev:api

# Subir UI (Vite)
npm run dev:ui
```

Comandos diretos (quando nÃ£o usar npm na raiz):

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

---

## TDD Skill Policy

For **all new feature work**, use the local orchestrator skill:
- `.agents/skills/tdd-feature-guard/SKILL.md`

Apply this skill **whenever possible**. If the request introduces or extends behavior, default to this skill.
If there is uncertainty, prefer applying TDD rather than skipping it.

Mandatory subagents in order:
1. `tdd-test-writer` (`.agents/skills/tdd-test-writer/SKILL.md`) for `RED`
2. `tdd-implementer` (`.agents/skills/tdd-implementer/SKILL.md`) for `GREEN`
3. `tdd-refactorer` (`.agents/skills/tdd-refactorer/SKILL.md`) for `REFACTOR`

Mandatory rule:
- Write or update a failing test first (`RED`) before editing production code.
- Implement the minimum code to pass (`GREEN`).
- Refactor only after tests pass, keeping tests green (`REFACTOR`).
- Record the red/green/refactor evidence in run artifacts (`test-plan.md` and `run-report.md`).

If a task cannot follow TDD (for example, no testable seam), document the reason explicitly in `risk-report.md` before changing production code.
