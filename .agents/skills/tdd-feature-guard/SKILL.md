---
name: tdd-feature-guard
description: Enforce strict Test-Driven Development with a Red-Green-Refactor cycle before implementing any new feature behavior. Auto-triggers when implementing features or adding new behavior. Prefer this workflow whenever possible; if it cannot be followed, require explicit risk documentation.
---

# TDD Feature Guard

This skill is **repository-general**: it guides any modification agent on any feature that improves the health of the repository. All conventions (artifacts, write roots, test commands, gates) come from **AGENTS.md at the repository root** — read it when applying this skill.

Use this skill whenever the task introduces new behavior in the system.
This guard orchestrates mandatory delegation to three subagents:
- `tdd-test-writer` for RED
- `tdd-implementer` for GREEN
- `tdd-refactorer` for REFACTOR

## Trigger Scope

Apply this skill by default for:
- New features
- New endpoints/use-cases
- New domain behavior
- Any request to implement, add feature, build, create functionality, or add new behavior

Usually do not apply to:
- Pure bug fixes that only restore intended behavior
- Documentation-only changes
- Pure configuration or infra tweaks without behavior change

If there is uncertainty, apply TDD.

## Mandatory Workflow

Every new feature MUST follow this strict 3-phase cycle. Do NOT skip phases.
Each phase must be completed by its designated subagent before moving forward.

Subagents must **respect allowed write roots and allowlisted commands** (see AGENTS.md). Do not assume a single test runner — the **scope** of the change (backend vs frontend) determines which test command to use (e.g. `npm run test:backend`, `npm run test:frontend`, or `npm test` per AGENTS.md / package.json).

### Phase 1: RED - Write Failing Test

Delegate to `tdd-test-writer` with:
- Feature requirement from user request
- Expected behavior to test

The subagent must return:
- Test file path
- Failure output confirming test fails
- Summary of what the test verifies

Do NOT proceed to GREEN until test failure is confirmed.

### Phase 2: GREEN - Make It Pass

Delegate to `tdd-implementer` with:
- Test file path from RED
- Feature requirement context

The subagent must return:
- Files modified
- Success output confirming test passes
- Implementation summary

Do NOT proceed to REFACTOR until test passes.

### Phase 3: REFACTOR - Improve

Delegate to `tdd-refactorer` with:
- Test file path
- Implementation files from GREEN

The subagent must return either:
- Changes made plus test success output, OR
- "No refactoring needed" with reasoning

Cycle is complete when REFACTOR returns.

## Evidence and Run Artifacts

For each feature cycle, record:
- RED evidence: test path and failing command/output summary
- GREEN evidence: implementation files and passing command/output summary
- REFACTOR evidence: changes made (or justification for no refactor) and final test status

When this repository uses run artifacts, update:
- `test-plan.md`
- `run-report.md`
- `risk-report.md` (mandatory if TDD could not be followed)

## Violation Rules

Never:
- Write production implementation before creating the failing test
- Move to GREEN without confirming RED failure
- Skip REFACTOR evaluation
- Start a new feature cycle before finishing the current cycle

If TDD is not feasible, stop and document the rationale and risk before production edits.
