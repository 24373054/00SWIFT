# CN–HK Production RACI (version 0.1-draft)

`A` means accountable sign-off; `R` responsible execution; `C` consulted;
`I` informed. Names and legal entities are intentionally blank until external
parties provide evidence.

| Control | Platform | Originating participant | Receiving participant | Settlement operator | Compliance | Legal/DPO | Security/HSM |
|---|---|---|---|---|---|---|---|
| Corridor admission | R | C | C | C | C | A | I |
| Rulebook acceptance | R | A | A | C | C | A | I |
| KYC/KYB and sanctions | I | R/A | R/A | C | A | C | I |
| Funding reservation | R (orchestrate) | A | C | R | C | I | C |
| Value finality | I | C | C | R/A | C | C | A (connector trust) |
| Ledger/reconciliation | R | A | A | C | C | I | I |
| Key ceremony/rotation | I | C | C | C | I | C | R/A |
| Data transfer/retention | R | C | C | C | C | A | C |
| Incident/DR | R | C | C | C | C | C | A |

All production `A` cells require named signatory evidence. Until supplied,
related controls remain `[EXT-BLOCKED]` and cannot authorize pilot/live.
