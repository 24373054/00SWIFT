# Frontend v4 Design Brief

## Cross-Border Payment Infrastructure Lab

Status: **Approved design direction**  
Audience: government agencies, banks, CIPS and institutional partners  
Product objective: a production-oriented, long-lived cross-border payment infrastructure workspace rather than a developer demo dashboard.

---

## 1. Approved decisions

| Decision | Approved direction |
|---|---|
| Product model | Multi-role platform with role-aware workspaces |
| Primary landing experience | Executive situational overview |
| Visual character | Sovereign institution / central-bank research system |
| Brand palette | Graphite, ivory and restrained burgundy |
| Theme model | Daylight analysis theme + Operations Dark monitoring theme |
| Information density | High-density financial terminal |
| Navigation | Organised by business workflow |
| Language | Full Chinese / English switch, never ad-hoc mixed-language pages |
| Frontend architecture | Vite + React + TypeScript |
| Motion language | Precision-mechanical motion |
| Geographic model | Geographic map and abstract infrastructure network switch |
| Time model | Live, historical windows and full replay |
| Primary executive metric | Cross-border payment volume |
| Spatial graphics | Extensive 3D is permitted, subject to strict semantic and performance rules |
| Home layout | Central situational map |
| Demonstration model | Full scenario story and replay engine |
| Authorization | Real backend RBAC/ABAC integration |
| Forbidden patterns | Large gradients, glassmorphism, glow borders, cyberpunk, crypto-exchange styling, card grids, excessive pill badges and purple as brand colour |

Priority visualisations approved for the first complete product programme:

1. Global cross-border payment situation map
2. UETR lifecycle track
3. RTGS liquidity and queue view
4. DNS net-settlement matrix
5. Atomic PvP settlement sequence
6. Multi-CBDC jurisdiction policy matrix
7. ISO 20022 message structure explorer
8. Message-version and Transaction Copy diff

---

## 2. Product positioning

The frontend must present 00SWIFT as a **cross-border payment infrastructure operating environment**. It is not:

- a generic API administration dashboard;
- a crypto exchange terminal;
- a marketing landing page;
- a collection of decorative financial charts;
- a simulated official SWIFT, CIPS or central-bank production console.

The interface must communicate four institutional qualities:

1. **Authority** — stable hierarchy, restrained materials and clear operational ownership.
2. **Traceability** — every important state, decision and mutation has an inspectable cause.
3. **Operational control** — the interface prioritises exceptions, liquidity, deadlines and interventions.
4. **Policy awareness** — jurisdiction, standards and access policy are first-class system objects.

All public-facing text must continue to state that the repository is an independent research sandbox and does not claim official certification, authorization or production connectivity.

---

## 3. Information architecture

Navigation is organised by workflow rather than by protocol brand.

### 3.1 Primary navigation

1. **Command Center**
   - Executive overview
   - Live network
   - Replay
   - Intervention queue

2. **Payments**
   - Payment worklist
   - UETR search
   - Payment detail
   - Transaction Copy
   - Data quality

3. **Investigations**
   - Open cases
   - SLA queue
   - Evidence graph
   - Case history

4. **Settlement**
   - CIPS routing
   - RTGS queue
   - DNS batches
   - Liquidity
   - FX quotes
   - PvP

5. **Standards**
   - Standards profiles
   - ISO 20022 builder
   - Validation findings
   - Conformance vectors
   - Message diff

6. **Digital Currency**
   - e-CNY operators
   - Retail wallets
   - Offline value
   - Programmable instruments
   - Multi-CBDC jurisdictions

7. **Risk & Policy**
   - Policy decisions
   - Jurisdiction matrix
   - Reconciliation
   - Audit integrity
   - Privacy controls

8. **Developer**
   - Credentials
   - API catalogue
   - Request builder
   - Environment diagnostics

9. **Administration**
   - Roles
   - Attributes
   - Entitlements
   - Display policy
   - System configuration

### 3.2 Role-aware experience

The authenticated role and backend policy decision determine:

- visible workspaces;
- visible data fields;
- permitted actions;
- approval requirements;
- masking and redaction;
- default landing page;
- alert severity and ownership.

Proposed primary roles:

