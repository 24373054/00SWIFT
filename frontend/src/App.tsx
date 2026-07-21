import { useEffect, useMemo, useState } from "react";
import { loadBootstrap, loadCommandCenter } from "./api";
import { fallbackBootstrap, fallbackCommandCenter, replayStateAt, roles } from "./fixtures";
import { t } from "./i18n";
import { NetworkScene } from "./NetworkScene";
import { DnsNetting, ExecutiveMetrics, IsoExplorer, MessageDiff, PolicyMatrix, PvpSequence, RtgsLiquidity, UetrLifecycle } from "./Visualizations";
import type { BootstrapPayload, CommandCenterPayload, Locale, ReplayScenario, ThemeName, ViewMode, WorkspaceId } from "./types";

const workspaceMessageKey: Record<WorkspaceId, Parameters<typeof t>[1]> = {
  command: "command", payments: "payments", investigations: "investigations", settlement: "settlement", standards: "standards",
  "digital-currency": "digitalCurrency", "risk-policy": "riskPolicy", developer: "developer", administration: "administration",
};

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

function InterventionRail({ data, locale }: { data: CommandCenterPayload; locale: Locale }) {
  return <aside className="side-rail intervention-rail" aria-labelledby="intervention-title"><header><p className="eyebrow">HUMAN CONTROL</p><h2 id="intervention-title">{t(locale, "interventions")}</h2></header><div className="rail-list">{data.interventions.map((item) => <article key={item.id} className={`intervention ${item.severity}`}><div className="intervention-top"><code>{item.id}</code><span>{item.due}</span></div><h3>{locale === "zh" ? item.title_zh : item.title}</h3><p>{locale === "zh" ? item.reason_zh : item.reason}</p><footer><span>{t(locale, "owner")}</span><strong>{item.owner}</strong></footer></article>)}</div></aside>;
}

function LiquidityRail({ data, locale }: { data: CommandCenterPayload; locale: Locale }) {
  const available = data.totals.available_liquidity;
  const reserved = data.totals.reserved_liquidity;
  const utilization = (reserved / Math.max(available + reserved, 1)) * 100;
  return <aside className="side-rail liquidity-rail" aria-labelledby="liquidity-title"><header><p className="eyebrow">CIPS · RTGS</p><h2 id="liquidity-title">{t(locale, "liquidity")}</h2></header><div className="liquidity-gauge"><div className="gauge-track"><span style={{ width: `${utilization}%` }} /></div><div className="gauge-values"><strong>{utilization.toFixed(1)}%</strong><span>{locale === "zh" ? "已预留占比" : "Reserved share"}</span></div></div><dl className="rail-metrics"><div><dt>{locale === "zh" ? "可用" : "Available"}</dt><dd>¥ {(available / 1_000_000_000).toFixed(2)}B</dd></div><div><dt>{locale === "zh" ? "已预留" : "Reserved"}</dt><dd>¥ {(reserved / 1_000_000_000).toFixed(2)}B</dd></div><div><dt>{locale === "zh" ? "排队" : "Queued"}</dt><dd>¥ {(data.totals.queued_value / 1_000_000).toFixed(0)}M</dd></div></dl><div className="corridor-register">{data.corridors.map((corridor) => <div key={corridor.id}><span className={`state-mark ${corridor.state}`} /><strong>{corridor.from_country} → {corridor.to_country}</strong><small>{corridor.channel}</small><code>{(corridor.volume / 1_000_000_000).toFixed(2)}B</code></div>)}</div></aside>;
}

function EventStream({ data, locale, scenario, progress }: { data: CommandCenterPayload; locale: Locale; scenario: ReplayScenario; progress: number }) {
  const replayTime = progress * scenario.duration;
  const activeEvents = scenario.events.filter((event) => event.at <= replayTime);
  return <section className="event-stream" aria-labelledby="events-title"><header className="section-header"><div><p className="eyebrow">TRACEABLE OPERATIONS</p><h2 id="events-title">{t(locale, "eventStream")}</h2></div><code>{replayStateAt(scenario, replayTime)}</code></header><div className="event-grid">{(activeEvents.length ? activeEvents.slice(-4).reverse() : data.events).map((event) => { const isReplay = "at" in event; return <article key={isReplay ? `${event.system}-${event.at}` : event.id}><time>{isReplay ? `T+${event.at}s` : event.time}</time><strong>{event.system}</strong><span>{isReplay ? (locale === "zh" ? event.title_zh : event.title) : (locale === "zh" ? event.text_zh : event.text)}</span><code>{event.state}</code></article>; })}</div></section>;
}

