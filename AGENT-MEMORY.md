# AGENT-MEMORY.md — SDeck Shared Context

Last updated: 2026-05-01

## Project Summary

GitOps-driven provisioning system for multiple Elgato Stream Deck devices
connected to Home Assistant. Profile-based YAML maps device serial numbers to
template sets (.dui packages) and controller configurations. Runs as a CNF —
Docker Desktop for PoC (MacBook USB), Talos K8s for production.

## Agent Team

| Agent     | Prompt                                    | Scope                          |
|-----------|-------------------------------------------|--------------------------------|
| Conductor | `.github/agents/conductor.agent.md`       | Sequencing, backlog, checklist |
| Ralph     | `.github/agents/ralph.agent.md`           | QA, review, quality gates      |
| Engineer  | `.github/agents/engineer.agent.md`        | Python code, tests, templates  |
| DevOps    | `.github/agents/devops.agent.md`          | Docker, K8s, CI, ArgoCD       |

## Decisions Log

| Date       | Decision                                                         | Rationale                                          |
|------------|------------------------------------------------------------------|----------------------------------------------------|
| 2026-05-01 | Python 3.11+ (not Go/Rust)                                      | DeckUI + HaClient are mature Python libs           |
| 2026-05-01 | DeckUI + HaClient as pip deps (not forked)                       | Actively maintained, 95% coverage; fork = burden   |
| 2026-05-01 | One pod per physical Stream Deck in K8s                          | USB HID is node-local, can't share across pods     |
| 2026-05-01 | Kustomize over Helm                                              | Simpler for this scale, overlays suffice           |
| 2026-05-01 | Profile `extends` does dict-level merge, not slot-level          | Pydantic validates after merge; keeps it simple    |
| 2026-05-01 | ArgoCD for GitOps (not Flux)                                     | Common on Talos clusters, better debugging UI      |
| 2026-05-01 | Org: raven2eyes, image: ghcr.io/raven2eyes/sdeck                | User-selected org                                  |

## Known Gotchas

### Python / Dependencies
- `uv sync` installs non-editable; use `uv pip install -e ".[dev]"` for local dev
- `StrEnum` required, not `(str, Enum)` — ruff UP042 enforces this
- pytest-asyncio 1.3.0 with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed

### DeckUI API
- `DeckManager.on_connect()` callback receives `(deck, info: DeviceInfo)`, not just `(deck)`
- `load_package()` takes a string path, not Path object
- `.dui` packages contain: `manifest.yaml` + `layout.svg` + optional `assets/`
- Supported models: Plus, Mini, Neo, XL — capabilities auto-detected from hardware

### HaClient API
- `HAClient.from_url(url, token=token)` — async context manager
- `ha.on_reconnect(coro_fn)` takes a coroutine function, not a regular callback
- Domain accessors: `.light()`, `.media_player()`, `.sensor()`, `.switch()`, etc.
- State object: `entity.state.state` (string), `entity.state.attributes` (dict)

### Container / K8s
- Docker Desktop macOS: USB passthrough requires `--privileged` + `/dev/bus/usb:/dev/bus/usb`
- Talos K8s: smarter-device-manager DaemonSet exposes USB via resource requests
- Container base: `python:3.11-slim` + `libcairo2-dev` + `libhidapi-dev` + `libusb-1.0-0`
- Dev overlay removes smarter-device-manager resource, adds `privileged: true`
- Prod overlay adds `nodeSelector: sdeck.io/usb-device: "true"` + pinned image tag

### CI
- System deps needed on runner for tests: `libcairo2-dev libhidapi-dev`
- Docker build job delegates to Dockerfile — no runner-level hidapi needed
- GHCR login uses `${{ secrets.GITHUB_TOKEN }}` — no additional secrets needed

## Scope Boundaries

### Included
- USB-connected Stream Deck provisioning
- GitOps pipeline (GH Actions → GHCR → ArgoCD → Talos)
- Docker + K8s deployment
- Multi-device profiles with YAML inheritance
- Stream Deck + model (primary), Mini/Neo/XL (template dirs exist, no templates yet)

### Excluded (Future)
- Ethernet/Network Dock transport (needs USB/IP or DeckUI network transport extension)
- Web UI for profile editing
- Automatic device inventory/discovery service
- Template marketplace / sharing
