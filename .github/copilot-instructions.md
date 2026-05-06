# SDeck — Repository-Wide Agent Instructions

## Identity

You are working on **SDeck**, a GitOps-driven provisioning system for Elgato Stream Deck devices
connected to Home Assistant. SDeck is built by **raven2eyes**.

SDeck discovers Stream Deck devices via USB, maps them to YAML profiles (by serial number),
loads `.dui` template packages onto each device, and wires Home Assistant controllers for
interactive control. It runs as a CNF — Docker Desktop for PoC, Talos Kubernetes for production.

**Profile YAML as Source of Truth** — Every device configuration is defined in YAML profiles.
Profiles support inheritance via `extends`, dict-level merging, and Pydantic validation.
No configuration lives outside of profiles and templates.

---

## Core Principles

### Profile-Driven Configuration
- Every device is configured via YAML profiles in `profiles/`
- Profile `extends` does dict-level merge (not slot-level)
- Pydantic validates all profiles at load time — invalid YAML fails fast
- Serial number maps device to profile; `None` key = default fallback

### Async-Native Architecture
- All I/O is asyncio-native — no blocking calls in async code paths
- DeckUI's `DeckManager` handles device discovery and lifecycle
- HaClient provides async REST + WebSocket to Home Assistant
- Controllers must implement async `setup()` and `sync_state()`

### One Pod Per Physical Device
- USB HID is node-local — a Stream Deck can only be accessed from its host
- Each Kubernetes pod manages exactly one physical device
- Node affinity ensures pods schedule where devices are connected
- Profile ConfigMaps and HA Secrets are mounted per pod

### Security by Design
- `.env` with `HA_URL` and `HA_TOKEN` is gitignored — never commit credentials
- Kubernetes Secrets for HA tokens — never ConfigMaps
- No secrets in Dockerfiles, build args, or CI workflow logs
- Container runs as non-root where possible

---

## Architecture Rules

### Python Code (`src/sdeck/`)
- Python 3.11+ with `from __future__ import annotations`
- Pydantic v2 for all data models (profiles, template manifests)
- Ruff: line length 100, target py311, rules E/W/F/I/B/UP/C4/SIM
- mypy strict mode — no untyped defs, no `Any` leaking through public APIs
- Structured logging (never bare `print()`)
- Conventional commits: `feat:`, `fix:`, `chore:`, `test:`, `refactor:`

### Controllers (`src/sdeck/controllers/`)
- Every controller extends `BaseController` (ABC with `setup` + `sync_state`)
- Registered via `@register_controller("name")` decorator
- Must handle HA disconnect gracefully — no unhandled exceptions on reconnect
- Controller name in decorator must match profile YAML `controller` field

### Templates (`templates/`)
- `.dui` packages: `manifest.yaml` + `layout.svg` + optional `assets/`
- Organized by Stream Deck model: `templates/plus/`, `templates/mini/`, etc.
- `load_package()` takes a string path, not a Path object

### Profiles (`profiles/`)
- `defaults.yaml` — base profile inherited by all devices
- `devices/<name>.yaml` — per-device overrides with `extends: defaults`
- DeckModel enum validates model field (plus, mini, neo, xl)
- Template slot indices must match the physical device layout

### Testing
- pytest + pytest-asyncio with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- All hardware mocked — no real Stream Deck or HA connection in tests
- Coverage gate: 80% (`pytest --cov=sdeck --cov-fail-under=80`)
- Test file naming: `test_<module>.py`

### Infrastructure (`deploy/`)
- Docker: `python:3.11-slim` base, system deps: libcairo2-dev, libhidapi-dev, libusb-1.0-0
- Kustomize with base + overlays (dev = Docker Desktop privileged, prod = Talos + smarter-device-manager)
- CI: GitHub Actions → lint, typecheck, test matrix (3.11/3.12/3.13), Docker build → GHCR
- GitOps: ArgoCD syncs from `deploy/k8s/overlays/prod/` to Talos cluster
- Image registry: `ghcr.io/raven2eyes/sdeck`

### Key Dependencies
- **DeckUI** — `DeckManager`, `Screen`, `load_package()`, `.dui` format (git dep from graphras-com)
- **HaClient** — `HAClient.from_url()`, domain accessors `.light()`, `.media_player()` (git dep from graphras-com)
- Both are git-sourced pip deps — do not fork; contribute upstream if changes needed

---

## Documentation Rules
- Update `AGENT-MEMORY.md` with decisions and known gotchas after every significant change
- Keep `AGENTS.md` current with architecture and setup instructions
- Profile schema changes must be reflected in both code and example profiles

### Code-to-Doc Mapping

When code in these areas changes, the corresponding docs **must** be updated in the same PR:

| Code change in | Must update |
|---|---|
| `src/sdeck/controllers/` | `AGENTS.md` (Architecture), `copilot-instructions.md` (Controllers section) |
| `profiles/` | Example profiles in `profiles/`, `copilot-instructions.md` (Profiles section) |
| `templates/` | `AGENTS.md` (Architecture), `README.md` |
| `deploy/` | `AGENTS.md` (Setup/Running), `README.md` |
| `.github/agents/` | `AGENTS.md` (Agent Team Table) |
| `src/sdeck/profile.py` | `copilot-instructions.md` (Profile-Driven Configuration), example profiles |
| `pyproject.toml` (deps) | `AGENTS.md` (Setup), `README.md` (Install) |

## Absolute Rules
1. Never commit credentials (HA tokens, .env files)
2. Never make blocking calls in async code paths
3. Never skip Pydantic validation on profile data
4. Never hardcode device serial numbers outside of profile YAML
5. Never use `print()` — use structured logging
6. Never commit directly to `main` — always use PRs
