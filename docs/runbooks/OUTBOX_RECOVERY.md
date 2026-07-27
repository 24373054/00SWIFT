# Outbox recovery runbook

## Scope

Use this runbook for a stuck, failed, duplicated, or dead-lettered production event. Every action is tenant-scoped and operator-authenticated.

## Triage

1. Query `GET /production/v1/outbox/metrics` and record `pending`, `processing`, `oldest_event_age_seconds`, `retry_attempts`, and `dead_letter`.
2. Inspect `GET /production/v1/dlq/{event_id}`. Verify `payload_hash`, aggregate, tenant, attempts, and `last_error` against the audit trail.
3. For `PROCESSING` with a null/expired lease, run the worker; the claim transaction reclaims it with `SKIP LOCKED` and ownership fencing.

## External side-effect safety

Before retrying a connector operation, query the connector by the persisted stable client reference (reservation intent, trade intent, message reference, settlement reference, cancellation id, or return id). Do not resend until the query proves no prior effect.

## DLQ replay

1. Operator creates `POST /production/v1/dlq/{event_id}/replay` with a reason.
2. A distinct checker approves `POST /production/v1/dlq/replays/{replay_id}/approve`.
3. Approval verifies the original payload hash and only then moves the event to `PENDING`; it never edits business state directly.
4. Capture both subjects, timestamps, hash, reason, and resulting event receipt in the incident record.

## Escalation

If broker, schema registry, connector, HSM, or PostgreSQL is unavailable, keep the event in `PENDING`/`DEAD_LETTER` and mark the incident `[EXT-BLOCKED]`. Never force a success state or bypass maker-checker.