- Executive Viewer
- Settlement Operator
- Payment Operations Analyst
- Compliance Investigator
- Standards Engineer
- CBDC Researcher
- Platform Administrator

The frontend must never treat hidden UI as authorization. Every protected action is enforced by backend RBAC/ABAC and the frontend renders the returned policy decision and reasons.

---

## 4. Visual system

### 4.1 Palette

The base palette is institutional and material rather than luminous.

- Graphite: navigation, primary text, operations surfaces
- Ivory: analytical canvas and document surfaces
- Burgundy: controlled emphasis, institutional identity and critical selected state
- Slate: hierarchy, secondary data and borders
- Amber: warning and SLA risk
- Red: failed, blocked or destructive state only
- Green: settled, reconciled or healthy state only
- Blue: informational system state, never the dominant brand field

Colour is semantic. It must not be used to make every chart category visually distinct.

### 4.2 Typography

Use a dual-family system:

- editorial/institutional family for major titles and formal summaries;
- highly legible UI family for controls, tables and long operational sessions;
- tabular or monospaced numerals for money, UETR, BIC, LEI, message IDs and timestamps.

Typography must provide the hierarchy that card borders currently provide. Avoid oversized marketing headings inside the application.

### 4.3 Shape and surfaces

- low-radius panels;
- thin borders;
- little or no floating shadow;
- strong baseline alignment;
- clear row and column rhythm;
- separators and whitespace before container proliferation;
- no card-grid homepage;
- no decorative top-edge gradients;
- no excessive pill badges.

Status should be communicated through compact text, icon, marker shape and restrained colour, not colour alone.

### 4.4 Themes

#### Daylight

Designed for configuration, standards analysis, investigations, reports and long reading sessions.

#### Operations Dark

Designed for live monitoring, settlement operations and replay. It is not a simple colour inversion; density, contrast, map layers and alert emphasis are tuned independently.

---

## 5. Command Center

The Command Center uses a central situational visual rather than a KPI-card grid.

### 5.1 Layout

- central map / infrastructure scene occupies the primary visual field;
- cross-border payment volume is the dominant executive metric;
- risk and intervention rail on one side;
- settlement and liquidity state on the opposite side;
- event stream and replay timeline below;
- contextual details open in a split panel without replacing the scene.

### 5.2 View modes

1. **Geographic View**
   - legal jurisdictions and real geographic placement;
   - payment corridors;
   - aggregate volume;
   - route state;
   - policy and data-residency overlays.

2. **Infrastructure View**
   - central banks;
   - clearing systems;
   - participant banks;
   - operator institutions;
   - settlement accounts;
   - route and dependency topology.

3. **Hybrid View**
   - geographic context retained;
   - infrastructure nodes elevated into a restrained spatial layer;
   - selected transaction path shown across both models.

### 5.3 Time controls

- Live
- 1 hour
- 24 hours
- 7 days
- Custom range
- Replay

Replay supports play, pause, speed, scrub, event markers, narration notes, branch points and final incident summary.

---

## 6. 3D and motion rules

Extensive 3D is approved, but it must remain an operational representation.

### 6.1 Allowed uses

- layered jurisdiction and infrastructure scenes;
- route depth and dependency relationships;
- atomic PvP leg locking and commit state;
- RTGS queue pressure and liquidity release;
- message path propagation;
- replay camera transitions between causally related events;
- selected-object inspection.

### 6.2 Prohibited uses

- decorative particles without data meaning;
- constant camera motion;
- neon glow or cyberpunk lighting;
- spinning coins, buildings or generic financial icons;
- motion that implies settlement when only a message was transmitted;
- animations that obscure failure, rollback or uncertainty;
- unbounded background GPU consumption.

### 6.3 Motion grammar

Use precision-mechanical motion:

- lock / unlock;
- reserve / release;
- queue / advance;
- validate / reject;
- pair / commit;
- rollback / isolate;
- reconcile / close.

Every animation must answer at least one question:

- What changed?
- Why did it change?
- Which system caused it?
- What is blocked?
- What can the operator do next?

### 6.4 Performance and fallback

- target 60 fps on supported desktop hardware;
- maintain a usable 30 fps floor under dense scenes;
- pause or reduce animation when the tab is not active;
- use level-of-detail, instancing and aggregation;
- provide Reduced Motion support;
- provide a complete 2D equivalent for every operationally important 3D view;
- automatically downgrade scene complexity on constrained hardware;
- never block payment operations while visual assets initialise.

