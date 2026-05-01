# SDeck — GitOps Stream Deck Provisioner

## Project overview
GitOps-driven provisioning system for multiple Elgato Stream Deck devices
connected to Home Assistant. Profile-based: YAML profiles map device serial
numbers to template sets (.dui packages) and controller configurations.

## Setup
- Python 3.11, managed with uv
- Install: `uv sync --extra dev`
- Git-sourced dependencies: `deckui` (DeckUI) and `haclient` (HaClient)
- Requires `.env` with `HA_URL`, `HA_TOKEN` (loaded via python-dotenv)
- System deps: `brew install cairo hidapi` (macOS) or `apt install libcairo2-dev libhidapi-dev` (Linux)

## Running
```
uv run sdeck
```
Or directly:
```
uv run python -m sdeck.main
```

## Architecture
- `src/sdeck/main.py` — Entrypoint; multi-device orchestration via DeckManager
- `src/sdeck/provisioner.py` — Reads device profiles, loads .dui packages, wires controllers
- `src/sdeck/profile.py` — Pydantic models for device profiles and template mappings
- `src/sdeck/controllers/` — Home Assistant controller modules (audio, light, timer, dashboard)
- `templates/<model>/` — .dui packages organized by Stream Deck model
- `profiles/` — YAML device provisioning profiles (defaults + per-device overrides)
- `deploy/docker/` — Dockerfile and docker-compose for local dev
- `deploy/k8s/` — Kustomize manifests for Kubernetes deployment (dev + prod overlays)

## Commands
```
ruff check .                              # lint
mypy src                                  # typecheck
pytest                                    # run tests
pytest --cov=sdeck --cov-fail-under=80    # tests with coverage
```

## Conventions
- Ruff: line length 100, target py311
- mypy strict mode
- asyncio_mode = "auto" for pytest
- `.env` is gitignored; never commit credentials
- One pod per physical Stream Deck in Kubernetes
- Profile YAML is the source of truth for device configuration
