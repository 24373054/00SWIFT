# Operations Runbook

## Environment profiles

### Sandbox

- Local mock services and reference fixtures.
- Self-signed sandbox certificate authority and per-application certificates.
- Empty admin token is permitted only for loopback development.
- SQLite is the default database.

### Pilot

- Intended for approved test endpoints and externally managed certificates.
- Requires an administrative token and configured upstream hosts.
- Must run behind TLS, access control, and restricted egress.

### Live

- Defensive production profile only; it is not a certification claim.
- Startup validates mandatory controls and emits an explicit warning.
- Requires independent architecture, legal, security, compliance, and operational approval.

## Start and stop

Native:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765
```

Container:

```bash
docker compose up -d --build
docker compose logs -f app
docker compose down
```

Graceful process termination stops the background JTI cleanup loop. Use the orchestrator's normal termination grace period rather than killing the process.

## Health model

- `GET /health`: process liveness, current mode, version.
- `GET /ready`: database connectivity.

Route traffic only when readiness succeeds. A healthy process with a failing readiness probe should be removed from service but not immediately crash-looped without investigation.

## Logging and audit

The request middleware records correlation, route, result, and measured latency. Bodies are bounded and recursively redact common secret fields. Operators must still:

- prevent debug logging in shared environments;
- restrict log access and retention;
- avoid placing sensitive values in URLs, custom field names, or free-text memos;
- forward security events to an append-only or tamper-evident destination;
- alert on repeated authentication failures, replay attempts, signature errors, and unusual administrative calls.

## Database

SQLite is a single-node development default. Before shared deployment:

1. adopt PostgreSQL or another reviewed transactional database;
2. introduce schema migrations rather than implicit table creation;
3. encrypt storage and backups;
4. test point-in-time recovery;
5. enforce least-privilege database credentials;
6. monitor connection, lock, transaction, and storage health;
7. reconcile ledger invariants after restore.

A ledger-integrity check should verify that every transaction balances by currency and that no orphan entries exist.

## Certificates and secrets

- Store `ADMIN_API_TOKEN` in the runtime secret store.
- Mount private keys with read-only, owner-only permissions.
- Never bake keys into container images or CI artifacts.
- Rotate credentials and revoke prior tokens during compromise response.
- Treat generated sandbox certificates as disposable and untrusted externally.
- For pilot/live, use an HSM/KMS or institution-approved PKI workflow.

## Backup and recovery

Back up database state and the exact application/configuration version together. Certificate recovery depends on deployment policy: production private keys should normally be recovered from the managed key system, not copied from application disks.

Recovery validation:

1. restore into an isolated environment;
2. run database connectivity and schema checks;
3. verify ledger balance invariants;
4. verify token/revocation and replay-store semantics;
5. run a signed end-to-end sandbox transaction;
6. only then restore traffic.

## Incident response

For suspected key/token exposure:

1. isolate the service and preserve logs;
2. rotate administrative and application credentials;
3. revoke active tokens and invalidate replay windows where appropriate;
4. inspect audit records by request ID and client identity;
5. reconcile ledger/payment state and upstream systems;
6. patch and test the root cause;
7. document scope, timeline, decisions, and notification obligations.

Do not use this sandbox to investigate third-party systems without authorization.

## Release and rollback

Releases are tagged from a green `main` commit. CI, CodeQL, tests, security checks, and the Docker build must pass before tagging. See [RELEASE.md](RELEASE.md).

Rollback is application-version rollback plus a database compatibility decision. Never roll back code across an irreversible schema/data change without a tested migration plan.
