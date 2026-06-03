"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const CALL_TYPES = [
  { v: "demo",            l: "Demo call" },
  { v: "followup_demo",   l: "Follow-up demo" },
  { v: "followup_query",  l: "Follow-up query" },
  { v: "poc",             l: "POC" },
  { v: "closure",         l: "Closure call" },
  { v: "other",           l: "Other" },
];

export default function UploadPage() {
  const router = useRouter();
  const [callType, setCallType] = useState("demo");
  const [prospect, setProspect] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    setError(null);
    setResult(null);
    const fd = new FormData();
    fd.append("call_type", callType);
    fd.append("prospect_company", prospect);
    fd.append("transcript", text);
    try {
      const r = await api<any>("/calls/upload", { method: "POST", body: fd });
      setResult(r);
      if (r.accepted && r.redirect) {
        // Backend returns immediately; analysis runs in background.
        // The call detail page shows "Analyzing…" and polls until ready.
        setTimeout(() => router.push(r.redirect), 800);
      }
    } catch (e: any) {
      // Surface the actual error instead of silently re-enabling the button.
      const msg = String(e?.message || e);
      // Clean up FastAPI's verbose error shape if present
      const m = msg.match(/\{.*\}/);
      let display = msg;
      if (m) {
        try { display = JSON.parse(m[0]).detail || msg; } catch {}
      }
      setError(display);
      console.error("[upload] failed:", e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
    <TopNav />
    <main className="max-w-3xl mx-auto p-10">
      <h1 className="text-2xl font-semibold text-ss-navy mb-1">Upload a call transcript</h1>
      <p className="text-ss-navy-soft mb-6">
        Paste a transcript from Granola (or any tool with speaker labels).
        We accept transcripts only — not meeting notes or summaries.
      </p>

      <label className="block text-sm font-medium text-ss-navy mb-2">Call type</label>
      <div className="grid grid-cols-3 gap-2 mb-6">
        {CALL_TYPES.map((t) => (
          <button key={t.v}
            type="button"
            onClick={() => setCallType(t.v)}
            className={`p-3 border-2 rounded-lg text-sm font-medium transition
              ${callType === t.v
                ? "border-ss-navy bg-ss-cyan-soft text-ss-navy"
                : "border-ss-cyan-soft text-ss-navy-soft hover:border-ss-cyan-bright"}`}>
            {t.l}
          </button>
        ))}
      </div>

      <label className="block text-sm font-medium text-ss-navy mb-2">Prospect company</label>
      <input
        value={prospect} onChange={(e) => setProspect(e.target.value)}
        placeholder="e.g. NorthLane Fintech"
        className="w-full mb-6 px-4 py-2.5 border border-ss-cyan-soft rounded-lg
                   outline-none focus:ring-2 focus:ring-ss-cyan focus:border-ss-cyan-deep transition"
      />

      <label className="block text-sm font-medium text-ss-navy mb-2">Transcript</label>
      <textarea
        value={text} onChange={(e) => setText(e.target.value)}
        placeholder="Paste the full diarized transcript with speaker labels (Name: text). Minimum ~500 words, ≥2 speakers."
        className="w-full min-h-[240px] p-4 font-mono text-sm border-2 border-dashed border-ss-cyan-soft
                   rounded-lg outline-none focus:border-ss-cyan-deep focus:border-solid transition"
      />

      {result && (
        <div
          className={`mt-4 p-4 rounded-lg border ${
            result.accepted
              ? "bg-emerald-50 border-emerald-300 text-emerald-900"
              : "bg-red-50 border-red-300 text-red-900"
          }`}
        >
          <div className="font-semibold mb-1">
            {result.validation.title || result.message}
          </div>
          <div className="text-sm">
            {result.validation.detail || result.message}
          </div>
          {result.accepted && (
            <div className="text-xs mt-2 opacity-80 italic">
              Redirecting to the call page — analysis usually takes 30-90 seconds and refreshes automatically when ready.
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 rounded-lg border bg-red-50 border-red-300 text-red-900">
          <div className="font-semibold mb-1">Upload failed</div>
          <div className="text-sm break-words">{error}</div>
          <div className="text-xs mt-2 opacity-80 italic">
            Your transcript wasn't lost — just click <strong>Analyze</strong> again to retry. If it keeps failing, ping kaushik with the error above.
          </div>
        </div>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <button onClick={() => router.push("/dashboard")}
                className="px-5 py-2.5 border border-ss-cyan-soft text-ss-navy rounded-lg hover:bg-ss-cream transition">
          Cancel
        </button>
        <button onClick={submit} disabled={submitting || !text || !prospect}
                className="px-5 py-2.5 bg-ss-navy text-white rounded-lg font-semibold
                           hover:bg-ss-navy-dark transition disabled:opacity-50 disabled:cursor-not-allowed">
          {submitting ? "Analyzing…" : "Analyze →"}
        </button>
      </div>
    </main>
    </>
  );
}
