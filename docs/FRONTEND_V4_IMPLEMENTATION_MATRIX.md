# Frontend v4 Implementation Matrix

## Cross-Border Payment Infrastructure Lab

This matrix records the implementation and verification boundary for version 4.0.0.

| Approved requirement | Implementation | Backend contract | Verification |
| --- | --- | --- | --- |
| Institutional product shell | `frontend/src/App.tsx` | `/nextgen/v1/ui/bootstrap` | Typecheck, production build, Docker smoke |
| Graphite / ivory / burgundy visual system | `frontend/src/styles.css` | N/A | Production bundle and responsive CSS review |
| Daylight and Operations Dark | Theme tokens in `styles.css`; theme control in `App.tsx` | Product environment returned by bootstrap | Frontend unit/build gate |
| Chinese and English | `frontend/src/i18n.ts` | Bilingual labels in UI read models | Strict TypeScript ensures key parity |
| Workflow navigation | Role-aware workspace list in `App.tsx` | Backend returns enabled state and reason | UI bootstrap API tests |
| RBAC/ABAC integration | Decision ID, result and unavailable workspaces rendered by UI | `ui_router.py`, `PolicyEngine`, persisted `PolicyDecision` | Allow, deny, redaction and obligation API tests |
| Global settlement network | `NetworkScene.tsx` | Command Center corridor read model | WebGL build, Docker bundle, 2D fallback |
| Reduced Motion / 2D | SVG operational geography and media-query behavior | Same corridor read model as 3D | No separate demo data path |
| Live and replay | Replay runtime in `App.tsx`; scenarios in backend and fallback fixtures | Command Center scenarios and live database overlay | Deterministic frontend unit tests |
| UETR lifecycle | `UetrLifecycle` in `Visualizations.tsx` | Payment lifecycle and Payment Lens overlay | Contract test verifies lifecycle model |
| RTGS liquidity | `RtgsLiquidity` | `CipsAccount` and queued settlement overlay | API contract and domain tests |
| DNS netting | `DnsNetting` | DNS matrix read model; existing atomic netting service | Matrix and liquidity metrics present in contract test |
| Atomic PvP | `PvpSequence` | `PvpSettlement` live state overlay | Existing PvP domain tests plus UI contract |
| Jurisdiction policy | `PolicyMatrix` | RBAC/ABAC decisions and representative bilateral policy | Amount denial and dual-approval tests |
| ISO 20022 structure | `IsoExplorer` | Versioned standards profiles and findings | Frontend typecheck and standards suite |
| Transaction Copy diff | `MessageDiff` | Transaction Copy and hash-chain domain | Existing copy-integrity tests and UI contract |
| Legacy migration path | `/legacy`, original `app.js` and `style.css` retained | Existing API contracts unchanged | Docker smoke checks both interfaces |
| Production serving | Vite `dist`, FastAPI static assets and SPA fallback | FastAPI `/`, `/assets`, catch-all | Container readiness and UI smoke |
| Release packaging | `publish.yml` includes verified `frontend/dist` | Version and release markers | Same-commit CI/CodeQL gate and checksums |
| Independent validation | `release.yml` rebuilds frontend and backend from tag | Published release metadata | Asset replacement and SHA-256 verification |

## Security boundary

- The backend remains authoritative for protected actions.
- UI hiding or disabling is never considered authorization.
- Institutional identity headers must only be trusted behind an authenticated gateway and the administration-token boundary.
- High-value mutations can carry dual-approval and operator-reason obligations.
- Non-investigator roles receive field-redaction instructions.
- The product remains an independent research sandbox and makes no official certification or production-connectivity claim.

## Performance and accessibility boundary

- Three-dimensional rendering is isolated from financial domain state.
- Every operationally important 3D state has a 2D representation.
- Reduced Motion follows the platform preference and can be selected explicitly.
- The application remains usable if WebGL is unavailable or the frontend API cannot be reached; deterministic representative data is clearly labelled.
- Release acceptance requires the production bundle, not development source alone.
