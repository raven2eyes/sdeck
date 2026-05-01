# Contributing to SDeck

Thank you for your interest in contributing to SDeck!

## Development Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/raven2eyes/sdeck.git
   cd sdeck
   ```

2. **Install dependencies** (requires Python 3.11+ and [uv](https://docs.astral.sh/uv/))
   ```bash
   uv sync --extra dev
   ```

3. **System dependencies**
   - macOS: `brew install cairo hidapi`
   - Linux: `apt install libcairo2-dev libhidapi-dev libusb-1.0-0`

4. **Environment** — copy `.env.example` to `.env` and fill in `HA_URL` and `HA_TOKEN`

## Branch Naming

Use prefixed branches:
- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `chore/short-description` — maintenance, deps, tooling
- `refactor/short-description` — code restructuring
- `test/short-description` — test additions/fixes
- `docs/short-description` — documentation only

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add light controller dimming support
fix: handle HA disconnect in audio controller
chore: update DeckUI dependency
test: add provisioner profile merge tests
refactor: extract template loading into separate module
```

## Pull Request Process

1. Create a branch from `main` using the naming convention above
2. Make your changes — keep PRs focused on a single concern
3. Ensure all quality gates pass:
   ```bash
   make ci   # or: ruff check . && mypy src && pytest
   ```
4. Fill out the PR template completely
5. Request review — Ralph (QA agent) will auto-review for quality gates

## Agent Workflow

SDeck uses a multi-agent development workflow:
- **Conductor** orchestrates and delegates tasks
- **Engineer** implements features and fixes
- **DevOps** handles infrastructure and CI/CD
- **Ralph** reviews all output for quality and correctness

When contributing, you don't need to use agents — but PRs will be reviewed against the same quality standards.

## Quality Gates

All PRs must pass:
- `ruff check .` — lint clean
- `mypy src` — type check clean (strict mode)
- `pytest --cov=sdeck --cov-fail-under=80` — tests pass with 80% coverage

## Code Style

- Python 3.11+ with `from __future__ import annotations`
- Ruff: line length 100, target py311
- Structured logging only — never `print()`
- Async-native I/O — no blocking calls in async code paths
- Pydantic v2 for all data models
