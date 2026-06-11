"use client";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { InfoIcon } from "@/components/MethodologyDrawer";
import { RecentCalls } from "@/components/RecentCalls";

const fetcher = (url: string): Promise<any> => api(url);

const MEDAL = ["🥇", "🥈"];

/** Raw shape returned by /calls — we adapt to the RecentCalls component shape. */
type RawCall = {
  call_id: string;
  se_name: string;
  prospect_company: string;
  call_type: string;
  cx_maturity: string | null;
  weighted_final: number | null;
  date: string | null;
  duration_min: number | null;
};

function mapCalls(raw: RawCall[]) {
  return (raw || []).map((c) => ({
    call_id: c.call_id,
    prospect: c.prospect_company || "—",
    type: c.call_type,
    score: c.weighted_final,
    cx_maturity: c.cx_maturity,
    duration_min: c.duration_min,
    date: c.date ? c.date.slice(0, 10) : "—",
    se_name: c.se_name,
  }));
}

export default function ManagerPage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/manager", fetcher);
  const { data: rawCalls } = useSWR<RawCall[]>("/calls", fetcher);

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const { team_metrics, leaderboard, demo_of_the_month } = data;
  const teamCalls = mapCalls(rawCalls || []);

  return (
    <>
    <TopNav />
    <main className="max-w-7xl mx-auto p-10">
      <h1 className="text-2xl font-semibold text-ss-navy mb-1">SE Team</h1>
      <p className="text-ss-navy-soft mb-6">Leaderboard, aggregates, and AE quality across the team.</p>

      {/* === DEMO OF THE MONTH === */}
      <div
        className="mb-6 rounded-xl p-6 border-2 text-white"
        style={{
          background: "linear-gradient(135deg, #4A9CA6 0%, #3A8290 100%)",
          borderColor: "#4A9CA6",
        }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="text-3xl">🏆</div>
          <div className="flex-1">
            <div className="text-xs font-bold uppercase tracking-wider opacity-90 flex items-center">
              Demo of the Month
              <button onClick={(e) => e.stopPropagation()} className="ml-1.5">
                <InfoIcon section="managers" label="How is Demo of the Month decided?" />
              </button>
            </div>
            <div className="text-lg font-semibold">
              Top performers on demo + follow-up demo calls this month
            </div>
          </div>
        </div>

        {demo_of_the_month && demo_of_the_month.length > 0 ? (
          <div className="grid grid-cols-2 gap-4">
            {demo_of_the_month.map((w: any, i: number) => (
              <div key={w.se_email}
                   className="bg-white/15 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center gap-3">
                  <div className="text-4xl">{MEDAL[i] || `#${i + 1}`}</div>
                  <div className="flex-1">
                    <div className="font-bold text-lg">{w.se_name}</div>
                    <div className="text-xs opacity-90">{w.se_email}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold">{w.avg_score}</div>
                    <div className="text-xs opacity-90">/ 5 · {w.call_count} calls</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="opacity-90 italic">
            No eligible SEs yet this month (need ≥2 scored demo or follow-up-demo calls).
          </p>
        )}
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <Stat label="Team avg score" value={`${team_metrics.avg_score} / 5`} />
        <Stat label="Calls analyzed" value={team_metrics.calls} />
        <Stat label="Product-led demos" value={`${Math.round(team_metrics.feature_selling_pct * 100)}%`} />
        <Stat label="AE quality flags" value={team_metrics.ae_quality_flags} />
      </div>

      <div className="bg-white border border-ss-cyan-soft rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ss-cream text-xs font-semibold text-ss-navy-soft uppercase tracking-wider">
            <tr>
              <th className="text-left p-4">SE</th>
              <th className="text-left p-4">Calls</th>
              <th className="text-left p-4">Avg score</th>
              <th className="text-left p-4">Percentile</th>
              <th className="text-left p-4">Trend</th>
              <th className="text-left p-4">Top gap</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-ss-navy-soft italic">
                No SE has uploaded a scored call yet.
              </td></tr>
            )}
            {leaderboard.map((r: any) => (
              <tr key={r.email || r.se} className="border-t border-ss-cyan-soft hover:bg-ss-cream transition">
                <td className="p-4 font-medium text-ss-navy">{r.se}</td>
                <td className="p-4 text-ss-navy">{r.calls}</td>
                <td className="p-4 font-semibold text-ss-navy">{r.score}</td>
                <td className="p-4 text-ss-navy">P{r.percentile}</td>
                <td className="p-4">
                  {r.trend === "up" ? <span className="text-emerald-600">↑</span>
                    : r.trend === "down" ? <span className="text-red-600">↓</span>
                    : <span className="text-ss-navy-soft">→</span>}
                </td>
                <td className="p-4 text-ss-navy-soft">{r.top_gap}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* === ALL TEAM CALLS — click any row to open the full scorecard === */}
      <div className="mt-8">
        <RecentCalls
          calls={teamCalls}
          showSE
          title="All team calls"
          emptyMessage="No team calls analyzed yet."
        />
      </div>
    </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-5">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-3">{label}</div>
      <div className="text-3xl font-bold text-ss-navy">{value}</div>
    </div>
  );
}
