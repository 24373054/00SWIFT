# Migration baseline

Revisions `0001_nextgen_core.py`, `0002_production_domain.py` and
`0003_production_hardening.py` are immutable historical baselines. New schema
changes must use a new revision; editing any baseline requires an explicit
migration replacement plan and cannot be hidden in a later commit.

| Revision | SHA-256 | Known historical limitation |
|---|---|---|
| `0001_nextgen_core.py` | `8C138AD3E5398C65EEC995E6B1D31282FF1091F7406D99ADC569EFB680B16FC6` | Legacy nextgen tables and compatibility schema. |
| `0002_production_domain.py` | `898617045F539A3B876AF5A71D7DA3E77B191DC3DFA7294E3C065B659745E8E5` | Original production tables lacked complete FK/RLS constraints. |
| `0003_production_hardening.py` | `7CE96D09AE341A263DC82C589F6A68E97275CC12AF548A147A1D987416C708FB` | Historical dynamic metadata table creation; superseded by explicit revisions. |

The verifier in `backend/scripts/verify_migration_baseline.py` fails closed on
any hash mismatch or missing baseline. Revisions `0004+` are explicit forward
migrations and may be appended without changing this table.
