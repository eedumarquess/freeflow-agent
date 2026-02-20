# Freeflow

Scaffold for the Freeflow (Featureflow) local agent.

This repository contains the minimum folder structure and Python packaging setup
to start implementing the core workflow.

## Quick start

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# Linux/macOS
# source .venv/bin/activate

python -m pip install -U pip
python -m pip install -e .
```

## CLI

```bash
python -m cli.main --help
python -m cli.main init
python -m cli.main run "minha story"
python -m cli.main test <run_id>
```

## API

```bash
python -m uvicorn web.api:app --reload
```
