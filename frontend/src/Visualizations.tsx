import { useMemo, useState, type CSSProperties } from "react";
import { formatMoney } from "./fixtures";
import { t } from "./i18n";
import type { DiffEntry, DnsMatrix, IsoNode, LifecycleStage, LiquidityAccount, Locale, PolicyCell, PvpStage } from "./types";

const statusText = (locale: Locale, value: string): string => {
  const labels: Record<string, [string, string]> = {
    allow: ["Allowed", "允许"], limited: ["Limited", "受限"], deny: ["Blocked", "阻断"],
    complete: ["Complete", "完成"], active: ["Active", "进行中"], waiting: ["Waiting", "等待"], rollback: ["Rollback", "回滚"],
  };
  const pair = labels[value];
  return pair ? pair[locale === "zh" ? 1 : 0] : value;
};

export function UetrLifecycle({ stages, locale }: { stages: LifecycleStage[]; locale: Locale }) {
  const [selected, setSelected] = useState(stages.find((stage) => stage.status === "active") ?? stages[0]);
  return <section className="visual-section" aria-labelledby="uetr-title">
    <header className="section-header"><div><p className="eyebrow">UETR · 2f7446bf-8c61-4cd9-96ac-9d2b3f4a0d81</p><h2 id="uetr-title">{t(locale, "uetrLifecycle")}</h2></div><span className="plain-status">SLA 01:42:18</span></header>
    <div className="lifecycle-track">{stages.map((stage, index) => <button className={`lifecycle-stage ${stage.status} ${selected?.code === stage.code ? "selected" : ""}`} key={stage.code} type="button" onClick={() => setSelected(stage)}><span className="stage-index">{String(index + 1).padStart(2, "0")}</span><span className="stage-copy"><strong>{locale === "zh" ? stage.label_zh : stage.label}</strong><small>{stage.system} · {stage.time}</small></span></button>)}</div>
    {selected && <div className="evidence-line" aria-live="polite"><span>{selected.system}</span><strong>{locale === "zh" ? selected.reason_zh : selected.reason}</strong><code>{selected.code}</code></div>}
  </section>;
}

export function RtgsLiquidity({ accounts, locale }: { accounts: LiquidityAccount[]; locale: Locale }) {
  const max = Math.max(...accounts.map((account) => account.opening + account.expected_incoming));
  return <section className="visual-section" aria-labelledby="rtgs-title">
    <header className="section-header"><div><p className="eyebrow">CIPS · RTGS · NO OVERDRAFT</p><h2 id="rtgs-title">{t(locale, "rtgs")}</h2></div></header>
    <div className="liquidity-table" role="table" aria-label="RTGS liquidity positions">
      <div className="liquidity-row liquidity-head" role="row"><span>{locale === "zh" ? "参与者" : "Participant"}</span><span>{locale === "zh" ? "余额结构" : "Position"}</span><span>{locale === "zh" ? "可用" : "Available"}</span><span>{locale === "zh" ? "队列" : "Queued"}</span><span>{locale === "zh" ? "预期入账" : "Incoming"}</span></div>
      {accounts.map((account) => { const available = Math.max(account.balance - account.reserved, 0); return <div className="liquidity-row" role="row" key={account.participant}><code>{account.participant}</code><div className="liquidity-bar" aria-label={`${account.participant} liquidity composition`}><span className="balance" style={{ width: `${(available / max) * 100}%` }} /><span className="reserved" style={{ width: `${(account.reserved / max) * 100}%` }} /><span className="queued" style={{ width: `${(account.queued / max) * 100}%` }} /></div><strong>{formatMoney(available, account.currency, locale === "zh" ? "zh-CN" : "en-US")}</strong><span className={account.queued > available ? "negative" : ""}>{formatMoney(account.queued, account.currency, locale === "zh" ? "zh-CN" : "en-US")}</span><span>{formatMoney(account.expected_incoming, account.currency, locale === "zh" ? "zh-CN" : "en-US")}</span></div>; })}
    </div>
    <div className="dependency-note"><span className="dependency-arrow">→</span><p>{locale === "zh" ? "HK-B 的 1.90 亿预期入账将释放两笔优先级支付；系统保持无透支。" : "HK-B's expected CNY 190m incoming settlement releases two priority payments while preserving the no-overdraft invariant."}</p></div>
  </section>;
}