function ReplayControls({ locale, scenarios, scenario, onScenario, progress, onProgress, playing, onPlaying }: { locale: Locale; scenarios: ReplayScenario[]; scenario: ReplayScenario; onScenario: (scenario: ReplayScenario) => void; progress: number; onProgress: (value: number) => void; playing: boolean; onPlaying: (value: boolean) => void }) {
  const current = progress * scenario.duration;
  return <div className="replay-control" aria-label="Scenario replay controls"><button type="button" className="primary-control" onClick={() => onPlaying(!playing)}>{playing ? t(locale, "pause") : t(locale, "play")}</button><label><span className="sr-only">Scenario</span><select value={scenario.id} onChange={(event) => { const selected = scenarios.find((item) => item.id === event.target.value); if (selected) onScenario(selected); }}>{scenarios.map((item) => <option key={item.id} value={item.id}>{locale === "zh" ? item.name_zh : item.name}</option>)}</select></label><input type="range" min="0" max="1000" value={Math.round(progress * 1000)} onChange={(event) => onProgress(Number(event.target.value) / 1000)} aria-label="Replay position" /><code>T+{current.toFixed(1)}s / {scenario.duration}s</code></div>;
}

function CommandCenter({ data, locale, theme, viewMode, setViewMode, spatial, setSpatial, scenario, progress, playing, setPlaying, setProgress, setScenario }: { data: CommandCenterPayload; locale: Locale; theme: ThemeName; viewMode: ViewMode; setViewMode: (mode: ViewMode) => void; spatial: boolean; setSpatial: (value: boolean) => void; scenario: ReplayScenario; progress: number; playing: boolean; setPlaying: (value: boolean) => void; setProgress: (value: number) => void; setScenario: (scenario: ReplayScenario) => void }) {
  return <div className="workspace command-workspace"><ExecutiveMetrics data={data} locale={locale} /><div className="command-grid"><InterventionRail data={data} locale={locale} /><section className="situation-stage" aria-labelledby="situation-title"><header className="stage-header"><div><p className="eyebrow">LIVE NETWORK / SCENARIO REPLAY</p><h1 id="situation-title">{t(locale, "command")}</h1></div><div className="segmented-controls" aria-label="Scene view mode">{(["geographic", "infrastructure", "hybrid"] as const).map((mode) => <button key={mode} type="button" className={viewMode === mode ? "active" : ""} onClick={() => setViewMode(mode)}>{t(locale, mode)}</button>)}<button type="button" className={spatial ? "active" : ""} onClick={() => setSpatial(!spatial)}>{spatial ? t(locale, "spatialMode") : t(locale, "reducedMotion")}</button></div></header><NetworkScene corridors={data.corridors} theme={theme} mode={viewMode} replayProgress={progress} spatial={spatial} locale={locale} /><div className="scene-legend"><span><i className="state-mark settled" />{locale === "zh" ? "最终结算" : "Final settlement"}</span><span><i className="state-mark moving" />{locale === "zh" ? "价值锁定" : "Value locked"}</span><span><i className="state-mark queued" />{locale === "zh" ? "排队" : "Queued"}</span><span><i className="state-mark blocked" />{locale === "zh" ? "策略阻断" : "Policy blocked"}</span></div><ReplayControls locale={locale} scenarios={data.scenarios} scenario={scenario} onScenario={setScenario} progress={progress} onProgress={setProgress} playing={playing} onPlaying={setPlaying} /></section><LiquidityRail data={data} locale={locale} /></div><EventStream data={data} locale={locale} scenario={scenario} progress={progress} /></div>;
}

function WorkspaceView({ workspace, data, locale, replayProgress }: { workspace: WorkspaceId; data: CommandCenterPayload; locale: Locale; replayProgress: number }) {
  switch (workspace) {
    case "payments":
    case "investigations": return <div className="workspace stacked-workspace"><UetrLifecycle stages={data.lifecycle} locale={locale} /><MessageDiff entries={data.message_diff} locale={locale} /></div>;
    case "settlement": return <div className="workspace stacked-workspace"><RtgsLiquidity accounts={data.liquidity} locale={locale} /><DnsNetting dns={data.dns} locale={locale} /><PvpSequence stages={data.pvp} locale={locale} replayProgress={replayProgress} /></div>;
    case "standards": return <div className="workspace stacked-workspace"><IsoExplorer nodes={data.iso_tree} locale={locale} /><MessageDiff entries={data.message_diff} locale={locale} /></div>;
    case "risk-policy":
    case "digital-currency": return <div className="workspace stacked-workspace"><PolicyMatrix cells={data.policy_matrix} locale={locale} /><PvpSequence stages={data.pvp} locale={locale} replayProgress={replayProgress} /></div>;
    case "developer":
    case "administration": return <div className="workspace institutional-empty"><p className="eyebrow">BACKEND-AUTHORITATIVE WORKSPACE</p><h1>{t(locale, workspaceMessageKey[workspace])}</h1><p>{locale === "zh" ? "该工作区已经纳入后端权限模型。后续配置操作必须返回策略决策编号、原因、义务与脱敏字段。" : "This workspace is included in the backend authorization model. Configuration actions must return a policy decision ID, reasons, obligations and redactions."}</p></div>;
    default: return null;
  }
}

