# CN–HK Corridor Admission Matrix (version 0.1-draft)

Every row requires an ACTIVE, time-valid admission and at least one valid
control attestation. `simulation_only=true` rows are confined to sandbox.

| Scenario | Currency | Subjects | Amount/time constraints | Funding flow | Finality | Data flow | Rulebook | Production status |
|---|---|---|---|---|---|---|---|---|
| Trade goods/services | CNY/HKD | Licensed CN/HK participants (TBD) | Admission-specific min/max and validity window | Versioned reservation/debit/credit | Qualified operator event (TBD) | Versioned CN/HK data map and retention | Signed participant rulebook (TBD) | `[EXT-BLOCKED]` |
| Salary/remittance | Not admitted by default | None until separate approval | N/A | N/A | N/A | N/A | N/A | DENY |
| Sandbox test | CNY/HKD | `SANDBOX-ORIGIN` | Local-only bounded window | Sandbox funding connector | Simulation finality only | Local test data | `sandbox-rulebook-v1` | SIMULATION |

Admission must match environment, corridor, subject, purpose scenario,
currency, amount and current time. A sandbox row cannot be copied into pilot or
live because the runtime rejects `simulation_only` admissions there.

Open decisions requiring external owners: licensed entities, permitted use
cases, settlement operator, FX model, participant rulebook, data transfer
mechanism, retention period, sanctions/AML controls and finality definition.
