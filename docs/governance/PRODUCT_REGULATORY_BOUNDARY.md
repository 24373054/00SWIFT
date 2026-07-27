# Product and Regulatory Boundary (version 0.1-draft)

Status: **DRAFT / `[EXT-BLOCKED]`**. This document is an engineering boundary,
not a legal opinion, license, settlement guarantee, or representation that the
system is a SWIFT participant or a digital RMB clearing institution.

## Legal entities and funds-flow boundary

| Stage | Debtor-side regulated entity | Network/message role | Creditor-side regulated entity | Funds authority | Evidence required |
|---|---|---|---|---|---|
| Instruction | Licensed originating participant (to be named) | Authenticated service identity | Licensed receiving participant (to be named) | Participant account mandate | mandate, KYC/KYB, message signature |
| Funding | Debtor participant / appointed settlement bank | Funding connector | Receiving participant | Reservation and release evidence | reservation, limit, sanction decision |
| Value settlement | Approved value-settlement operator (to be named) | Qualified connector | Approved operator/participant | Finality event only from qualified source | finality proof, connector attestation |
| Beneficiary credit | Receiving participant | pacs.002/pacs.004 lifecycle | Beneficiary account provider | Local credit authority | beneficiary credit evidence |
| Reconciliation | Both participants and appointed operator | Evidence/reporting | Both participants | Ledger and external statement comparison | immutable journal, break case, sign-off |

The platform stores instructions, control decisions, evidence and projections;
it does not custody funds, issue e-CNY, create legal finality, or replace a
licensed participant. A production payment is denied until the named entities,
licensed roles, corridor rulebook and signatories are externally approved.

## Explicit non-commitments

- No claim of SWIFT membership, ISO certification, PBOC/HKMA endorsement,
  settlement finality, or legal enforceability.
- No claim that sandbox connectors, embedded standards or simulated finality
  are production evidence.
- No cross-border data transfer or personal-data processing approval is implied.
- No participant, HSM, CA, OCSP/CRL or legal sign-off is inferred from a config
  path, test fixture or successful local test.

Approved version and validity must be represented by an ACTIVE
`ProductionCorridorAdmission` and `ProductionControlAttestation`; absent those,
readiness and payment creation remain default-deny.
