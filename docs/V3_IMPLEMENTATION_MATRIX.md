# Version 3 implementation matrix

This matrix maps the twenty-point roadmap to the code, public API, persistence,
verification, and safety boundaries delivered in 00SWIFT v3.0.0.

> 00SWIFT remains an independent research sandbox. References to SWIFT, CBPR+,
> CIPS, e-CNY, HK retail behavior, BIS Innovation Hub, or mBridge describe
> independently authored behavioral models and synthetic fixtures. They do not
> represent certification, production connectivity, or redistributed restricted
> specifications.

## Batch 1 — standards and durable runtime

| # | Roadmap item | Implementation | Verification |
| ---: | --- | --- | --- |
| 1 | Versioned Standards Profile Registry | `nextgen/standards.py` defines explicit ISO 20022 base, CBPR+ 2025, CBPR+ SR2026, and CIPS 2026 research profiles. Findings contain profile, rule, message type, path, severity, and description. | Profile inventory and rule-selection tests; `/nextgen/v1/standards/profiles`. |
| 2 | SR2026 structured and hybrid addresses | Address classification distinguishes structured, hybrid, unstructured, and missing forms. SR2026 rules reject fully unstructured debtor and creditor addresses. | Positive structured/hybrid and negative unstructured vectors. |
| 3 | Business Application Header integrity | Business message identifier, message definition, business service, sender, receiver, UETR, amount, and currency rules are evaluated independently and across header/document boundaries. | BAH mismatch and required-field regression tests. |
| 4 | ISO 20022 message adapters | Hardened XML parsing and deterministic envelope generation support `pacs.008`, `pacs.009`, `pacs.002`, `pacs.004`, `camt.056`, `camt.029`, `camt.110`, `camt.111`, and `admi.024`. | XML round-trip, DTD/entity rejection, supported-family tests. |
| 5 | Standards conformance suite | Vectors declare profile, message family, payload, expected validity, and a deterministic SHA-256 digest. Results report exact failed rule identifiers. | `/nextgen/v1/standards/conformance`; CI regression vectors. |
| 9 | Idempotency, Outbox, and durable workflows | Persistent request hashes, replay-safe responses, transactional outbox events, retry/dead-letter states, optimistic workflow versions, and database leases. | Replay/conflict, outbox lifecycle/dead-letter, workflow-version, and API tests. |
| 20A | Migration and PostgreSQL foundation | Alembic environment, versioned next-generation schema, `psycopg`, SQLite local profile, and PostgreSQL durable profile. | Upgrade → downgrade → re-upgrade on SQLite and PostgreSQL 16 in every PR. |

## Batch 2 — payment lifecycle, CIPS, and two-tier e-CNY

| # | Roadmap item | Implementation | Verification |
| ---: | --- | --- | --- |
| 6 | UETR and Universal Confirmation lifecycle | UUIDv4 UETR creation, cover-payment inheritance, explicit state transitions, deadlines, optimistic versions, timeline events, and outbox publication. | Legal/illegal transitions, stale version, cover-inheritance, and complete timeline tests. |
| 7 | Transaction Copy and field lineage | Immutable message copies form a payload-hash chain. Flattened field records retain message, source party, value digest, and change reason. | Chain verification, tamper detection, and lineage-count tests. |
| 8 | Case Management | Cases require an existing UETR, type, owner, structured details, deadline, and an allow-listed state machine supporting review, information requests, resolution, closure, and reopening. | SLA creation, ownership transfer, transition, closure, and invalid-state tests. |
| 10 | Data Quality Analytics | Completeness, validity, consistency, and transaction-integrity scores remain separate and traceable to standards findings. | Perfect-message scoring, profile failures, BAH inconsistency, and copy-integrity tests. |
| 11 | CIPS participant directory and routing | Direct/indirect participants, BIC/LEI metadata, country, capabilities, settlement hours, and deterministic route scoring. | Exact-BIC, destination-jurisdiction, direct-participant, and capability ranking tests. |
| 12 | CIPS RTGS, DNS, and liquidity | Direct-participant settlement accounts, no-overdraft RTGS queue/release, priority ordering, DNS net positions, all-debit liquidity precheck, and atomic application. | Insufficient-liquidity queue, later release, balanced DNS, and atomic failure tests. |
| 13 | CIPS pre-validation and Payment Lens | Independent CIPS profile validation and cross-system event timelines keep SWIFT-style, CIPS, and ledger states distinct. | CNY-rule rejection and lifecycle/CIPS timeline tests. |
| 14 | Two-tier e-CNY operations | Central-bank service registers authorized operators, sets issuance ceilings, controls mint/redemption, and reconciles issued amount to the operator ledger account. | Issue, redeem, limit rejection, ledger balance, and reconciliation tests. |

## Batch 3 — retail CBDC, offline value, programmable money, and PvP

