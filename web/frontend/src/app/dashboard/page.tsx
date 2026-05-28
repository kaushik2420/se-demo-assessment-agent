"use client";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function DashboardPage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/se", fetcher);

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed to load: {String(error)}</div></>);
  if (data?.empty) return (<><TopNav /><div className="p-10">No profile data yet.</div></>);

  const { headline, coaching_action, recent_calls, dotm_winner } = data;
  const noCalls = !recent_calls || recent_calls.length === 0;

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Hello, {data.se.name}</h1>
            <p className="text-ss-navy-soft">
              {noCalls
                ? "No calls analyzed yet. Click + Upload transcript to get started."
                : `${headline.calls_this_month} call${headline.calls_this_month === 1 ? "" : "s"} analyzed this month`}
            </p>
          </div>
          <Link href="/upload"
                className="px-5 py-2.5 bg-ss-navy text-white rounded-lg font-semibold hover:bg-ss-navy-dark transition">
            + Upload transcript
          </Link>
        </div>

        {/* === DEMO OF THE MONTH WINNER BADGE === */}
        {dotm_winner && (
          <div
            className="mb-6 rounded-xl p-6 border-2 text-white"
            style={{
              background: "linear-gradient(135deg, #4A9CA6 0%, #3A8290 100%)",
              borderColor: "#4A9CA6",
              boxShadow: "0 8px 24px rgba(74,156,166,0.25)",
            }}
          >
            <div className="flex items-center gap-4">
              <div className="text-5xl">🏆</div>
              <div className="flex-1">
                <div className="text-xs font-bold uppercase tracking-wider opacity-90 mb-1">
                  Demo of the Month · #{dotm_winner.rank}
                </div>
                <div className="text-2xl font-bold">
                  Congrats, {dotm_winner.se_name.split(" ")[0]}!
                </div>
                <div className="text-sm opacity-90 mt-1">
                  You're ranked #{dotm_winner.rank} this month with an average score of{" "}
                  <strong>{dotm_winner.avg_score}/5</strong> across{" "}
                  {dotm_winner.call_count} demo{dotm_winner.call_count === 1 ? "" : "s"}.
                </div>
              </div>
            </div>
          </div>
        )}

        {!noCalls && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <Stat label="Current Score" value={`${headline.current_score} / 5`}
                    trend={headline.score_delta_mom >= 0 ? "up" : "down"}
                    trendText={headline.score_delta_mom !== 0
                      ? `${headline.score_delta_mom >= 0 ? "↑" : "↓"} ${Math.abs(headline.score_delta_mom)} vs last month`
                      : ""} />
              <Stat label="Industry Percentile" value={`P${headline.industry_percentile}`} />
              <Stat label="Calls This Month" value={String(headline.calls_this_month)} />
              <Stat label="Coaching Action" value={coaching_action ? "See below ↓" : "Not set yet"} />
            </div>

            {coaching_action && (
              <div
                className="rounded-xl p-6 mb-6 border"
                style={{
                  background: "linear-gradient(135deg, #DCEFF1 0%, #B1EAF8 100%)",
                  borderColor: "#5DACB6",
                }}
              >
                <div className="text-xs font-bold text-ss-navy uppercase tracking-wider mb-2">
                  ★ Coaching action of the month
                </div>
                <p className="text-ss-navy leading-relaxed">{coaching_action.text}</p>
                <div className="text-xs text-ss-navy-soft mt-3">
                  Set by {coaching_action.set_by} · {coaching_action.month}
                </div>
              </div>
            )}
          </>
        )}

        {/* === RECENT CALLS (full width again, focus on coaching) === */}
        <div className="bg-white rounded-xl border border-ss-cyan-soft p-6">
          <h2 className="font-semibold text-ss-navy mb-4">Recent calls</h2>
          {noCalls && (
            <p className="text-ss-navy-soft italic">
              No calls yet — upload your first transcript above.
            </p>
          )}
          {recent_calls?.map((c: any) => (
            <Link key={c.call_id} href={`/call/${c.call_id}`}
                  className="grid grid-cols-[1fr,120px,140px,80px] gap-4 items-center py-3
                             border-b border-ss-cyan-soft last:border-0 hover:bg-ss-cream rounded transition">
              <div>
                <div className="font-medium text-ss-navy">{c.prospect}</div>
                <div className="text-xs text-ss-navy-soft">{c.date}</div>
              </div>
              <span className="px-2 py-1 bg-ss-cyan-soft text-ss-navy text-xs font-semibold rounded uppercase">
                {c.type}
              </span>
              <span className="text-xs text-ss-navy-soft">{c.cx_maturity || "—"}</span>
              <div className="text-right font-semibold text-ss-navy">
                {c.score?.toFixed(2) ?? "—"} / 5
              </div>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}

function Stat({ label, value, trend, trendText }: { label: string; value: string; trend?: "up" | "down"; trendText?: string }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-5">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-3">{label}</div>
      <div className="text-3xl font-bold text-ss-navy">{value}</div>
      {trendText && (
        <div className={`text-xs mt-2 ${trend === "up" ? "text-emerald-600" : "text-red-600"}`}>
          {trendText}
        </div>
      )}
    </div>
  );
}
