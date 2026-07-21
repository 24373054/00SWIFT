# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/) where practical.

## [2.1.0] - 2026-07-21

### Security

- Store application secrets as salted PBKDF2 hashes and reveal them only once.
- Persist OAuth access tokens as deterministic digests rather than reusable bearer values.
- Bind token revocation to the authenticated client.
- Verify request signatures against the exact request body without an empty-body fallback.
- Enforce sandbox e-CNY administration tokens and fail closed in pilot/live environments.
- Redact assertions, credentials, tokens, and nested sensitive fields from bounded audit logs.
- Apply constant-time comparisons to administrative credentials.

### Ledger and domain correctness

- Make double-entry ledger entries the source of truth for wallet balances.
- Add currency to ledger entries and database integrity constraints.
- Model central-bank issuance and redemption with balanced liability entries.
- Calculate outstanding issuance without being affected by wallet-to-wallet transfers.
- Enforce source, destination, per-transaction, daily, and balance limits.
- Reject non-finite monetary values during pre-validation.

### Reliability

- Fix a latent GPI status-transition constant error.
- Honor configured certificate directories and protect generated private-key permissions.
- Add liveness and database-backed readiness probes.
- Replace optional router imports with explicit startup failures.
- Clamp pagination limits and harden schema defaults and validations.

### Quality and delivery

- Expand the suite from 36 to 50 tests, including authentication, API-security, e-CNY flow, and regression coverage.
- Add a 68% line-coverage gate, Ruff, Bandit, compile checks, JavaScript parsing, Docker builds, CodeQL, and release validation.
- Add a production-grade README, architecture/API/operations/threat-model documentation, contribution policy, security policy, issue templates, Dependabot, container assets, and release process.

## [2.0.0] - 2026-07-20

- Introduced the contract-aligned SWIFT sandbox and initial e-CNY cross-border payment prototype.