| # | Roadmap item | Implementation | Verification |
| ---: | --- | --- | --- |
| 15 | Hong Kong retail e-CNY profile | Synthetic four-tier wallets, phone-hash identity option, FPS-style top-up, quote reference, merchant-category payments, balance/single limits, and explicit cross-border P2P prohibition. | Top-up/payment balances, tier-limit rejection, inactive/unknown operator, and P2P-block tests. |
| 16 | Offline value and hardware-wallet risk model | Online value reservation into escrow, device binding, authenticated nonce, expiry, one-time redemption, invalidation, and duplicate-consumption rejection. | Reserve/redeem, wrong nonce, expired voucher, invalidation, and double-spend tests. |
| 17 | Constrained programmable money | Allow-listed directed-subsidy, merchant-category, expiry, staged-payment, escrow-release, conditional-refund, and multi-approval templates. Funds remain in ledger escrow; arbitrary code is rejected. | Allowed/denied context, spend, refund, expiry, threshold, and arbitrary-template tests. |
| 18 | Multi-CBDC jurisdiction model | Jurisdictions, central/commercial/operator/observer nodes, bilateral amount/purpose policy, data-residency declaration, and node lifecycle boundary. | Bilateral allow/deny reasons, unknown jurisdiction, role, and node tests. |
| 19 | FX quote and atomic PvP | Decimal rates, fees, capacity, expiry, expected credit-leg calculation, optimistic lock/commit/abort states, account leases, nested transaction, and two authoritative ledger legs. | Quote mismatch/expiry/capacity, source liquidity/currency, atomic commit, and abort tests. |
| 20B | Production-oriented platform controls | KMS/HSM provider protocol, authenticated local development provider, explainable RBAC/ABAC decisions, trace context, hash-chained audit evidence, reconciliation, diagnostic CI artifacts, Docker smoke tests, and release automation. | HMAC/encryption, policy reasons, audit tamper detection, reconciliation, container readiness, CodeQL, and published-asset verification. |

## Public API map

| Context | Base paths |
| --- | --- |
| Standards and conformance | `/nextgen/v1/standards/*` |
| Durable runtime | `/nextgen/v1/runtime/*` |
| Payment lifecycle and cases | `/nextgen/v1/payments/*`, `/nextgen/v1/cases/*` |
| CIPS research | `/nextgen/v1/cips/*` |
| Two-tier e-CNY | `/nextgen/v1/ecny/operators/*` |
| HK retail | `/nextgen/v1/hk-retail/*` |
| Offline value | `/nextgen/v1/offline/*` |
| Programmable money | `/nextgen/v1/programmable/*` |
| Multi-CBDC, FX, and PvP | `/nextgen/v1/cbdc/*`, `/nextgen/v1/fx/*`, `/nextgen/v1/pvp/*` |
| Policy, KMS, reconciliation, audit, privacy | `/nextgen/v1/policy/*`, `/nextgen/v1/kms/*`, `/nextgen/v1/reconciliation`, `/nextgen/v1/audit/*`, `/nextgen/v1/privacy/*` |

## Financial and runtime invariants

1. A cover payment cannot replace the original UETR.
2. Lifecycle and case transitions are explicitly allow-listed and version checked.
3. Transaction copies and runtime audit evidence expose tampering through hash-chain verification.
4. Idempotency keys cannot be reused with a different request body.
5. Outbox publication failure cannot erase the committed business operation.
6. RTGS accounts do not overdraw; unfunded settlements remain queued.
7. DNS net positions apply only after every net debit is fundable.
8. Authorized operators cannot increase currency supply outside the central-bank issuance service or above their ceiling.
9. Wallet, offline, programmable, and PvP balances are derived from authoritative ledger entries.
10. Offline value is reserved before disconnection and can redeem only once.
11. Programmable money cannot execute arbitrary user-supplied code.
12. FX quotes expire and enforce amount capacity before PvP locking and commit.
13. PvP uses two ledger legs inside one transaction boundary; failed settlement becomes `ABORTED`.
14. Policy and quality outputs contain explicit reasons and are not legal, AML, sanctions, or credit decisions.
15. The local key provider is development-only; production integrations implement the same provider protocol with an HSM or managed KMS.

## GitHub delivery evidence

The implementation was delivered through three independently reviewed pull
requests and a release-automation repair:

- Batch 1: standards, conformance, idempotency, migrations, and PostgreSQL foundation.
- Batch 2: lifecycle, transaction copies, cases, analytics, CIPS, and two-tier e-CNY.
- Batch 3: retail CBDC, offline value, programmable money, multi-CBDC, PvP, platform controls, and the v3 release request.
- Release repair: explicit post-publication validation dispatch, immutable-tag revalidation, asset replacement, and checksum redownload.

Every delivery PR passed:

- Python 3.11 and 3.12 regression suites;
- the 68% coverage floor;
- Ruff lint and canonical formatting;
- Python compilation and frontend JavaScript parsing;
- Bandit;
- Python and JavaScript/TypeScript CodeQL;
- SQLite and PostgreSQL migration round trips;
- Docker image build, real application startup, `/health`, and `/ready` probes;
- pending or published Release metadata and SHA-256 asset integrity.

The `v3.0.0` Release is represented by three independent repository facts:

1. the immutable `v3.0.0` tag contains package version `3.0.0`;
2. `.release/v3.0.0.published` records the gated publisher run and original merge commit;
3. `.release/v3.0.0.validated` records the independent immutable-tag validation run after assets were downloaded, verified, rebuilt, replaced, downloaded again, and reverified.
