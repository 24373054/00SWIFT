# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 2.1.x | Yes |
| 2.0.x and earlier | No |

Security fixes are released from the latest minor line. This repository is a research sandbox, not certified financial infrastructure.

## Reporting a vulnerability

Do **not** open a public issue containing exploit details, credentials, private keys, payment data, or a working proof of concept. Use GitHub's private vulnerability reporting feature on this repository. Include:

- affected version or commit;
- affected endpoint/module;
- prerequisites and realistic impact;
- minimal reproduction steps;
- suggested remediation, when known.

You should receive an acknowledgement through GitHub Security Advisories. Please allow the maintainer time to validate, patch, test, and coordinate disclosure. Do not access data that is not yours, disrupt services, or test against third-party/production financial systems.

## Security boundaries

- `sandbox` is the only mode intended for local experimentation.
- `pilot` and `live` require explicit administrative credentials, upstream hosts, and externally managed PKI material.
- Generated sandbox certificates are not trusted outside this application.
- SQLite is suitable for local development; multi-user deployment requires a production database, backups, access control, and migrations.
- Built-in compliance rules are demonstration controls, not legal or regulatory determinations.

## Deployment minimums

Before any network exposure:

1. Set a high-entropy `ADMIN_API_TOKEN` through a secret manager.
2. Restrict `CORS_ORIGINS` and bind behind an authenticated TLS reverse proxy.
3. Mount certificate/private-key material read-only and apply least-privilege permissions.
4. Replace SQLite with a supported production database and configure encrypted backups.
5. Export redacted logs to access-controlled, tamper-evident storage.
6. Add rate limiting, network policy, WAF/API gateway controls, alerting, and incident procedures.
7. Review all upstream contracts and legal/compliance obligations independently.

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) and [docs/OPERATIONS.md](docs/OPERATIONS.md).
