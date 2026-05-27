"use client";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function ManagerPage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/manager", fetcher);
  if (isLoading) return (<><TopNav /><div className="p-10">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const { team_metrics, leaderboard } = data;

  return (
    <>
    <TopNav />
    <main className="max-w-7xl mx-auto p-10">
      <h1 className="text-2xl font-semibold mb-6">SE Team — May 2026</h1>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Stat label="Team avg score" value={`${team_metrics.avg_score} / 5`} />
        <Stat label="Calls analyzed" value={team_metrics.calls} />
        <Stat label="Feature-selling demos" value={`${Math.round(team_metrics.feature_selling_pct * 100)}%`} />
        <Stat label="AE quality flags" value={team_metrics.ae_quality_flags} />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
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
            {leaderboard.map((r: any) => (
              <tr key={r.se} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="p-4 font-medium">{r.se}</td>
                <td className="p-4">{r.calls}</td>
                <td className="p-4 font-semibold">{r.score}</td>
                <td className="p-4">P{r.percentile}</td>
                <td className="p-4">{r.trend === "up" ? "↑" : r.trend === "down" ? "↓" : "→"}</td>
                <td className="p-4 text-slate-600">{r.top_gap}</td>
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
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">{label}</div>
      <div className="text-3xl font-bold">{value}</div>
    </div>
  );
}
