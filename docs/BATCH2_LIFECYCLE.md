# Payment lifecycle, CIPS settlement, and two-tier e-CNY

This document describes the independently authored research behavior introduced in roadmap batch 2. It is not an implementation guide for any production financial market infrastructure.

## UETR lifecycle

Every payment uses a UUIDv4 UETR and an explicit state machine. Cover-payment scenarios must retain the original UETR. Invalid, reverse, or stale-version transitions are rejected. Every transition writes a Payment Lens event and an outbox event so downstream delivery can be retried independently of the database transaction.

## Transaction copy and lineage

Each incoming or outgoing ISO 20022 representation can be recorded as an immutable transaction copy. Copies form a payload-hash chain. Leaf values are flattened into field-lineage records containing the source party, message identifier, value digest, and change reason. The platform can therefore identify where a value originated without exposing the original field in an index.

## Case management

Investigations are linked to an existing UETR and carry a case type, responsible owner, structured details, and deadline. The case state machine supports review, information requests, resolution, closure, and controlled reopening.

## Data quality

The research score separates four dimensions:

- completeness: populated fields versus observed fields;
- validity: standards-profile findings;
- consistency: cross-field and message-definition agreement;
- integrity: transaction-copy hash-chain verification.

A quality score is diagnostic evidence, not an AML, sanctions, credit, or legal determination.

## CIPS bounded context

CIPS participants, accounts, routes, settlement states, and lens events are distinct from SWIFT records. Direct participants may hold settlement accounts. RTGS transfers remain queued when available liquidity is insufficient and never create a negative balance. DNS batches calculate all net positions and apply them only after every net-debit participant can fund its position.

The included CIPS profile and routing directory are synthetic research constructs. They contain no production participant directory or restricted operating rules.

## Two-tier e-CNY

The central-bank service registers authorized operators, assigns an issuance ceiling, and controls mint and redemption operations. Operator issuance is reconciled against the existing ledger-authoritative account. Operators cannot create currency independently or exceed the configured ceiling.
