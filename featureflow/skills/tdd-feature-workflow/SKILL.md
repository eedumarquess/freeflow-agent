---
name: tdd-feature-workflow
description: Enforce test-driven development for new feature implementation in this repository. Use when implementing or extending product behavior so the agent writes failing tests first, then code, then refactors with tests green.
---

# TDD Feature Workflow

Follow this workflow for every new feature request.

## 1) Define scope and target behavior

- Confirm the feature boundary and acceptance criteria.
- Identify where behavior should be tested first (`tests/` backend, `ui/` tests for frontend behavior).
- List modules involved, affected flow, central files, and test commands before proposing a patch.

## 2) RED: write failing tests first

- Add or update tests that describe the requested behavior before any production code change.
- Run targeted tests and confirm failure is caused by missing feature behavior.
- Keep failure evidence concise for `run-report.md` (command + failing assertion summary).

Do not edit production code before a meaningful failing test exists.

## 3) GREEN: implement minimum code

- Change only the smallest set of production files needed to satisfy the new tests.
- Prefer simple, explicit logic over speculative abstractions.
- Re-run targeted tests until they pass.

## 4) REFACTOR: improve safely

- Refactor only with all tests green.
- Preserve behavior and avoid out-of-scope cleanup.
- Re-run targeted tests and then broader suite (`python -m pytest -q` or project script).

## 5) Record evidence in run artifacts

- Update `test-plan.md` with the tests created/updated for the feature.
- Update `run-report.md` with RED -> GREEN progression and commands executed.
- If TDD cannot be applied, document reason and mitigation in `risk-report.md` before production edits.
