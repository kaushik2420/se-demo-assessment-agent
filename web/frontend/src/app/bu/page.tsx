"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string): Promise<any> => api(url);

type Headlines = {
  calls_analyzed: number;
  loss_risk_signals: number;
  blocker_feature_mentions: number;
  high_maturity_prospects: number;
  team_avg_score: number;
  wins_recent_count: number;
  won_total_value: number;
  won_total_count: number;
  open_pipeline_value: number;
  at_risk_value: number;
};

type PipelineRow = { stage: string; count: number; deals_with_value: number; total_value: number };

type CommitteeMember = { name: string; title: string | null; role: string; evidence?: string };
type Win = {
  call_id: string;
  prospect: string;
  use_case: string | null;
  product: string | null;
  se_name: string;
  ae_name: string | null;
  closed_date: string;
  go_live_date: string | null;
  demo_to_close_days: number | null;
  close_to_go_live_days: number | null;
  buying_committee: CommitteeMember[];
  primary_users: string[];
  incumbent: { tool?: string; years_using?: string; experience?: string; switching_reason?: string };
  discovery_source: string | null;
  aha: string | null;
  deal_value: number | null;
  deal_currency: string | null;
  deal_stage: string | null;
  crm_deal_url: string | null;
};

type BUData = {
  headlines: Headlines;
  pipeline_by_stage: PipelineRow[];
  wins: Win[];
  buying_committee: any[];
  deal_velocity: any[];
  incumbent_displacement: any[];
  discovery_source: any[];
  aha_patterns: any[];
};

function fmtMoney(v: number | null | undefined, currency = "USD"): string {
  if (v == null) return "—";
  // Compact display for big numbers, full for small
  if (v >= 1e6) return `${currency} ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${currency} ${(v / 1e3).toFixed(0)}K`;
  return `${currency} ${Number(v).toLocaleString()}`;
}

const ROLE_LABEL: Record<string, string> = {
  champion: "Champion",
  decision_maker: "Decision",
  primary_user: "Primary user",
  secondary_user: "Secondary user",
  it_security: "IT / Security",
  procurement: "Procurement",
  finance: "Finance / CFO",
  exec_sponsor: "Exec sponsor",
  influencer: "Influencer",
};

const ROLE_COLOR: Record<string, string> = {
  champion: "bg-emerald-100 text-emerald-800",
  decision_maker: "bg-rose-100 text-rose-800",
  primary_user: "bg-teal-100 text-teal-800",
  secondary_user: "bg-teal-50 text-teal-700",
  it_security: "bg-slate-100 text-slate-700",
  procurement: "bg-orange-100 text-orange-800",
  finance: "bg-amber-100 text-amber-800",
  exec_sponsor: "bg-violet-100 text-violet-800",
  influencer: "bg-blue-100 text-blue-800",
};

function fmtDate(s: string | null): string {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return s; }
}

