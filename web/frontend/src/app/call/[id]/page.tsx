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
              <Insight title="Previous tool"
                       body={insights.incumbent?.tool
                         ? `${insights.incumbent.tool}${insights.incumbent.years_using ? ` · ${insights.incumbent.years_using}` : ""}${insights.incumbent.switching_reason ? ` — ${insights.incumbent.switching_reason}` : ""}`
                         : "—"} />
              <Insight title="Discovery source"
                       body={insights.discovery_source?.source || "—"} />
              <Insight title={`Buying committee (${insights.buying_committee?.length || 0})`}
                       body={(insights.buying_committee || []).map((m: any) =>
                         `${m.name}${m.title ? ` (${m.title})` : ""} — ${m.role?.replace(/_/g, " ")}`).join(" · ") || "—"} />
              <Insight title="Primary users"
                       body={(insights.primary_users || []).join(" · ") || "—"} />
            </div>
          </div>
        )}
        {/* === Deal enrichment (SE-editable) === */}
        <DealEnrichmentSection call={call} callId={id} me={me} />
      </main>
    </>
  );
}

function DealEnrichmentSection({ call, callId, me }: { call: any; callId: string; me: any }) {
  const [editing, setEditing] = useState(false);
  const canEdit = me?.role === "admin" || me?.role === "manager" || me?.role === "se";

  if (editing) {
    return (
      <DealEnrichmentForm
        call={call} callId={callId}
        onCancel={() => setEditing(false)}
        onSaved={() => { setEditing(false); window.location.reload(); }}
      />
    );
  }
  return (
    <div className="mt-6 bg-white border border-ss-cyan-soft rounded-xl p-6">
      <div className="flex justify-between items-start mb-4">
        <h3 className="font-semibold text-ss-navy">Deal enrichment</h3>
        {canEdit && (
          <button onClick={() => setEditing(true)}
            className="px-3 py-1.5 text-xs font-semibold bg-ss-cream border border-ss-cyan-soft text-ss-navy rounded hover:bg-ss-cyan-soft transition">
            ✎ Edit fields
          </button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <DetailRow label="Deal outcome" value={call.deal_outcome || "—"} />
        <DetailRow label="Deal stage" value={call.deal_stage ? call.deal_stage.replace(/_/g, " ") : "—"} />
        <DetailRow label="Deal value"
          value={call.deal_value != null
            ? `${(call.deal_currency || "USD")} ${Number(call.deal_value).toLocaleString()}`
            : "—"} />
        <DetailRow label="Closed date"  value={call.closed_date ? new Date(call.closed_date).toLocaleDateString() : "—"} />
        <DetailRow label="Go-live date" value={call.go_live_date ? new Date(call.go_live_date).toLocaleDateString() : "—"} />
        <DetailRow label="Expected close date" value={call.expected_close_date ? new Date(call.expected_close_date).toLocaleDateString() : "—"} />
        <DetailRow label="Discovery source (override)" value={call.discovery_source_override || "(using auto-extracted)"} />
        <div className="col-span-2">
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">CRM deal link</div>
          {call.crm_deal_url
            ? <a href={call.crm_deal_url} target="_blank" rel="noopener noreferrer"
                 className="text-ss-teal-deep hover:underline text-sm break-all">{call.crm_deal_url}</a>
            : <div className="text-ss-navy">—</div>}
        </div>
        <div className="col-span-3">
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">Aha moment (override)</div>
          <div className="text-ss-navy italic">{call.aha_moment_override || <span className="not-italic text-ss-navy-soft">(using auto-extracted)</span>}</div>
        </div>
        <div className="col-span-3">
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">Enrichment notes</div>
          <div className="text-ss-navy whitespace-pre-wrap">{call.enrichment_notes || <span className="text-ss-navy-soft">(none)</span>}</div>
        </div>
      </div>
      {call.enrichment_updated_at && (
        <div className="text-xs text-ss-navy-soft mt-3">
          Last updated {new Date(call.enrichment_updated_at).toLocaleString()} by {call.enrichment_updated_by}
        </div>
      )}
    </div>
  );
}

function DealEnrichmentForm({ call, callId, onCancel, onSaved }: {
  call: any; callId: string; onCancel: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState({
    deal_outcome: call.deal_outcome || "",
    deal_stage: call.deal_stage || "",
    deal_value: call.deal_value != null ? String(call.deal_value) : "",
    deal_currency: call.deal_currency || "USD",
    crm_deal_url: call.crm_deal_url || "",
    expected_close_date: call.expected_close_date ? call.expected_close_date.slice(0, 10) : "",
    closed_date: call.closed_date ? call.closed_date.slice(0, 10) : "",
    go_live_date: call.go_live_date ? call.go_live_date.slice(0, 10) : "",
    discovery_source_override: call.discovery_source_override || "",
    aha_moment_override: call.aha_moment_override || "",
    enrichment_notes: call.enrichment_notes || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(null);
    try {
      // Coerce deal_value to number or null
      const payload: any = { ...form };
      if (form.deal_value === "" || form.deal_value == null) payload.deal_value = null;
      else payload.deal_value = Number(form.deal_value);
      await api(`/calls/${callId}/enrichment`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      onSaved();
    } catch (e: any) {
      setErr(String(e?.message || e));
      setSaving(false);
    }
  }
  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  return (
    <form onSubmit={save} className="mt-6 bg-white border-2 border-ss-cyan-deep rounded-xl p-6">
      <h3 className="font-semibold text-ss-navy mb-1">Edit deal enrichment</h3>
      <p className="text-xs text-ss-navy-soft mb-5">
        Deal status + HubSpot data + closure context. Once HubSpot integration is in place, the
        deal-value / stage / CRM-link fields will sync automatically.
      </p>

      <div className="text-[11px] font-bold uppercase tracking-wider text-ss-navy-soft mb-2 pb-1 border-b border-ss-cyan-soft">Deal status (from HubSpot — manual for now)</div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div>
          <Label>Deal outcome</Label>
          <select value={form.deal_outcome} onChange={e => set("deal_outcome", e.target.value)} className={selCls}>
            <option value="">— Set later —</option>
            <option value="open">Open / in progress</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
            <option value="no_decision">No decision</option>
          </select>
        </div>
        <div>
          <Label>Deal stage</Label>
          <select value={form.deal_stage} onChange={e => set("deal_stage", e.target.value)} className={selCls}>
            <option value="">—</option>
            <option value="prospecting">Prospecting</option>
            <option value="qualified">Qualified</option>
            <option value="demo_scheduled">Demo scheduled</option>
            <option value="demo_completed">Demo completed</option>
            <option value="proposal">Proposal</option>
            <option value="negotiation">Negotiation</option>
            <option value="verbal_commit">Verbal commit</option>
            <option value="closed_won">Closed-won</option>
            <option value="closed_lost">Closed-lost</option>
            <option value="no_decision">No decision</option>
          </select>
        </div>
        <div>
          <Label>Deal value</Label>
          <input type="number" min="0" step="any" value={form.deal_value}
            onChange={e => set("deal_value", e.target.value)}
            placeholder="e.g. 24000"
            className={selCls} />
        </div>
        <div>
          <Label>Currency</Label>
          <select value={form.deal_currency} onChange={e => set("deal_currency", e.target.value)} className={selCls}>
            <option value="USD">USD</option>
            <option value="INR">INR</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="AUD">AUD</option>
            <option value="SGD">SGD</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <Label>HubSpot / CRM deal link</Label>
          <input type="url" value={form.crm_deal_url}
            onChange={e => set("crm_deal_url", e.target.value)}
            placeholder="https://app.hubspot.com/contacts/.../deal/..."
            className={selCls} />
        </div>
        <div>
          <Label>Expected close date</Label>
          <input type="date" value={form.expected_close_date}
            onChange={e => set("expected_close_date", e.target.value)} className={selCls} />
        </div>
      </div>

      <div className="text-[11px] font-bold uppercase tracking-wider text-ss-navy-soft mb-2 pb-1 border-b border-ss-cyan-soft mt-6">Dates after close</div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <Label>Closed date (actual)</Label>
          <input type="date" value={form.closed_date} onChange={e => set("closed_date", e.target.value)} className={selCls} />
        </div>
        <div>
          <Label>Go-live date</Label>
          <input type="date" value={form.go_live_date} onChange={e => set("go_live_date", e.target.value)} className={selCls} />
        </div>
      </div>
      <div className="text-[11px] font-bold uppercase tracking-wider text-ss-navy-soft mb-2 pb-1 border-b border-ss-cyan-soft mt-6">Context (override auto-extracted)</div>
      <div className="mb-4">
        <Label>Discovery source (override auto-extracted)</Label>
        <select value={form.discovery_source_override} onChange={e => set("discovery_source_override", e.target.value)} className={selCls}>
          <option value="">— Use auto-extracted —</option>
          <option value="referral">Referral (customer / partner)</option>
          <option value="ae_outbound">AE outbound</option>
          <option value="organic_search">Organic search</option>
          <option value="g2_comparison">G2 / comparison page</option>
          <option value="event_conference">Event / conference</option>
          <option value="plg_upgrade">PLG / freemium upgrade</option>
          <option value="analyst_research">Analyst research (Gartner / Forrester)</option>
          <option value="unknown">Unknown</option>
        </select>
      </div>
      <div className="mb-4">
        <Label>Aha moment (override) — the prospect quote that sealed the deal</Label>
        <textarea rows={3} value={form.aha_moment_override} onChange={e => set("aha_moment_override", e.target.value)}
          placeholder="Leave blank to use the auto-extracted top candidate."
          className={selCls} />
      </div>
      <div className="mb-4">
        <Label>Enrichment notes (deal context, internal observations)</Label>
        <textarea rows={3} value={form.enrichment_notes} onChange={e => set("enrichment_notes", e.target.value)} className={selCls} />
      </div>
      {err && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded text-red-800 text-xs">{err}</div>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded text-sm hover:bg-ss-cream transition">Cancel</button>
        <button type="submit" disabled={saving} className="px-4 py-2 bg-ss-navy text-white rounded text-sm font-semibold hover:bg-ss-navy-dark disabled:opacity-50 transition">
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

const selCls = "w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal bg-white";
function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">{children}</label>;
}
function DetailRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">{label}</div>
      <div className="text-ss-navy">{value || "—"}</div>
    </div>
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
