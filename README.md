# Freeflow

A local AI agent designed to help implement features with quality in a Python repository. Freeflow follows a guided workflow that emphasizes productivity and safety through controlled changes, restricted commands, full logging, and human-approval gates.

## Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# Linux/macOS
# source .venv/bin/activate

# Install dependencies
python -m pip install -U pip
python -m pip install -e .
```

## What Freeflow Can Do

### Automated Feature Implementation

Freeflow automates the feature implementation process by:
- Loading repository context (file tree, key files, git diff)
- Generating change requests and test plans
- Proposing implementation steps with reasoning
- Applying changes via unified diff patches
- Running pytest to validate changes
- Diagnosing test failures and retrying (up to configured iterations)
- Analyzing regression risk
- Generating run reports and PR comments

### Guided Workflow with Approval Gates

Three human approval gates ensure safety and control:

| Gate | Purpose |
|------|---------|
| **PLAN** | Approve the change request and test plan before implementation |
| **PATCH** | Approve the actual code changes before applying |
| **FINAL** | Approve finalization after tests pass |

### Security Features

- **Command Allowlist**: Only predefined commands can be executed (e.g., `pytest`, `git diff`, `git status`)
- **Path Restrictions**: File changes restricted to allowed directories (`featureflow/`, `cli/`, `web/`, `tests/`, `outputs/`)
- **Diff Size Limits**: Configurable limits on max diff lines (default 800) and max files changed (default 20)
- **File Size Limits**: Max file size for read/write operations (default 512KB)

### Run Artifacts

Each run generates versioned outputs in `outputs/runs/<run_id>/`:

- `run.json` - Complete run state and metadata
- `change-request.md` - Objective, scope, done criteria
- `test-plan.md` - Testing strategy
- `run-report.md` - Command logs and execution summary
- `risk-report.md` - Regression risk analysis
- `pr-comment.md` - Summary for pull requests

## CLI Commands

```bash
# Initialize project (creates featureflow.yaml and outputs/runs/)
python -m cli.main init

# Start a new run with a story/feature description
python -m cli.main run "your feature description here"

# Approve a pending gate
python -m cli.main approve --run-id <run_id> --gate plan|patch|final

# Advance workflow until pause point or end
python -m cli.main next --run-id <run_id>

# Run tests for a specific run
python -m cli.main test <run_id>

# Validate change request contract
python -m cli.main validate --run-id <run_id>

# Apply a unified diff patch
python -m cli.main apply <run_id> <patch_file>
```

## API

Start the API server:

```bash
python -m uvicorn web.api:app --reload
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/runs` | GET | List all runs |
| `/runs/{run_id}` | GET | Get specific run details |
| `/runs/{run_id}/approve` | POST | Approve/reject a gate |
| `/runs/{run_id}/graph` | GET | Get workflow node statuses |
| `/runs/{run_id}/metrics` | GET | Get run metrics |
| `/runs/{run_id}/artifacts/{name}` | GET | Download artifact files |

## Configuration

Configuration is managed in `featureflow.yaml`:

```yaml
project:
  base_branch: "master"

runs:
  outputs_dir: "outputs/runs"
  max_iters: 3              # Max fix loop iterations
  timeout_seconds: 600     # Command timeout

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

# Optional LLM integration (used in PLAN and PROPOSE_CHANGES only)
llm:
  enabled: true
  provider: "openai"   # openai | anthropic | gemini | ollama
  model: "gpt-4.1-mini"
  api_key: "<your-key>"
  base_url: ""         # Ollama only; default http://localhost:11434
  timeout_seconds: 30
  temperature: 0
  max_repo_tree_entries: 250
  max_diff_chars: 12000
  max_key_file_chars: 6000
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `project.base_branch` | Base branch for git operations | "master" |
| `runs.outputs_dir` | Directory for run outputs | "outputs/runs" |
| `runs.max_iters` | Max fix loop iterations | 3 |
| `runs.timeout_seconds` | Command timeout | 600 |
| `security.allowed_commands` | Whitelist of executable commands | pytest, git |
| `security.allowed_write_roots` | Directories allowed for writes | featureflow, tests, web, cli |
| `llm.enabled` | Enable LLM integration | true |
| `llm.provider` | LLM provider: openai, anthropic, gemini, ollama | openai |
| `llm.model` | Model to use | gpt-4.1-mini |
| `llm.base_url` | Ollama base URL (ignored by other providers) | "" (Ollama: http://localhost:11434) |

**LLM auth / env (per provider):** `openai` → `OPENAI_API_KEY`; `anthropic` → `ANTHROPIC_API_KEY`; `gemini` → `GOOGLE_API_KEY` or `GEMINI_API_KEY`; `ollama` → no key required.

## Tech Stack

### Backend (Python)

- **Language**: Python 3.10+
- **Web Framework**: FastAPI 0.110+
- **CLI**: Typer 0.12+
- **Workflow Engine**: LangGraph 0.2+
- **LLM Integration**: LangChain 0.3+, OpenAI / Anthropic / Gemini / Ollama (LangChain providers)
- **Validation**: Pydantic 2.7+
- **Testing**: Pytest 8.0+

### Frontend (React)

- **Framework**: React 18.3+
- **Build Tool**: Vite 5.4+
- **Language**: TypeScript 5.6+

## Project Structure

```
free-flow-agent/
├── cli/                 # CLI commands (Typer)
├── featureflow/        # Core agent logic
│   ├── workflow/        # LangGraph workflow (nodes, graph, engine, state)
│   ├── llm/            # LLM integration (OpenAI, Anthropic, Gemini, Ollama)
│   ├── prompts/        # LLM prompt templates
│   ├── config.py       # Configuration management
│   ├── storage.py      # Run state persistence
│   ├── shell.py        # Command allowlist executor
│   ├── fs_ops.py       # File operations with security
│   └── artifacts.py    # Run artifact generation
├── web/                # FastAPI backend
│   └── api.py          # REST API endpoints
├── ui/                 # React frontend (Vite)
├── tests/              # pytest test suite
├── outputs/            # Run outputs directory
├── featureflow.yaml    # Main configuration
└── package.json        # NPM scripts for testing/development
```