function exportCsv(name: string, headers: string[], rows: (string | number | null | undefined)[][]) {
  // String(null) → "null" and String(undefined) → "undefined" — neither is what
  // we want in a spreadsheet. Coerce both to "" before serialising.
  const esc = (v: unknown) => `"${(v == null ? "" : String(v)).replace(/"/g, '""').replace(/\n/g, " ")}"`;
  const csv = [headers.map(esc).join(","), ...rows.map(r => r.map(esc).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `bu-${name}-${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(url);
}

export default function BUPage() {
  const { data, error, isLoading } = useSWR<BUData>("/dashboard/bu", fetcher);

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading BU dashboard…</div></>);
  if (error)     return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);
  if (!data)     return (<><TopNav /><div className="p-10 text-ss-navy-soft">No data.</div></>);

  const h = data.headlines;

  return (
    <>
      <TopNav />
      <main className="max-w-[1400px] mx-auto p-8">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">BU Health Dashboard</h1>
            <p className="text-ss-navy-soft mt-1">
              Deal anatomy, market signal, team craft. Snapshot as of {new Date().toLocaleDateString()}.
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => window.print()}
              className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded-lg text-sm hover:bg-ss-cream transition">
              ⎙ Print / PDF
            </button>
          </div>
        </div>

        {/* ─── Headlines (2 rows: scoreboard + dollar-weighted) ─── */}
        <div className="bg-white border border-ss-cyan-soft rounded-xl mb-6 overflow-hidden">
          <div className="grid grid-cols-5 border-b border-ss-cyan-soft">
            <Stat label="Calls analyzed" value={h.calls_analyzed} />
            <Stat label="Loss-risk signals" value={h.loss_risk_signals} />
            <Stat label="Blocker feature mentions" value={h.blocker_feature_mentions} />
            <Stat label="High maturity prospects" value={h.high_maturity_prospects} />
            <Stat label="Team avg score" value={h.team_avg_score.toFixed(2)} />
          </div>
          <div className="grid grid-cols-4">
            <Stat label={<>Won this period <span className="text-emerald-600">($)</span></>}
                  value={fmtMoney(h.won_total_value)}
                  sub={`${h.won_total_count} deals`} />
            <Stat label={<>Open pipeline <span className="text-ss-teal-deep">($)</span></>}
                  value={fmtMoney(h.open_pipeline_value)} />
            <Stat label={<>Pipeline at risk <span className="text-red-600">($)</span></>}
                  value={fmtMoney(h.at_risk_value)}
                  sub="open deals with loss-risk signals" />
            <Stat label="Avg deal size"
                  value={h.won_total_count
                    ? fmtMoney(h.won_total_value / h.won_total_count)
                    : "—"} />
          </div>
          <div className="px-4 py-2 text-[10px] text-ss-navy-soft italic border-t border-ss-cyan-soft">
            $-weighted metrics sum across deals regardless of currency. For accurate totals, SEs should enter USD-equivalent
            in the deal value field. HubSpot integration removes the manual step.
          </div>
        </div>

        {/* ─── Pipeline by stage ─── */}
        <Panel title="Pipeline by stage (HubSpot data — manual)"
               subtitle={`${data.pipeline_by_stage.reduce((s, p) => s + p.count, 0)} deals across stages`}
               onExport={() => exportCsv("pipeline-by-stage", [
                 "Stage", "Deals", "Deals with value entered", "Total value"
               ], data.pipeline_by_stage.map(p => [
                 p.stage, p.count, p.deals_with_value, p.total_value
               ]))}>
          <Table headers={["Stage", "Deals", "With $ entered", "Total value"]}>
            {data.pipeline_by_stage.map(p => (
              <tr key={p.stage} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5 font-semibold text-ss-navy">{p.stage.replace(/_/g, " ")}</td>
                <td className="px-4 py-2.5 text-ss-navy">{p.count}</td>
                <td className="px-4 py-2.5 text-ss-navy-soft text-xs">
                  {p.deals_with_value} / {p.count}
                  {p.deals_with_value < p.count && <span className="ml-2 text-amber-700 italic">— missing values</span>}
                </td>
                <td className="px-4 py-2.5 text-ss-navy font-semibold">{fmtMoney(p.total_value)}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        {/* ─── Wins ─── */}
        <Panel title="Wins — full deal anatomy"
               subtitle={`${data.wins.length} closed-won deals`}
               onExport={() => exportCsv("wins", [
                 "Prospect", "Product", "SE", "Closed date", "Go-live date",
                 "Demo→Close (days)", "Close→Go-live (days)", "Discovery source",
                 "Incumbent", "Switching reason", "Aha"
               ], data.wins.map(w => [
                 w.prospect, w.product, w.se_name, w.closed_date, w.go_live_date,
                 w.demo_to_close_days, w.close_to_go_live_days, w.discovery_source,
                 w.incumbent?.tool, w.incumbent?.switching_reason, w.aha,
               ]))}
        >
          {data.wins.length === 0 && (
            <div className="p-8 text-center text-ss-navy-soft italic">
              No closed-won deals yet. Once SEs mark deals as won via the
              call detail page, deal anatomy will appear here.
            </div>
          )}
          {data.wins.map(w => (
            <div key={w.call_id} className="border-b border-slate-100 p-5">
              <div className="flex justify-between items-start gap-4 mb-3">
                <div>
                  <a href={`/call/${w.call_id}`} className="font-semibold text-ss-navy hover:text-ss-teal-deep text-base">
                    {w.prospect} {w.use_case && <span className="font-normal text-ss-navy-soft">· {w.use_case}</span>}
                  </a>
                  <div className="text-xs text-ss-navy-soft mt-1">
                    {w.product} · Closed {fmtDate(w.closed_date)} · SE: {w.se_name}{w.ae_name && ` · AE: ${w.ae_name}`}
                  </div>
                </div>
                <div className="text-right text-xs text-ss-navy-soft whitespace-nowrap">
                  {w.deal_value != null && (
                    <div className="mb-1">
                      <span className="text-emerald-700 font-bold text-base">{fmtMoney(w.deal_value, w.deal_currency || "USD")}</span>
                      {w.crm_deal_url && (
                        <a href={w.crm_deal_url} target="_blank" rel="noopener noreferrer"
                          className="ml-2 text-ss-teal-deep hover:underline text-[10px]">HubSpot ↗</a>
                      )}
                    </div>
                  )}
                  {w.demo_to_close_days != null && <div><strong className="text-ss-navy text-sm">{w.demo_to_close_days}d</strong> demo→close</div>}
                  {w.close_to_go_live_days != null && <div><strong className="text-ss-navy text-sm">{w.close_to_go_live_days}d</strong> close→go-live</div>}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-3 mt-3 text-xs">
                <div>
                  <div className="font-semibold text-ss-navy-soft uppercase tracking-wide mb-1">Buying committee ({w.buying_committee.length})</div>
                  <div className="space-y-1">
                    {w.buying_committee.length === 0 && <div className="text-ss-navy-soft italic">Not extracted</div>}
                    {w.buying_committee.map((m, i) => (
                      <div key={i} className="text-ss-navy">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider mr-2 ${ROLE_COLOR[m.role] || "bg-slate-100 text-slate-600"}`}>
                          {ROLE_LABEL[m.role] || m.role}
                        </span>
                        {m.name}{m.title && <span className="text-ss-navy-soft">, {m.title}</span>}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-ss-navy-soft uppercase tracking-wide mb-1">Previous tool</div>
                  <div className="text-ss-navy">
                    {w.incumbent?.tool ? (
                      <>
                        <strong>{w.incumbent.tool}</strong>
                        {w.incumbent.years_using && ` · ${w.incumbent.years_using}`}
                        {w.incumbent.switching_reason && <div className="text-ss-navy-soft mt-1 italic">"{w.incumbent.switching_reason}"</div>}
                      </>
                    ) : <span className="text-ss-navy-soft italic">Not captured</span>}
                  </div>
                  <div className="font-semibold text-ss-navy-soft uppercase tracking-wide mb-1 mt-3">How they found us</div>
                  <div className="text-ss-navy">{w.discovery_source || <span className="text-ss-navy-soft italic">Unknown</span>}</div>
                </div>
              </div>
              {w.aha && (
                <div className="mt-3 px-3 py-2.5 bg-teal-50 border-l-4 border-teal-600 rounded">
                  <div className="text-[10px] font-bold text-teal-700 uppercase tracking-wider mb-1">★ Aha moment</div>
                  <div className="text-ss-navy text-sm italic">"{w.aha}"</div>
                </div>
              )}
            </div>
          ))}
        </Panel>

        {/* ─── Buying committee composition ─── */}
        <Panel title="Buying committee — composition patterns"
               subtitle={`${data.buying_committee.reduce((s, r) => s + r.calls_present, 0)} role-presences across ${h.calls_analyzed} calls`}
               onExport={() => exportCsv("buying-committee", [
                 "Role", "Present on N calls", "% of calls", "Top titles",
                 "Avg score when present", "Avg score when absent"
               ], data.buying_committee.map(r => [
                 ROLE_LABEL[r.role] || r.role, r.calls_present,
                 (r.pct_calls * 100).toFixed(0) + "%",
                 (r.top_titles || []).join(" · "),
                 r.avg_score_when_present, r.avg_score_when_absent,
               ]))}>
          <Table headers={["Role", "Calls present", "% calls", "Typical titles", "Avg score (present)", "Avg score (absent)"]}>
            {data.buying_committee.map(r => (
              <tr key={r.role} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5">
                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${ROLE_COLOR[r.role] || "bg-slate-100"}`}>
                    {ROLE_LABEL[r.role] || r.role}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-semibold text-ss-navy">{r.calls_present}</td>
                <td className="px-4 py-2.5 text-ss-navy">{(r.pct_calls * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 text-xs text-ss-navy-soft">{(r.top_titles || []).slice(0,4).join(" · ") || "—"}</td>
                <td className="px-4 py-2.5 text-ss-navy">{r.avg_score_when_present ?? "—"}</td>
                <td className="px-4 py-2.5 text-ss-navy-soft">{r.avg_score_when_absent ?? "—"}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        {/* ─── Deal velocity ─── */}
        <Panel title="Deal velocity — demo→close + close→go-live"
               subtitle="median + P90 by cohort"
               onExport={() => exportCsv("deal-velocity", [
                 "Cohort", "N", "Median demo→close", "P90 demo→close",
                 "Median close→go-live", "P90 close→go-live"
               ], data.deal_velocity.map(c => [
                 c.cohort, c.n,
                 c.demo_to_close?.median, c.demo_to_close?.p90,
                 c.close_to_go_live?.median, c.close_to_go_live?.p90,
               ]))}>
          <Table headers={["Cohort", "N deals", "Median demo→close", "P90 demo→close", "Median close→go-live", "P90 close→go-live"]}>
            {data.deal_velocity.map(c => (
              <tr key={c.cohort} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5 text-ss-navy">{c.cohort}</td>
                <td className="px-4 py-2.5 text-ss-navy font-semibold">{c.n}</td>
                <td className="px-4 py-2.5 text-ss-navy">{c.demo_to_close?.median ?? "—"}{c.demo_to_close?.median != null && "d"}</td>
                <td className="px-4 py-2.5 text-ss-navy-soft">{c.demo_to_close?.p90 ?? "—"}{c.demo_to_close?.p90 != null && "d"}</td>
                <td className="px-4 py-2.5 text-ss-navy">{c.close_to_go_live?.median ?? "—"}{c.close_to_go_live?.median != null && "d"}</td>
                <td className="px-4 py-2.5 text-ss-navy-soft">{c.close_to_go_live?.p90 ?? "—"}{c.close_to_go_live?.p90 != null && "d"}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        {/* ─── Incumbent displacement ─── */}
        <Panel title="Incumbent displacement — who we're replacing"
               subtitle={`${data.incumbent_displacement.length} incumbents named`}
               onExport={() => exportCsv("incumbent-displacement", [
                 "Incumbent", "Calls", "Products", "Top switching reason", "Years using (samples)"
               ], data.incumbent_displacement.map(r => [
                 r.tool, r.calls, (r.products || []).join("/"),
                 r.top_switching_reason, (r.years_using_samples || []).join(", "),
               ]))}>
          <Table headers={["Incumbent", "Calls displacing", "Product", "Top switching reason", "Years used (samples)"]}>
            {data.incumbent_displacement.map(r => (
              <tr key={r.tool} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5 font-semibold text-ss-navy">{r.tool}</td>
                <td className="px-4 py-2.5 text-ss-navy">{r.calls}</td>
                <td className="px-4 py-2.5 text-xs">{(r.products || []).join(" · ")}</td>
                <td className="px-4 py-2.5 text-ss-navy text-xs italic">{r.top_switching_reason || "—"}</td>
                <td className="px-4 py-2.5 text-xs text-ss-navy-soft">{(r.years_using_samples || []).join(", ") || "—"}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        {/* ─── Discovery source ─── */}
        <Panel title="Discovery source — how prospects find us"
               subtitle={`${data.discovery_source.length} channels`}
               onExport={() => exportCsv("discovery-source", [
                 "Source", "Calls", "% of calls", "Wins", "Win rate", "Avg score",
                 "Total won value", "Avg deal size"
               ], data.discovery_source.map(s => [
                 s.source, s.calls, (s.pct_of_calls * 100).toFixed(0) + "%",
                 s.wins, (s.win_rate * 100).toFixed(0) + "%", s.avg_score,
                 s.total_won_value, s.avg_deal_size,
               ]))}>
          <Table headers={["Source", "Calls", "% of demos", "Wins", "Win rate", "Total won $", "Avg deal size", "Avg score"]}>
            {data.discovery_source.map(s => (
              <tr key={s.source} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5 font-semibold text-ss-navy">{s.source}</td>
                <td className="px-4 py-2.5 text-ss-navy">{s.calls}</td>
                <td className="px-4 py-2.5 text-ss-navy">{(s.pct_of_calls * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 text-ss-navy">{s.wins}</td>
                <td className="px-4 py-2.5 text-ss-navy font-semibold">{(s.win_rate * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 text-emerald-700 font-semibold">{fmtMoney(s.total_won_value)}</td>
                <td className="px-4 py-2.5 text-ss-navy">{s.avg_deal_size ? fmtMoney(s.avg_deal_size) : "—"}</td>
                <td className="px-4 py-2.5 text-ss-navy">{s.avg_score ?? "—"}</td>
              </tr>
            ))}
          </Table>
        </Panel>

        {/* ─── Aha patterns ─── */}
        <Panel title="Aha moments — what's actually closing deals"
               subtitle={`${data.aha_patterns.reduce((s, p) => s + p.wins_citing, 0)} aha moments across wins`}
               onExport={() => exportCsv("aha-patterns", [
                 "Category", "Wins citing", "% of wins", "Example quote"
               ], data.aha_patterns.map(p => [
                 p.category, p.wins_citing, (p.pct_of_wins * 100).toFixed(0) + "%",
                 p.examples?.[0]?.quote,
               ]))}>
          <Table headers={["Category", "Wins citing", "% of wins", "Representative quote"]}>
            {data.aha_patterns.map(p => (
              <tr key={p.category} className="border-t border-slate-100 hover:bg-ss-cream">
                <td className="px-4 py-2.5 font-semibold text-ss-navy">{p.category.replace(/_/g, " ")}</td>
                <td className="px-4 py-2.5 text-ss-navy">{p.wins_citing}</td>
                <td className="px-4 py-2.5 text-ss-navy font-semibold">{(p.pct_of_wins * 100).toFixed(0)}%</td>
                <td className="px-4 py-2.5 text-ss-navy text-xs italic">
                  {p.examples?.[0] ? `"${p.examples[0].quote}" — ${p.examples[0].prospect}` : "—"}
                </td>
              </tr>
            ))}
          </Table>
        </Panel>

        <div className="text-xs text-ss-navy-soft text-center mt-6">
          Source-of-truth: per-call insights v4 (auto-extracted) + SE-edited enrichment fields (close date, go-live date, deal outcome, aha override, discovery source override).
        </div>
      </main>
    </>
  );
}

function Stat({ label, value, sub }: { label: React.ReactNode; value: any; sub?: string }) {
  return (
    <div className="p-5 border-r border-ss-cyan-soft last:border-r-0">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-2">{label}</div>
      <div className="text-2xl font-bold text-ss-navy">{value}</div>
      {sub && <div className="text-xs text-ss-navy-soft mt-1">{sub}</div>}
    </div>
  );
}

function Panel({ title, subtitle, children, onExport }: {
  title: string; subtitle?: string; children: React.ReactNode; onExport?: () => void;
}) {
  return (
    <section className="bg-white border border-ss-cyan-soft rounded-xl mb-6 overflow-hidden">
      <div className="px-5 py-3 border-b border-ss-cyan-soft flex justify-between items-center">
        <div>
          <h2 className="font-semibold text-ss-navy text-sm">{title}</h2>
          {subtitle && <div className="text-xs text-ss-navy-soft mt-0.5">{subtitle}</div>}
        </div>
        {onExport && (
          <button onClick={onExport}
            className="px-3 py-1 text-[11px] font-semibold border border-ss-cyan-soft text-ss-navy rounded hover:bg-ss-cream transition">
            ⤓ CSV
          </button>
        )}
      </div>
      <div className="text-sm">{children}</div>
    </section>
  );
}

function Table({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-ss-cream text-xs font-semibold text-ss-navy-soft uppercase tracking-wider">
          <tr>{headers.map(h => <th key={h} className="text-left px-4 py-2.5">{h}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
