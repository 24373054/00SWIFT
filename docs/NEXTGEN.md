# Next-generation payment research platform

The `/nextgen/v1` surface is a standards-driven research layer built beside the existing SWIFT-style and e-CNY sandbox APIs. It is deliberately separated from institutional connectivity and does not claim certification by SWIFT, CIPS, PBOC, HKMA, BIS Innovation Hub, or mBridge.

## Design principles

1. Standards behavior is selected through explicit, versioned profiles.
2. Transport schemas, market-practice rules, domain invariants, and settlement state are validated independently.
3. Every mutating workflow is designed for idempotency, durable state, and transactional event publication.
4. SWIFT, CIPS, e-CNY, and multi-CBDC concepts remain separate bounded contexts.
5. Monetary state is never inferred from message status alone; settlement and accounting records are authoritative.
6. Rules and test vectors carry source dates and deterministic digests so behavior can be reproduced.

## Batch 1 capabilities

- ISO 20022 base, CBPR+ 2025, CBPR+ SR2026, and CIPS research profiles.
- Structured and hybrid postal address checks for the SR2026 transition.
- Business Application Header and message-identifier consistency checks.
- Behavioral envelopes for pacs.008, pacs.009, pacs.002, pacs.004, camt.056, camt.029, camt.110, camt.111, and admi.024.
- Deterministic conformance-vector execution.
- Idempotency records, transactional outbox events, durable workflows, dead-letter state, and database leases.
- Alembic migrations and PostgreSQL runtime support while retaining SQLite for local tests.

## Public endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/nextgen/v1/standards/profiles` | List available standards profiles |
| POST | `/nextgen/v1/standards/validate` | Validate a JSON or XML message against a profile |
| POST | `/nextgen/v1/standards/build` | Build the research ISO 20022 envelope |
| POST | `/nextgen/v1/standards/conformance` | Execute deterministic conformance vectors |
| POST | `/nextgen/v1/runtime/outbox` | Enqueue an idempotent transactional event |

## Restricted standards material

The repository implements independently authored behavioral subsets derived from publicly described requirements. It must not contain or redistribute licensed implementation guides, proprietary schemas, production directories, credentials, participant data, or confidential integration material.

## Delivery sequence

- Batch 1: standards, conformance, idempotency, migrations, and PostgreSQL foundation.
- Batch 2: UETR lifecycle, transaction copies, investigations, quality analytics, CIPS participants, routing, RTGS/DNS, and two-tier e-CNY operations.
- Batch 3: Hong Kong retail profile, offline value, programmable instruments, multi-CBDC governance, FX/PvP, policy, key management, telemetry, reconciliation, and the v3 release.
