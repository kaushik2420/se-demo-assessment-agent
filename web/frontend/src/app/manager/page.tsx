"use client";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function ManagerPage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/manager", fetcher);
  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const { team_metrics, leaderboard } = data;

  return (
    <>
    <TopNav />
    <main className="max-w-7xl mx-auto p-10">
      <h1 className="text-2xl font-semibold text-ss-navy mb-1">SE Team</h1>
      <p className="text-ss-navy-soft mb-6">Leaderboard, aggregates, and AE quality across the team.</p>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <Stat label="Team avg score" value={`${team_metrics.avg_score} / 5`} />
        <Stat label="Calls analyzed" value={team_metrics.calls} />
        <Stat label="Feature-selling demos" value={`${Math.round(team_metrics.feature_selling_pct * 100)}%`} />
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
