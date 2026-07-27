# Payment compensation table

| Step | Failure/unknown | Compensation | Evidence and idempotency |
|---|---|---|---|
| funding reserve | rejected/timeout | release reservation; query before retry | reservation intent reference |
| FX accept | timeout/unknown | query trade intent; open case if indeterminate | trade intent reference |
| message send | rejected | suspend and open case | message client reference |
| settlement submit | timeout/unknown | query finality; return only after proof | settlement leg reference |
| cancellation | accepted | release funding/limit/FX exposure; close unsuccessful | cancellation request id |
| return | rejected/unknown | retain original facts; query return reference | return payment id/UETR |

Each compensation action is an append-only fact/evidence event and is itself
idempotent. No row is moved to a successful terminal state without external
proof, journal and reconciliation evidence.