---

## 7. Priority visualisations

### 7.1 Global cross-border payment situation map

Required layers:

- jurisdiction;
- institution;
- clearing network;
- payment corridor;
- aggregate volume;
- settlement state;
- policy restriction;
- active incident;
- replay event.

The map must distinguish message movement, value movement and final settlement. They are not rendered as the same line.

### 7.2 UETR lifecycle track

A payment workspace combines:

- lifecycle states;
- system events;
- SLA deadline;
- cases;
- copies;
- validation findings;
- route decisions;
- settlement state;
- audit evidence.

The lifecycle is a causal track, not a decorative stepper. Selecting an event reveals source system, timestamp, payload reference, policy decision and operator action.

### 7.3 RTGS liquidity and queue view

Required concepts:

- opening balance;
- current balance;
- reserved balance;
- available liquidity;
- queued outgoing value;
- expected incoming value;
- payment priority;
- release dependencies;
- no-overdraft constraint.

The visualisation must show which incoming settlement can release which queued payments.

### 7.4 DNS net-settlement matrix

Required concepts:

- bilateral gross obligations;
- net participant positions;
- liquidity required before netting;
- liquidity required after netting;
- savings ratio;
- insufficient-funds participant;
- batch finality state.

### 7.5 Atomic PvP sequence

Required stages:

1. quote validation;
2. policy authorization;
3. debit-leg reserve;
4. credit-leg reserve;
5. both legs locked;
6. atomic commit;
7. settlement confirmation.

Failure on either side visibly rolls back both legs. The UI must not animate success until the backend state confirms atomic commit.

### 7.6 Multi-CBDC policy matrix

The matrix exposes:

- source jurisdiction;
- destination jurisdiction;
- permitted status;
- amount ceiling;
- purpose restrictions;
- data-residency rule;
- required participant role;
- decision explanation.

### 7.7 ISO 20022 structure explorer

The explorer renders:

- Business Application Header;
- Group Header;
- debtor and creditor;
- debtor and creditor agents;
- settlement information;
- remittance;
- profile-specific requirements;
- field lineage.

Validation findings navigate directly to the affected node and show rule source, severity, explanation and remediation.

### 7.8 Message and Transaction Copy diff

The diff presents:

- additions;
- removals;
- modifications;
- source party;
- reason;
- payload hash;
- previous hash;
- chain position;
- integrity result.

---

## 8. Replay and scenario engine

The replay engine is a product capability, not a presentation-only slideshow.

Initial scenarios:

1. normal cross-border payment;
2. SR2026 address validation failure;
3. RTGS liquidity shortage and later release;
4. DNS batch blocked by one participant;
5. PvP second-leg failure and atomic rollback;
6. UETR SLA breach and investigation escalation;
7. message-copy integrity failure;
8. jurisdiction policy rejection.

A replay package contains:

- deterministic event stream;
- virtual clock;
- actor and system metadata;
- state snapshots;
- explanatory annotations;
- camera and focus cues;
- expected final state;
- verification assertions.

Replay must use the same visual components as live mode to prevent a separate, misleading demo-only product.

---

## 9. Frontend architecture

### 9.1 Foundation

- Vite
- React
- TypeScript with strict checks
- route-based code splitting
- typed API client generated or maintained from backend contracts
- query cache for server state
- isolated local UI state
- schema validation at external data boundaries
- internationalisation from the first migration batch

### 9.2 Layering

```text
src/
  app/             application shell, routing, providers
  auth/            identity, roles, attributes, policy decisions
  api/             typed clients and transport
  design/          tokens, primitives, themes, typography
  domains/         payments, settlement, standards, cbdc, risk
  visualizations/  2D/3D scenes, charts, timelines and matrices
  replay/          virtual clock, event stream and scenario runtime
  i18n/            Chinese and English resources
  testing/         fixtures, accessibility and visual regression helpers
```

### 9.3 Scene isolation

The 3D renderer must be isolated behind a domain-neutral scene adapter. Business components publish semantic scene objects such as `PaymentRoute`, `SettlementLeg`, `LiquidityPressure` and `PolicyBlock`, rather than directly manipulating meshes.

