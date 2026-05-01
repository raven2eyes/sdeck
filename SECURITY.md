# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in SDeck, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **security@raven2eyes.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: within 48 hours
- **Assessment**: within 7 days
- **Fix**: as soon as practical, depending on severity

## Scope

This policy covers:
- The SDeck application code (`src/sdeck/`)
- Docker and Kubernetes deployment manifests (`deploy/`)
- CI/CD pipeline configurations (`.github/workflows/`)
- Profile and template handling

## Known Security Considerations

- Home Assistant tokens must be stored in `.env` (local) or Kubernetes Secrets (production) — never in code, ConfigMaps, or CI logs
- USB HID access requires elevated privileges — containers run with device passthrough, not as root where possible
- Profile YAML is validated via Pydantic before use — untrusted YAML is rejected at load time
