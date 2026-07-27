# Payment state machine

The orchestration state is separate from authorization, compliance, funding,
FX, message delivery, value settlement, beneficiary and reconciliation
dimensions. A network `DELIVERED` or `NETWORK_ACKED` fact never means `FINAL`.

| From | To | Command | Guard | Event | Timeout/compensation |
|---|---|---|---|---|---|
| CONTROL_CHECKS | RESERVATION_PENDING | authorize | authorization PASS | payment.authorized | authorization SLA / release limits |
| RESERVATION_PENDING | MESSAGE_DELIVERED | deliver_message | funding RESERVED + compliance PASS | payment.message.delivered | delivery SLA / release funding |
| MESSAGE_DELIVERED | VALUE_SETTLEMENT | settle | message DELIVERED | payment.settlement.submitted | settlement SLA / query then return |
| VALUE_SETTLEMENT | CUSTOMER_COMPLETED | credit | verified beneficiary credit | payment.beneficiary.credited | credit SLA / manual case |
| CUSTOMER_COMPLETED | OPERATIONALLY_CLOSED | close | journal + finality + reconciliation + no reservations | payment.operationally.closed | close SLA / case |
| EXECUTION_CANCELLED | OPERATIONALLY_CLOSED_UNSUCCESSFUL | close | reservations released + external status known | payment.cancelled.closed | close SLA / case |

Terminal states are immutable. Every command supplies an expected aggregate
version and every transition emits an auditable event/fact.
