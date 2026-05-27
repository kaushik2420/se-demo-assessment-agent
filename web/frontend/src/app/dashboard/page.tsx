"use client";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function DashboardPage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/se", fetcher);

  if (isLoading) return (<><TopNav /><div className="p-10">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);
  if (data?.empty) return (<><TopNav /><div className="p-10">No profile data yet.</div></>);

  const { headline, coaching_action, recent_calls } = data;
  const noCalls = !recent_calls || recent_calls.length === 0;

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold">Hello, {data.se.name}</h1>
            <p className="text-slate-500">
              {noCalls
                ? "No calls analyzed yet. Click + Upload transcript to get started."
                : `${headline.calls_this_month} calls analyzed this month`}
            </p>
          </div>
          <Link href="/upload" className="px-5 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700">
            + Upload transcript
          </Link>
        </div>

        {!noCalls && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <Stat label="Current Score" value={`${headline.current_score} / 5`}
                    trend={headline.score_delta_mom >= 0 ? "up" : "down"}
                    trendText={headline.score_delta_mom !== 0 ? `${headline.score_delta_mom >= 0 ? "↑" : "↓"} ${Math.abs(headline.score_delta_mom)} vs last month` : ""} />
              <Stat label="Industry Percentile" value={`P${headline.industry_percentile}`} />
              <Stat label="Calls This Month" value={String(headline.calls_this_month)} />
              <Stat label="Coaching Action" value={coaching_action ? "See below" : "Not set"} />
            </div>

            {coaching_action && (
              <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl p-6 mb-6">
                <div className="text-xs font-bold text-blue-900 uppercase tracking-wider mb-2">★ Coaching action of the month</div>
                <p className="text-slate-800 leading-relaxed">{coaching_action.text}</p>
                <div className="text-xs text-slate-500 mt-3">Set by {coaching_action.set_by} · {coaching_action.month}</div>
              </div>
            )}
          </>
        )}

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold mb-4">Recent calls</h2>
          {noCalls && <p className="text-slate-500 italic">No calls yet — upload your first transcript above.</p>}
          {recent_calls?.map((c: any) => (
            <Link key={c.call_id} href={`/call/${c.call_id}`}
                  className="grid grid-cols-[1fr,120px,140px,80px] gap-4 items-center py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 rounded transition">
              <div>
                <div className="font-medium">{c.prospect}</div>
                <div className="text-xs text-slate-500">{c.date}</div>
              </div>
              <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded uppercase">{c.type}</span>
              <span className="text-xs text-slate-600">{c.cx_maturity || "—"}</span>
              <div className="text-right font-semibold">{c.score?.toFixed(2) ?? "—"} / 5</div>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}

function Stat({ label, value, trend, trendText }: { label: string; value: string; trend?: "up" | "down"; trendText?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">{label}</div>
      <div className="text-3xl font-bold">{value}</div>
      {trendText && (
        <div className={`text-xs mt-2 ${trend === "up" ? "text-emerald-600" : "text-red-600"}`}>{trendText}</div>
      )}
    </div>
  );
}