This permits:

- replacement of the renderer;
- 2D fallback;
- deterministic replay;
- unit testing without WebGL;
- accessibility descriptions;
- performance profiling by scene type.

---

## 10. RBAC/ABAC integration

The backend is the authority.

The frontend consumes a decision envelope containing:

- subject;
- action;
- resource;
- result;
- reasons;
- obligations;
- redactions;
- decision ID;
- policy version.

The UI must:

- render denied actions as unavailable with an explanation when disclosure is permitted;
- apply required redaction and masking;
- request step-up approval when returned as an obligation;
- attach decision IDs to consequential user actions;
- refresh permissions after role, attribute or environment changes;
- avoid caching authorization beyond the backend-defined validity period.

The frontend must not infer policy from role names alone.

---

## 11. Accessibility and institutional usability

- full keyboard access for operational workflows;
- visible focus state;
- Reduced Motion support;
- colour-independent status encoding;
- textual alternative for every map, network and 3D state;
- tabular access to underlying visualised data;
- screen-reader announcements for state changes;
- Chinese and English layouts tested independently;
- dates, currencies and numbers formatted by locale and business convention;
- no critical information available only on hover.

---

## 12. Delivery roadmap

### Phase 0 — Contract and inventory

- map every existing frontend page to v3 backend capability;
- inventory APIs and missing read endpoints;
- define identity, RBAC and ABAC decision contracts;
- define visualisation domain models;
- create representative datasets and replay fixtures.

### Phase 1 — React foundation and institutional design system

- introduce Vite + React + TypeScript;
- preserve backend serving and deployment compatibility;
- implement themes, typography, spacing and data-table primitives;
- implement Chinese / English switching;
- implement application shell and workflow navigation;
- establish accessibility and visual regression checks.

### Phase 2 — Command Center

- central geographic / infrastructure scene;
- cross-border payment volume hierarchy;
- live and historical controls;
- intervention rail;
- network status and settlement summary;
- adaptive 3D/2D renderer.

### Phase 3 — Payment and standards workspaces

- payment worklist;
- UETR lifecycle;
- payment split view;
- ISO 20022 structure explorer;
- validation findings;
- Transaction Copy diff and integrity.

### Phase 4 — Settlement visualisation

- RTGS liquidity and queue;
- DNS matrix;
- FX quotes;
- PvP atomic sequence;
- CIPS route inspection.

### Phase 5 — Policy, investigations and replay

- jurisdiction policy matrix;
- investigation evidence graph;
- full scenario runtime;
- incident replay and report;
- role-aware workspace defaults.

### Phase 6 — Production hardening

- WebGL and rendering performance budgets;
- failure and degraded-mode testing;
- accessibility audit;
- security review;
- observability;
- end-to-end tests;
- institutional acceptance scenarios.

---

## 13. Acceptance criteria

The redesign is not complete until:

1. all major v3 backend domains have an intentional frontend location;
2. the homepage is not a card grid;
3. Chinese and English are complete and switchable;
4. Daylight and Operations Dark are independently designed;
5. a user can inspect a payment from executive aggregate to UETR-level evidence;
6. the eight priority visualisations are implemented with underlying tabular access;
7. live and replay modes use the same state components;
8. backend RBAC/ABAC controls every protected action and field;
9. every meaningful 3D view has reduced-motion and 2D fallbacks;
10. the application remains usable when 3D rendering fails;
11. visual regression, accessibility and end-to-end checks run in CI;
12. no forbidden visual patterns are introduced;
13. the independent sandbox and non-certification boundary remains explicit.

---

## 14. Immediate implementation batch

The first implementation PR should remain deliberately narrow:

1. add the Vite + React + TypeScript application foundation;
2. preserve the current frontend behind a temporary legacy route or build flag;
3. implement the new application shell and workflow navigation;
4. implement Daylight and Operations Dark tokens;
5. implement Chinese / English resources;
6. add an authorization-context client for backend RBAC/ABAC decisions;
7. create a static Command Center composition using representative data;
8. establish unit, accessibility, build and end-to-end CI gates.

The first batch must not attempt all eight visualisations. It creates the architecture and visual discipline that prevent later screens from becoming isolated demos.
