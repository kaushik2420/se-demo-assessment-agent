"use client";
import { use } from "react";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, isLoading } = useSWR<any>(`/calls/${id}`, fetcher);

  if (isLoading) return (<><TopNav /><div className="p-10">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const { call, scorecard, insights } = data;
  if (!scorecard) return (<><TopNav /><div className="p-10">Analysis pending…</div></>);

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">← Back to dashboard</Link>
        <div className="flex justify-between items-end mt-2 mb-6">
          <div>
            <h1 className="text-2xl font-semibold">{call.prospect_company}</h1>
            <p className="text-slate-500">{call.date?.slice(0,10)} · {call.duration_min} min · {call.call_type} · {call.source}</p>
          </div>
          <div className="flex gap-2">
            <span className="px-3 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-full uppercase">{call.call_type}</span>
            {insights?.cx_maturity && (
              <span className="px-3 py-1 bg-amber-100 text-amber-800 text-xs font-semibold rounded-full uppercase">{insights.cx_maturity.category}</span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-6">
          <Stat label="Weighted Score" value={`${scorecard.weighted_final} / 5`} />
          <Stat label="Industry Percentile" value={`P${scorecard.industry_percentile}`} />
          <Stat label="SE Selling Style" value={insights?.se_selling_style?.verdict || "—"} />
          <Stat label="AE Behavior" value={insights?.ae_behavior?.ae_quality_flag ? "Flagged" : "Clean"} />
        </div>

        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Criteria */}
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold mb-4">Score by criterion</h3>
            {Object.entries(scorecard.per_criterion_score).map(([k, v]: any) => (
              <div key={k} className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0 text-sm">
                <div className="flex-1">{k}</div>
                <div className="font-semibold w-12 text-right">{Number(v).toFixed(2)}</div>
                <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full" style={{ width: `${(Number(v) / 5) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          {/* Strengths/Gaps */}
          <div>
            <div className="bg-white border border-slate-200 rounded-xl p-6 mb-4">
              <h3 className="font-semibold mb-3">Top strengths</h3>
              <ul className="space-y-2 text-sm">
                {(scorecard.qualitative?.top_3_strengths || []).map((s: string, i: number) => (
                  <li key={i} className="flex gap-2"><span className="text-emerald-600">✓</span> {s}</li>
                ))}
              </ul>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="font-semibold mb-3">Areas of improvement</h3>
              <ul className="space-y-2 text-sm">
                {(scorecard.qualitative?.top_3_gaps || []).map((g: string, i: number) => (
                  <li key={i} className="flex gap-2"><span className="text-red-600">!</span> {g}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Coaching action */}
        {scorecard.qualitative?.one_coaching_action && (
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl p-6 mb-6">
            <div className="text-xs font-bold text-blue-900 uppercase tracking-wider mb-2">★ Coaching action</div>
            <p className="leading-relaxed">{scorecard.qualitative.one_coaching_action}</p>
          </div>
        )}

        {/* 9 insights */}
        {insights && (
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold mb-4">Deal-intelligence signals</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <Insight title="Use case" body={insights.use_case?.summary} />
              <Insight title="CX maturity" body={`${insights.cx_maturity?.category} — ${insights.cx_maturity?.rationale || ""}`} />
              <Insight title={`Feature requests (${insights.feature_requests?.length || 0})`}
                       body={(insights.feature_requests || []).map((f: any) => f.feature).join(" · ")} />
              <Insight title="Competitors"
                       body={(insights.competitors_mentioned || []).map((c: any) => c.name).join(", ") || "—"} />
              <Insight title={`Trial issues (${insights.trial_issues?.length || 0})`}
                       body={(insights.trial_issues || []).map((t: any) => t.issue).join(" · ") || "—"} />
              <Insight title="SE selling style"
                       body={`${insights.se_selling_style?.verdict} (${Math.round((insights.se_selling_style?.feature_selling_share||0)*100)}% features / ${Math.round((insights.se_selling_style?.value_selling_share||0)*100)}% value)`} />
              <Insight title="AE interruptions" body={`${insights.ae_behavior?.interruption_count ?? 0} times`} />
              <Insight title="Prospect engagement" body={insights.prospect_engagement?.sentiment} />
            </div>
          </div>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

function Insight({ title, body }: { title: string; body: any }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{title}</div>
      <div className="text-slate-800">{body || "—"}</div>
    </div>
  );
}