export function App() {
  const prefersReducedMotion = useReducedMotion();
  const [locale, setLocale] = useState<Locale>(() => (navigator.language.startsWith("zh") ? "zh" : "en"));
  const [theme, setTheme] = useState<ThemeName>("daylight");
  const [role, setRole] = useState("executive_viewer");
  const [bootstrap, setBootstrap] = useState<BootstrapPayload>(fallbackBootstrap);
  const [data, setData] = useState<CommandCenterPayload>(fallbackCommandCenter);
  const [workspace, setWorkspace] = useState<WorkspaceId>("command");
  const [viewMode, setViewMode] = useState<ViewMode>("hybrid");
  const [spatial, setSpatial] = useState(!prefersReducedMotion);
  const [loading, setLoading] = useState(true);
  const [scenario, setScenario] = useState<ReplayScenario>(fallbackCommandCenter.scenarios[0]!);
  const [progress, setProgress] = useState(0.22);
  const [playing, setPlaying] = useState(true);

  useEffect(() => setSpatial(!prefersReducedMotion), [prefersReducedMotion]);
  useEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.lang = locale === "zh" ? "zh-CN" : "en"; }, [theme, locale]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([loadBootstrap(role), loadCommandCenter(role)]).then(([nextBootstrap, nextData]) => {
      if (!active) return;
      setBootstrap(nextBootstrap); setData(nextData); setScenario(nextData.scenarios[0] ?? fallbackCommandCenter.scenarios[0]!); setLoading(false);
      const currentAllowed = nextBootstrap.workspaces.find((item) => item.id === workspace)?.enabled;
      if (!currentAllowed) setWorkspace("command");
    });
    return () => { active = false; };
  }, [role]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setProgress((current) => current >= 1 ? 0 : Math.min(current + 0.004, 1)), 160);
    return () => window.clearInterval(timer);
  }, [playing, scenario.id]);

  const visibleWorkspaces = useMemo(() => bootstrap.workspaces, [bootstrap.workspaces]);
  const title = t(locale, workspaceMessageKey[workspace]);
  return <div className="app-shell"><aside className="primary-nav"><div className="brand-block"><span className="brand-mark">CB</span><div><strong>{t(locale, "product")}</strong><small>00SWIFT · v{bootstrap.product.version}</small></div></div><nav aria-label="Primary workflow navigation">{visibleWorkspaces.map((item, index) => <button key={item.id} type="button" disabled={!item.enabled} className={workspace === item.id ? "active" : ""} onClick={() => item.enabled && setWorkspace(item.id)} title={item.enabled ? "" : item.reason ?? t(locale, "denied")}><span>{String(index + 1).padStart(2, "0")}</span><strong>{locale === "zh" ? item.label_zh : item.label}</strong>{!item.enabled && <i>—</i>}</button>)}</nav><div className="policy-proof"><small>POLICY DECISION</small><code>{bootstrap.decision.decision_id.slice(0, 18)}</code><span className={bootstrap.decision.result}>{bootstrap.decision.result.toUpperCase()}</span></div></aside><main className="application-main"><header className="top-command-bar"><div className="breadcrumb"><span>00SWIFT</span><b>/</b><strong>{title}</strong></div><div className="system-status"><span className="status-square healthy" />{bootstrap.product.environment.toUpperCase()}<code>{data.generated_at.slice(11, 19)} UTC</code></div><div className="control-cluster"><label><span>{t(locale, "role")}</span><select value={role} onChange={(event) => setRole(event.target.value)}>{roles.map(([value, en, zh]) => <option key={value} value={value}>{locale === "zh" ? zh : en}</option>)}</select></label><label><span>{t(locale, "theme")}</span><select value={theme} onChange={(event) => setTheme(event.target.value as ThemeName)}><option value="daylight">{t(locale, "daylight")}</option><option value="operations">{t(locale, "operations")}</option></select></label><label><span>{t(locale, "language")}</span><select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}><option value="en">English</option><option value="zh">中文</option></select></label></div></header>{loading && <div className="loading-rule" aria-live="polite"><span /></div>}{workspace === "command" ? <CommandCenter data={data} locale={locale} theme={theme} viewMode={viewMode} setViewMode={setViewMode} spatial={spatial} setSpatial={setSpatial} scenario={scenario} progress={progress} playing={playing} setPlaying={setPlaying} setProgress={setProgress} setScenario={(next) => { setScenario(next); setProgress(0); setPlaying(true); }} /> : <WorkspaceView workspace={workspace} data={data} locale={locale} replayProgress={progress} />}<footer className="institutional-boundary"><span>{bootstrap.product.data_mode.toUpperCase()}</span><p>{t(locale, "sandboxBoundary")}</p></footer></main></div>;
}