export function DnsNetting({ dns, locale }: { dns: DnsMatrix; locale: Locale }) {
  return <section className="visual-section" aria-labelledby="dns-title">
    <header className="section-header"><div><p className="eyebrow">CIPS · DNS · BATCH 2026-07-22-03</p><h2 id="dns-title">{t(locale, "dns")}</h2></div><span className="plain-status warning">{dns.state}</span></header>
    <div className="netting-summary"><div><small>{t(locale, "grossRequired")}</small><strong>{formatMoney(dns.gross_required, "CNY", locale === "zh" ? "zh-CN" : "en-US")}</strong></div><span className="mechanical-arrow">→</span><div><small>{t(locale, "netRequired")}</small><strong>{formatMoney(dns.net_required, "CNY", locale === "zh" ? "zh-CN" : "en-US")}</strong></div><div className="savings-ratio"><small>{t(locale, "savings")}</small><strong>{dns.savings_ratio.toFixed(2)}%</strong></div></div>
    <div className="matrix-wrap"><table className="matrix-table"><caption>{locale === "zh" ? "双边总额义务（百万元人民币）" : "Bilateral gross obligations (CNY millions)"}</caption><thead><tr><th>From / To</th>{dns.participants.map((participant) => <th key={participant}>{participant}</th>)}<th>Net</th></tr></thead><tbody>{dns.participants.map((participant, row) => <tr key={participant} className={dns.blocked_participant === participant ? "blocked-row" : ""}><th>{participant}</th>{dns.obligations[row]?.map((value, column) => <td key={`${row}-${column}`} className={row === column ? "diagonal" : value > 300 ? "high" : ""}>{value || "—"}</td>)}<td className={(dns.net_positions[row] ?? 0) < 0 ? "negative" : "positive"}>{dns.net_positions[row] ?? 0}</td></tr>)}</tbody></table></div>
  </section>;
}

export function PvpSequence({ stages, locale, replayProgress }: { stages: PvpStage[]; locale: Locale; replayProgress: number }) {
  const activeIndex = Math.min(stages.length - 1, Math.floor(replayProgress * stages.length));
  return <section className="visual-section" aria-labelledby="pvp-title">
    <header className="section-header"><div><p className="eyebrow">CNY / HKD · QUOTE Q-91 · ATOMIC STATE MACHINE</p><h2 id="pvp-title">{t(locale, "pvp")}</h2></div><span className="plain-status">VERSION {activeIndex + 1}</span></header>
    <div className="pvp-machine"><div className={`settlement-leg ${activeIndex >= 2 ? "locked" : ""}`}><span>CNY</span><strong>¥ 10,000,000</strong><small>{activeIndex >= 2 ? (locale === "zh" ? "已预留" : "Reserved") : (locale === "zh" ? "待校验" : "Pending")}</small></div><div className="pvp-lock"><div className={`lock-body ${activeIndex >= 4 ? "engaged" : ""}`}><span /></div><small>{activeIndex >= 5 ? (locale === "zh" ? "原子提交" : "Atomic commit") : (locale === "zh" ? "等待双腿锁定" : "Awaiting both locks")}</small></div><div className={`settlement-leg ${activeIndex >= 3 ? "locked" : ""}`}><span>HKD</span><strong>$ 10,785,000</strong><small>{activeIndex >= 3 ? (locale === "zh" ? "已预留" : "Reserved") : (locale === "zh" ? "待校验" : "Pending")}</small></div></div>
    <ol className="pvp-stages">{stages.map((stage, index) => { const visualState = index < activeIndex ? "complete" : index === activeIndex ? "active" : stage.state; return <li key={stage.code} className={visualState}><span>{String(index + 1).padStart(2, "0")}</span><strong>{locale === "zh" ? stage.label_zh : stage.label}</strong><small>{statusText(locale, visualState)}</small></li>; })}</ol>
  </section>;
}

export function PolicyMatrix({ cells, locale }: { cells: PolicyCell[]; locale: Locale }) {
  const jurisdictions = useMemo(() => [...new Set(cells.flatMap((cell) => [cell.source, cell.destination]))], [cells]);
  const lookup = (source: string, destination: string) => cells.find((cell) => cell.source === source && cell.destination === destination);
  const [selected, setSelected] = useState<PolicyCell | undefined>(cells[0]);
  return <section className="visual-section" aria-labelledby="policy-title">
    <header className="section-header"><div><p className="eyebrow">RBAC / ABAC · POLICY UI-V4</p><h2 id="policy-title">{t(locale, "policyMatrix")}</h2></div></header>
    <div className="policy-layout"><table className="policy-table"><thead><tr><th>{t(locale, "source")} ↓ / {t(locale, "destination")} →</th>{jurisdictions.map((jurisdiction) => <th key={jurisdiction}>{jurisdiction}</th>)}</tr></thead><tbody>{jurisdictions.map((source) => <tr key={source}><th>{source}</th>{jurisdictions.map((destination) => { const cell = lookup(source, destination); if (source === destination) return <td key={destination} className="not-applicable">—</td>; if (!cell) return <td key={destination} className="unknown">N/A</td>; return <td key={destination}><button type="button" className={`policy-cell ${cell.status}`} onClick={() => setSelected(cell)}><span>{statusText(locale, cell.status)}</span><small>{cell.ceiling ? formatMoney(cell.ceiling, "CNY", locale === "zh" ? "zh-CN" : "en-US") : "—"}</small></button></td>; })}</tr>)}</tbody></table>{selected && <aside className="policy-explanation"><p className="eyebrow">DECISION CONTEXT</p><h3>{selected.source} → {selected.destination}</h3><dl><div><dt>Status</dt><dd>{statusText(locale, selected.status)}</dd></div><div><dt>Ceiling</dt><dd>{selected.ceiling ? formatMoney(selected.ceiling, "CNY", locale === "zh" ? "zh-CN" : "en-US") : "—"}</dd></div><div><dt>Purpose</dt><dd>{selected.purposes.join(", ") || "—"}</dd></div><div><dt>Residency</dt><dd>{selected.residency}</dd></div></dl><p>{locale === "zh" ? selected.reason_zh : selected.reason}</p></aside>}</div>
  </section>;
}

