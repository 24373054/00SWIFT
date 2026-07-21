# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/) where practical.

## [4.0.0] - 2026-07-22

### Institutional frontend

- Replace the primary vanilla-JavaScript dashboard with a Vite, React 19 and strict TypeScript application while retaining the previous developer console under `/legacy`.
- Introduce the **Cross-Border Payment Infrastructure Lab** product identity for government, bank, CIPS and institutional-partner workflows.
- Add graphite, ivory and restrained burgundy Daylight and Operations Dark themes with complete Chinese and English resources.
- Add workflow-oriented, role-aware navigation backed by persisted RBAC/ABAC policy decisions, decision reasons, obligations and redaction instructions.

### Operational visualisation

- Add a semantic 3D settlement-infrastructure scene with geographic, infrastructure and hybrid views plus complete 2D and Reduced Motion fallbacks.
- Add deterministic live/replay controls and representative incident scenarios using the same operational components.
- Add UETR lifecycle, RTGS liquidity and release dependencies, DNS gross-to-net matrix, atomic PvP sequence, multi-CBDC policy matrix, ISO 20022 structure explorer and Transaction Copy diff/hash-chain views.
- Distinguish message movement, value reservation, queueing, policy blocking and final settlement instead of rendering all movement as one decorative flow.

### Platform and delivery

- Add institutional UI bootstrap, authorization and Command Center read-model APIs with database overlays for payment, CIPS, case, liquidity and PvP state.
- Build the frontend in a dedicated container stage and serve the immutable production bundle from FastAPI, with SPA routing and legacy compatibility.
- Add frontend typecheck, unit-test, production-build, artifact, Docker smoke and release-package gates to CI.
- Package the verified frontend bundle inside release archives and repeat frontend and backend quality gates during independent post-publication validation.

## [3.0.0] - 2026-07-21

### Standards and interoperability

- Add versioned ISO 20022 base, CBPR+ 2025, CBPR+ SR2026, and CIPS research profiles.
- Validate structured and hybrid postal addresses for the SR2026 transition.
- Add Business Application Header and cross-message identifier consistency rules.
- Add behavioral adapters for pacs.008, pacs.009, pacs.002, pacs.004, camt.056, camt.029, camt.110, camt.111, and admi.024.
- Add deterministic conformance vectors, rule identifiers, effective dates, message paths, and reproducible digests.

### Payment lifecycle and CIPS

- Add UUIDv4 UETR lifecycle controls, cover-payment inheritance, deadlines, and optimistic concurrency.
- Add immutable transaction-copy chains and field-level data lineage.
- Add structured case management with ownership, SLAs, resolution, closure, and controlled reopening.
- Add completeness, validity, consistency, and transaction-integrity quality analytics.
- Add CIPS participant routing, direct-participant settlement accounts, liquidity-aware RTGS, atomic DNS netting, and Payment Lens events.

### Digital currency and settlement

- Add central-bank controlled two-tier e-CNY operator issuance, redemption, limits, and reconciliation.
- Add a synthetic Hong Kong cross-border retail profile with FPS-style top-up, wallet tiers, merchant payments, and explicit P2P restrictions.
- Add offline value reservation, authenticated vouchers, one-time redemption, expiry, and invalidation.
- Add allow-listed programmable-money templates without arbitrary code execution.
- Add multi-CBDC jurisdictions, nodes, bilateral policy checks, data-residency declarations, FX quotes, and atomic payment-versus-payment settlement.

### Runtime, security, and delivery

- Add universal idempotency records, transactional outbox events, durable workflows, dead-letter states, and database leases.
- Add PostgreSQL and Alembic migration support while retaining SQLite for local development.
- Add an HSM/KMS provider interface, authenticated local development provider, explainable RBAC/ABAC policy decisions, trace contexts, hash-chained audit evidence, and end-of-day reconciliation.
- Validate migrations against both SQLite and PostgreSQL in GitHub Actions.
- Add a release-candidate gate that permits publication only after main CI and same-commit CodeQL success.

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
- Add a 68% line-coverage gate, Ruff, Bandit, compile checks, JavaScript parsing, Docker builds, CodeQL, release validation.
- Add a production-grade README, architecture/API/operations/threat-model documentation, contribution policy, security policy, issue templates, Dependabot, container assets, and release process.

## [2.0.0] - 2026-07-20

- Introduced the contract-aligned SWIFT sandbox and initial e-CNY cross-border payment prototype.
