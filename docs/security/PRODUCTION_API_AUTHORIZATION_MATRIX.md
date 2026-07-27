# Production API Authorization Matrix

This matrix is the security contract for every `/production/v1/*` route. A
blank requirement is intentional only for liveness or a read-only endpoint;
all mutation rows require authenticated participant identity, tenant scope,
integrity verification, idempotency where state can change, and an audit fact.

| Route | Method | Identity | Scope | Tenant filter | Integrity | Idempotency | Maker/checker | Audit |
|---|---:|---|---|---|---|---|---|---|
| `/health` | GET | public liveness | none | none | none | n/a | n/a | telemetry |
| `/payments` | POST | service identity | `production.write` | initiator participant | RFC9421 + digest | required | payment authorization | payment fact + evidence |
| `/payments` | GET | service identity | `production.read` | participant/admin | signed response context | n/a | n/a | access event |
| `/payments/{order_id}` | GET | service identity | `production.read` | owner/admin | signed response context | n/a | n/a | access event |
| `/payments/{order_id}/facts` | GET | service identity | `production.read` | owner/admin | signed response context | n/a | n/a | access event |
| `/payments/{order_id}/investigation-cases` | POST | operator identity | `production.write` | owner/admin | RFC9421 + digest | required | checker for closure | investigation audit |
| `/investigation-cases` | GET | operator identity | `production.read` | tenant/admin | signed response context | n/a | n/a | access event |
| `/fx-quotes` | POST | service identity | `production.write` | participant | RFC9421 + digest | required | quote acceptance later | FX audit |
| `/payments/{order_id}/fx-acceptance-intents` | POST | service identity | `production.write` | owner | RFC9421 + digest | required | maker/checker | FX intent audit |
| `/payments/{order_id}/cancellation-requests` | POST | service identity | `production.write` | owner | RFC9421 + digest | required | maker/checker | cancellation audit |
| `/payments/{order_id}/return-requests` | POST | service identity | `production.write` | owner | RFC9421 + digest | required | maker/checker | return audit |
| `/participants` | POST | admin/operator identity | `production.admin` | tenant admin | RFC9421 + digest | required | dual control | participant audit |
| `/participants/{participant_id}/entitlements` | POST | admin/operator identity | `production.admin` | target tenant | RFC9421 + digest | required | dual control | entitlement audit |
| `/service-identities` | POST | admin/operator identity | `production.admin` | target tenant | RFC9421 + digest | required | dual control | credential audit |
| `/participants/{participant_id}/limit-profiles` | POST | admin/operator identity | `production.admin` | target tenant | RFC9421 + digest | required | dual control | limit audit |
| `/approvals` | POST | maker/checker identity | `production.admin` | aggregate tenant | RFC9421 + digest | required | maker != checker; independent checker | approval audit |
| `/outbox` | GET | operator identity | `production.read` | tenant/admin | signed response context | n/a | n/a | operational access |
| `/ledger/trial-balance` | POST snapshot | operator identity | `production.ledger.read` | legal entity/book | RFC9421 + digest | snapshot key | dual control for export | ledger audit |
| `/worker/run` | POST | internal worker identity | `production.worker` | service tenant | internal mTLS/signature | worker lease | n/a | worker audit |
| `/operations/summary` | GET | operator identity | `production.read` | tenant/admin | signed response context | n/a | n/a | operational access |
| `/reconciliation/runs` | POST | operator identity | `production.ledger.write` | tenant/legal entity | RFC9421 + digest | required | dual control | reconciliation audit |
| `/ledger/accounts` | GET | operator identity | `production.ledger.read` | tenant/legal entity | signed response context | n/a | n/a | ledger access |
| `/ledger/accounts` | POST | operator identity | `production.ledger.write` | tenant/legal entity | RFC9421 + digest | required | dual control | ledger audit |
| `/ledger/journals` | POST | operator identity | `production.ledger.write` | tenant/legal entity | RFC9421 + digest | required | dual control | immutable journal audit |
| `/evidence/{evidence_id}` | GET | operator/auditor identity | `production.audit.read` | tenant/legal hold | signed response context | n/a | n/a | evidence access |
| `/reporting/reports` | GET | auditor/operator identity | `production.audit.read` | tenant/jurisdiction | signed response context | n/a | n/a | report access |
| `/evidence/{evidence_id}/legal-hold` | POST | legal/auditor identity | `production.audit.write` | tenant | RFC9421 + digest | required | dual control | legal hold audit |
| `/standards/profiles` | GET | service identity | `production.read` | corridor/tenant | signed response context | n/a | n/a | standards access |
| `/standards/validate` | POST | service identity | `production.write` | participant/corridor | RFC9421 + digest | required | message authorization | standards evidence |

## Non-negotiable rules

1. Production never trusts `X-User-Role`, `X-User-Subject` or arbitrary
   `X-Participant-ID`; those headers are test-only and must be rejected outside
   sandbox.
2. A mutation is not authorized until identity, scope, tenant, message
   integrity, idempotency, business authorization, and audit context all pass.
3. Maker and checker identities must be distinct and independently entitled;
   an administrator cannot self-approve by adding an elevated role header.
4. `/worker/run` is internal-only and is unavailable from the public pilot/live
   router. Simulation responses are labelled and cannot satisfy readiness.