function IsoBranch({ node, depth = 0, onSelect }: { node: IsoNode; depth?: number; onSelect: (node: IsoNode) => void }) {
  return <li className={node.severity ? `has-${node.severity}` : ""} style={{ "--depth": depth } as CSSProperties}><button type="button" onClick={() => onSelect(node)}><span className="tree-marker" /><span><strong>{node.label}</strong><small>{node.path}</small></span><code>{node.value || "∅"}</code></button>{node.children && <ul>{node.children.map((child) => <IsoBranch key={child.path} node={child} depth={depth + 1} onSelect={onSelect} />)}</ul>}</li>;
}

export function IsoExplorer({ nodes, locale }: { nodes: IsoNode[]; locale: Locale }) {
  const [selected, setSelected] = useState<IsoNode>(nodes[0] ?? { path: "", label: "", value: "", required: false });
  return <section className="visual-section" aria-labelledby="iso-title"><header className="section-header"><div><p className="eyebrow">pacs.008.001.13 · CBPR+ SR2026</p><h2 id="iso-title">{t(locale, "isoExplorer")}</h2></div><span className="plain-status warning">1 WARNING</span></header><div className="iso-layout"><ul className="iso-tree">{nodes.map((node) => <IsoBranch key={node.path} node={node} onSelect={setSelected} />)}</ul><aside className="node-inspector"><p className="eyebrow">FIELD INSPECTOR</p><h3>{selected.label}</h3><code>{selected.path}</code><dl><div><dt>Value</dt><dd>{selected.value || "Empty"}</dd></div><div><dt>Required</dt><dd>{selected.required ? "Yes" : "No"}</dd></div>{selected.rule && <div><dt>{t(locale, "rule")}</dt><dd>{selected.rule}</dd></div>}</dl>{selected.severity && <p className="finding-text">{locale === "zh" ? "当前字段触发配置规则。选择该字段可进行定向修复。" : "This field triggers a profile rule. The selected node is the remediation target."}</p>}</aside></div></section>;
}

export function MessageDiff({ entries, locale }: { entries: DiffEntry[]; locale: Locale }) {
  const [selected, setSelected] = useState(entries.find((entry) => entry.kind !== "unchanged") ?? entries[0]);
  return <section className="visual-section" aria-labelledby="diff-title"><header className="section-header"><div><p className="eyebrow">TRANSACTION COPY · HASH CHAIN VALID</p><h2 id="diff-title">{t(locale, "messageDiff")}</h2></div><span className="plain-status success">INTEGRITY VERIFIED</span></header><div className="diff-layout"><div className="diff-list">{entries.map((entry, index) => <button type="button" key={entry.path} className={`diff-row ${entry.kind} ${selected?.path === entry.path ? "selected" : ""}`} onClick={() => setSelected(entry)}><span>{String(index + 1).padStart(2, "0")}</span><code>{entry.path}</code><strong>{entry.kind}</strong></button>)}</div>{selected && <aside className="diff-inspector"><div className="hash-chain"><code>{selected.previous_hash ?? "GENESIS"}</code><span>→</span><code>{selected.payload_hash}</code></div><div className="before-after"><div><small>{t(locale, "before")}</small><pre>{selected.before ?? "∅"}</pre></div><div><small>{t(locale, "after")}</small><pre>{selected.after ?? "∅"}</pre></div></div><dl><div><dt>Source party</dt><dd>{selected.source_party}</dd></div><div><dt>Reason</dt><dd>{selected.reason}</dd></div></dl></aside>}</div></section>;
}
