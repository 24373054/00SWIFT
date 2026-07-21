export type Locale = "en" | "zh";
export type ThemeName = "daylight" | "operations";
export type ViewMode = "geographic" | "infrastructure" | "hybrid";
export type WorkspaceId =
  | "command"
  | "payments"
  | "investigations"
  | "settlement"
  | "standards"
  | "digital-currency"
  | "risk-policy"
  | "developer"
  | "administration";

export interface Workspace {
  id: WorkspaceId;
  label: string;
  label_zh: string;
  enabled: boolean;
  reason?: string;
}

export interface PolicyDecision {
  decision_id: string;
  subject: string;
  action: string;
  resource: string;
  result: "allow" | "deny";
  reasons: string[];
  obligations: string[];
  redactions: string[];
  policy_version: string;
}

export interface BootstrapPayload {
  product: {
    name: string;
    version: string;
    environment: string;
    data_mode: "live" | "representative";
    independent_sandbox: boolean;
  };
  identity: {
    subject: string;
    role: string;
    role_label: string;
    role_label_zh: string;
    source: string;
  };
  workspaces: Workspace[];
  permissions: string[];
  decision: PolicyDecision;
}

export interface Corridor {
  id: string;
  from: string;
  to: string;
  from_country: string;
  to_country: string;
  volume: number;
  currency: string;
  state: "settled" | "moving" | "queued" | "blocked";
  channel: string;
  message_state: string;
  value_state: string;
  settlement_state: string;
  start: [number, number, number];
  end: [number, number, number];
}

export interface Intervention {
  id: string;
  severity: "critical" | "warning" | "information";
  title: string;
  title_zh: string;
  owner: string;
  due: string;
  reason: string;
  reason_zh: string;
}

export interface NetworkEvent {
  id: string;
  time: string;
  system: string;
  type: string;
  state: string;
  text: string;
  text_zh: string;
}

export interface LiquidityAccount {
  participant: string;
  opening: number;
  balance: number;
  reserved: number;
  queued: number;
  expected_incoming: number;
  currency: string;
}

export interface DnsMatrix {
  participants: string[];
  obligations: number[][];
  net_positions: number[];
  gross_required: number;
  net_required: number;
  savings_ratio: number;
  blocked_participant?: string;
  state: string;
}

export interface LifecycleStage {
  code: string;
  label: string;
  label_zh: string;
  system: string;
  time: string;
  status: "completed" | "active" | "pending" | "blocked";
  reason: string;
  reason_zh: string;
}

export interface PvpStage {
  code: string;
  label: string;
  label_zh: string;
  state: "complete" | "active" | "waiting" | "rollback";
}

export interface PolicyCell {
  source: string;
  destination: string;
  status: "allow" | "limited" | "deny";
  ceiling: number;
  purposes: string[];
  residency: string;
  reason: string;
  reason_zh: string;
}

export interface IsoNode {
  path: string;
  label: string;
  value: string;
  required: boolean;
  severity?: "error" | "warning";
  rule?: string;
  children?: IsoNode[];
}

export interface DiffEntry {
  path: string;
  kind: "added" | "removed" | "modified" | "unchanged";
  before: string | null;
  after: string | null;
  source_party: string;
  reason: string;
  payload_hash: string;
  previous_hash: string | null;
}

export interface ReplayEvent {
  at: number;
  system: string;
  title: string;
  title_zh: string;
  detail: string;
  detail_zh: string;
  state: string;
  focus: WorkspaceId;
}

export interface ReplayScenario {
  id: string;
  name: string;
  name_zh: string;
  duration: number;
  expected_state: string;
  events: ReplayEvent[];
}

export interface CommandCenterPayload {
  generated_at: string;
  data_mode: "live" | "representative";
  totals: {
    cross_border_volume: number;
    currency: string;
    active_payments: number;
    queued_value: number;
    open_cases: number;
    available_liquidity: number;
    reserved_liquidity: number;
    system_availability: number;
  };
  corridors: Corridor[];
  interventions: Intervention[];
  events: NetworkEvent[];
  liquidity: LiquidityAccount[];
  dns: DnsMatrix;
  lifecycle: LifecycleStage[];
  pvp: PvpStage[];
  policy_matrix: PolicyCell[];
  iso_tree: IsoNode[];
  message_diff: DiffEntry[];
  scenarios: ReplayScenario[];
}
