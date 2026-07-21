# Threat Model

## Assets

- application consumer secrets and private keys;
- OAuth bearer tokens and certificate identities;
- administrative control over fixtures and credentials;
- payment, wallet, ledger, message, and compliance state;
- audit records and correlation identifiers;
- upstream endpoint configuration.

## Adversaries

- unauthenticated network callers;
- authenticated clients attempting privilege escalation or replay;
- malicious/compromised administrators;
- supply-chain compromise in dependencies or CI actions;
- accidental operator misconfiguration;
- a compromised upstream or man-in-the-middle outside correctly validated TLS.

## Primary threats and controls

| Threat | Control in repository | Required deployment control |
| --- | --- | --- |
| Secret disclosure | Salted secret hashes; one-time return; audit redaction | Secret manager, access reviews, rotation |
| Bearer-token theft from DB | Token digests at rest | Database encryption, network isolation |
| Client assertion replay | Persistent JTI store and expiry window | Shared durable store for multiple replicas |
| Request-body substitution | Exact-body signature verification | TLS, canonical client signing implementation |
| Scope escalation | Requested-scope subset validation | Credential governance and review |
| Cross-client revocation | Token ownership check | Administrative monitoring |
| Ledger tampering/drift | Double-entry posting and ledger-derived balances | DB roles, append-only audit, reconciliation |
| Limit bypass | Source/destination/per-tx/daily checks | Concurrency controls and policy service |
| Log exfiltration | Bounded recursive redaction | SIEM access control and retention policy |
| Admin endpoint abuse | Admin token and mode validation | Separate management plane, mTLS/RBAC |
| Dependency compromise | Dependabot, Bandit, CodeQL, scheduled audit | Pinning/provenance review, artifact signing |
| Denial of service | Bounded collection/body limits | Rate limiting, quotas, WAF, autoscaling |

## Residual risks

- SQLite and in-process scheduling are unsuitable for horizontally scaled production.
- The deterministic token digest permits equality correlation inside the database; use a keyed digest or dedicated token service when the database threat model requires it.
- PBKDF2 parameters should be reviewed periodically and migrated as hardware changes.
- The sandbox has no universal idempotency key, distributed lock, or serializable policy engine for concurrent financial operations.
- Compliance hooks are illustrative and do not implement sanctions-list quality, model governance, explainability, or regulatory reporting obligations.
- Reference fixtures can become stale and are not authoritative.
- Pilot/live forwarding requires additional validation not represented by local tests.

## Security test priorities

Future security work should include property-based ledger tests, concurrency/race tests, malformed JWT/certificate fuzzing, XML entity/schema abuse tests, authorization matrices, migration tests, dependency provenance verification, and container/runtime hardening scans.
