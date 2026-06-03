"use client";
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { InfoIcon } from "@/components/MethodologyDrawer";

const fetcher = (url: string) => api(url);

export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  // Poll every 4s while the analysis is in flight. Stop once we have a
  // scorecard OR the server has marked the analysis as failed (no point
  // polling a permanently broken row — the user has to click Retry).
  const { data, error, isLoading } = useSWR<any>(`/calls/${id}`, fetcher, {
    refreshInterval: (latest) => {
      if (latest?.scorecard) return 0;
      if (latest?.call?.analysis_status === "failed") return 0;
      return 4000;
    },
  });
  const { data: me } = useSWR<any>("/auth/me", fetcher);
  const [deleting, setDeleting] = useState(false);
  const canDelete = me?.role === "admin" || me?.role === "manager";

  async function handleDelete() {
    const label = data?.call?.prospect_company || id;
    if (!confirm(`Delete this call (${label}) along with its scorecard and insights? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await api(`/calls/${id}`, { method: "DELETE" });
      router.push(me?.role === "se" ? "/dashboard" : "/manager");
    } catch (e: any) {
      alert(`Delete failed: ${e?.message || e}`);
      setDeleting(false);
    }
  }

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const { call, scorecard, insights } = data;
  if (!scorecard) {
    return (
      <>
        <TopNav />
        <main className="max-w-3xl mx-auto p-10">
          <h1 className="text-2xl font-semibold text-ss-navy mb-1">
            {call?.prospect_company || "New call"}
          </h1>
          <p className="text-ss-navy-soft mb-6">
            {call?.call_type} · {call?.duration_min ? `~${call.duration_min} min` : "duration tbd"}
          </p>
          <AnalysisStatusCard call={call} callId={id} />
        </main>
      </>
    );
  }

  // Backward-compatible read: new shape has `insights.maturity` + `insights.product`;
  // old calls have `insights.cx_maturity` only.
  const maturityBlock = insights?.maturity || insights?.cx_maturity || null;
  const maturityScope: string | null =
    insights?.maturity?.scope || (insights?.cx_maturity ? "CX" : null);
  const product: string | null = insights?.product?.primary || null;
  const featuresDiscussed = insights?.features_discussed || [];
  const featureRequests = insights?.feature_requests || [];
  // Surface any sub-criteria the model couldn't assess from the transcript
  const notAssessable: Record<string, string[]> = scorecard.not_assessable || {};
  const notAssessableSubs = Object.entries(notAssessable).flatMap(([crit, subs]) =>
    (subs as string[]).map((s) => `${crit} → ${s}`)
  );

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <div className="flex justify-between items-center">
          <Link href="/dashboard" className="text-sm text-ss-navy-soft hover:text-ss-navy">← Back to dashboard</Link>
          {canDelete && (
            <button onClick={handleDelete} disabled={deleting}
              className="px-3 py-1.5 text-xs font-semibold text-red-700 hover:text-white hover:bg-red-600 border border-red-200 hover:border-red-600 rounded transition disabled:opacity-50 disabled:cursor-not-allowed">
              {deleting ? "Deleting…" : "🗑 Delete call"}
            </button>
          )}
        </div>
        <div className="flex justify-between items-end mt-2 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">{call.prospect_company}</h1>
            <p className="text-ss-navy-soft">
              {call.date?.slice(0, 10)} · {call.duration_min} min · {call.call_type} · {call.source}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            <span className="px-3 py-1 bg-ss-cyan-soft text-ss-navy text-xs font-semibold rounded-full uppercase">
              {call.call_type}
            </span>
            {product && (
              <span className="px-3 py-1 bg-teal-100 text-teal-800 text-xs font-semibold rounded-full uppercase">
                {product}
              </span>
            )}
            {maturityBlock?.category && (
              <span className="px-3 py-1 bg-amber-100 text-amber-800 text-xs font-semibold rounded-full uppercase">
                {maturityBlock.category}{maturityScope ? ` · ${maturityScope}` : ""}
              </span>
            )}
          </div>
        </div>

        {/* Banner: which sub-criteria the analysis couldn't assess from transcript */}
        {notAssessableSubs.length > 0 && (
          <div className="mb-6 px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 flex gap-2 items-start">
            <span className="font-bold mt-0.5">ⓘ</span>
            <div>
              <strong>{notAssessableSubs.length} sub-criteria were not assessable from the transcript</strong> (typically visual signals when screen content wasn't verbally described). These were excluded from the weighted score rather than penalized: {notAssessableSubs.join(" · ")}.
            </div>
          </div>
        )}

        <div className="grid grid-cols-4 gap-4 mb-6">
          <Stat label={<>Weighted Score<InfoIcon section="formula" /></>} value={`${scorecard.weighted_final} / 5`} />
          <Stat label={<>Industry Percentile<InfoIcon section="percentile" /></>} value={`P${scorecard.industry_percentile}`} />
          <Stat label="SE Selling Style" value={insights?.se_selling_style?.verdict || "—"} />
          <Stat label="AE Behavior" value={insights?.ae_behavior?.ae_quality_flag ? "Flagged" : "Clean"} />
        </div>

        {/* Source-aware disclaimer for Granola transcripts */}
        {call.source === "granola" && insights?.ae_behavior && (
          <div className="mb-6 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex gap-2 items-start">
            <span className="font-bold mt-0.5">ⓘ</span>
            <div>
              <strong>AE behavior signals are inferred, not measured</strong> for this call. Granola
              transcripts use a single audio track for everyone other than the SE, so we can't
              distinguish AE turns from prospect turns directly — Claude attributes them from
              content patterns. Treat AE-quality flags as directional. For surgical AE
              measurement on a specific call, paste the richer per-speaker transcript via Upload.
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Criteria */}
          <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
            <h3 className="font-semibold text-ss-navy mb-4 flex items-center">
              Score by criterion<InfoIcon section="per-criterion" label="How are criterion scores benchmarked?" />
            </h3>
            {Object.entries(scorecard.per_criterion_score).map(([k, v]: any) => (
              <div key={k} className="flex items-center gap-3 py-2 border-b border-ss-cyan-soft last:border-0 text-sm">
                <div className="flex-1 text-ss-navy">{k}</div>
                <div className="font-semibold w-12 text-right text-ss-navy">{Number(v).toFixed(2)}</div>
                <div className="w-32 h-2 bg-ss-cream rounded-full overflow-hidden">
                  <div className="h-full bg-ss-navy rounded-full"
                       style={{ width: `${(Number(v) / 5) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          {/* Strengths/Gaps */}
          <div>
            <div className="bg-white border border-ss-cyan-soft rounded-xl p-6 mb-4">
              <h3 className="font-semibold text-ss-navy mb-3">Top strengths</h3>
              <ul className="space-y-2 text-sm">
                {(scorecard.qualitative?.top_3_strengths || []).map((s: string, i: number) => (
                  <li key={i} className="flex gap-2 text-ss-navy">
                    <span className="text-emerald-600 font-bold">✓</span> {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
              <h3 className="font-semibold text-ss-navy mb-3">Areas of improvement</h3>
              <ul className="space-y-2 text-sm">
                {(scorecard.qualitative?.top_3_gaps || []).map((g: string, i: number) => (
                  <li key={i} className="flex gap-2 text-ss-navy">
                    <span className="text-red-600 font-bold">!</span> {g}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Coaching action */}
        {scorecard.qualitative?.one_coaching_action && (
          <div
            className="rounded-xl p-6 mb-6 border"
            style={{
              background: "linear-gradient(135deg,#E7F7FC 0%,#B1EAF8 100%)",
              borderColor: "#5CCDED",
            }}
          >
            <div className="text-xs font-bold text-ss-navy uppercase tracking-wider mb-2">
              ★ Coaching action
            </div>
            <p className="leading-relaxed text-ss-navy">{scorecard.qualitative.one_coaching_action}</p>
          </div>
        )}

        {/* Deal-intelligence signals */}
        {insights && (
          <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
            <h3 className="font-semibold text-ss-navy mb-4">Deal-intelligence signals</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <Insight title="Product" body={product || "Unknown"} />
              <Insight title={`Maturity${maturityScope ? ` (${maturityScope})` : ""}`}
                       body={maturityBlock ? `${maturityBlock.category} — ${maturityBlock.rationale || ""}` : "—"} />
              <Insight title="Use case" body={insights.use_case?.summary} />
              <Insight title="Competitors"
                       body={(insights.competitors_mentioned || []).map((c: any) => c.name).join(", ") || "—"} />
              <Insight title={`Features discussed (${featuresDiscussed.length})`}
                       body={featuresDiscussed.length === 0 ? "—" :
                             featuresDiscussed.map((f: any) => f.feature).join(" · ")} />
              <Insight title={`Feature requests / gaps (${featureRequests.length})`}
                       body={featureRequests.length === 0 ? "—" :
                             featureRequests.map((f: any) =>
                               `${f.feature}${f.urgency ? ` [${f.urgency}]` : ""}`).join(" · ")} />
              <Insight title={`Trial issues (${insights.trial_issues?.length || 0})`}
                       body={(insights.trial_issues || []).map((t: any) => t.issue).join(" · ") || "—"} />
              <Insight title="SE selling style"
                       body={`${insights.se_selling_style?.verdict} (${Math.round((insights.se_selling_style?.feature_selling_share || 0) * 100)}% features / ${Math.round((insights.se_selling_style?.value_selling_share || 0) * 100)}% value)`} />
              <Insight title="AE interruptions" body={`${insights.ae_behavior?.interruption_count ?? 0} times`} />
              <Insight title="Prospect engagement" body={insights.prospect_engagement?.sentiment} />
            </div>
          </div>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: React.ReactNode; value: any }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-5">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-2 flex items-center">{label}</div>
      <div className="text-2xl font-bold text-ss-navy">{value}</div>
    </div>
  );
}

function Insight({ title, body }: { title: string; body: any }) {
  return (
    <div className="bg-ss-cream rounded-lg p-3">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">{title}</div>
      <div className="text-ss-navy">{body || "—"}</div>
    </div>
  );
}

/**
 * Surface what's ACTUALLY happening with the analysis instead of a forever
 * spinner. Three states:
 *   - analyzing → pulsing icon + elapsed-time hint, optional "Retry" if >10min
 *   - failed → red error card with the server-side message + always-on Retry
 *   - pending → brief transient state right after upload; same UI as analyzing
 */
function AnalysisStatusCard({ call, callId }: { call: any; callId: string }) {
  const status: string = call?.analysis_status || "analyzing";
  const startedAt: string | null = call?.analysis_started_at || null;
  const errorMsg: string | null = call?.analysis_error || null;
  const elapsedMin = startedAt
    ? Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 60000))
    : 0;

  const [retrying, setRetrying] = useState(false);
  const [retryErr, setRetryErr] = useState<string | null>(null);

  async function handleRetry() {
    setRetrying(true);
    setRetryErr(null);
    try {
      await api(`/calls/${callId}/retry`, { method: "POST" });
      // SWR will pick up the new status on its next poll (every 4s)
      setTimeout(() => window.location.reload(), 1500);
    } catch (e: any) {
      setRetryErr(String(e?.message || e));
      setRetrying(false);
    }
  }

  if (status === "failed") {
    return (
      <div className="bg-red-50 border border-red-300 rounded-xl p-8">
        <div className="text-3xl mb-3">⚠️</div>
        <div className="font-semibold text-red-900 mb-2">Analysis failed</div>
        <p className="text-sm text-red-800 mb-4 max-w-2xl whitespace-pre-wrap">
          {errorMsg || "Something went wrong during the analysis. The transcript is safely stored — click Retry to try again."}
        </p>
        <div className="flex gap-3 items-center">
          <button onClick={handleRetry} disabled={retrying}
            className="px-4 py-2 bg-red-700 text-white rounded-lg font-semibold text-sm hover:bg-red-800 disabled:opacity-50 transition">
            {retrying ? "Restarting…" : "🔁 Retry analysis"}
          </button>
          <span className="text-xs text-red-700">
            If retry keeps failing, ping kaushik with the error message above.
          </span>
        </div>
        {retryErr && <div className="mt-3 text-xs text-red-900">{retryErr}</div>}
      </div>
    );
  }

  // analyzing / pending state
  const isStuck = elapsedMin >= 10;
  return (
    <div className="bg-ss-cream border border-ss-cyan-soft rounded-xl p-8 text-center">
      <div className="text-3xl mb-3 animate-pulse">⏳</div>
      <div className="font-semibold text-ss-navy mb-1">
        {isStuck ? "Still analyzing… this is taking longer than usual" : "Analyzing your call…"}
      </div>
      <p className="text-sm text-ss-navy-soft max-w-md mx-auto mb-3">
        Claude is reading the transcript and scoring it against the 7-criterion rubric +
        extracting deal-intelligence signals. This usually takes 30-90 seconds.
        The page refreshes automatically when results land.
      </p>
      {startedAt && (
        <p className="text-xs text-ss-navy-soft mb-3">
          Started {elapsedMin === 0 ? "just now" : `${elapsedMin} minute${elapsedMin === 1 ? "" : "s"} ago`}
        </p>
      )}
      {isStuck && (
        <div className="mt-3">
          <button onClick={handleRetry} disabled={retrying}
            className="px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark disabled:opacity-50 transition">
            {retrying ? "Restarting…" : "🔁 Force retry"}
          </button>
          <p className="text-xs text-ss-navy-soft mt-2 italic">
            The worker may have crashed — clicking retry kicks off a fresh analysis.
          </p>
          {retryErr && <div className="mt-2 text-xs text-red-700">{retryErr}</div>}
        </div>
      )}
    </div>
  );
}
