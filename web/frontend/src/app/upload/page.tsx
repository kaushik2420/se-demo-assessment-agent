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
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    const fd = new FormData();
    fd.append("call_type", callType);
    fd.append("prospect_company", prospect);
    fd.append("transcript", text);
    try {
      const r = await api<any>("/calls/upload", { method: "POST", body: fd });
      setResult(r);
      if (r.accepted && r.redirect) {
        setTimeout(() => router.push(r.redirect), 1500);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
    <TopNav />
    <main className="max-w-3xl mx-auto p-10">
      <h1 className="text-2xl font-semibold mb-1">Upload a call transcript</h1>
      <p className="text-slate-500 mb-6">We accept transcripts only — not meeting notes or summaries.</p>

      <label className="block text-sm font-medium mb-2">Call type</label>
      <div className="grid grid-cols-3 gap-2 mb-6">
        {CALL_TYPES.map((t) => (
          <button key={t.v}
            onClick={() => setCallType(t.v)}
            className={`p-3 border-2 rounded-lg text-sm font-medium transition
              ${callType === t.v ? "border-blue-600 bg-blue-50 text-blue-900" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
            {t.l}
          </button>
        ))}
      </div>

      <label className="block text-sm font-medium mb-2">Prospect company</label>
      <input value={prospect} onChange={(e) => setProspect(e.target.value)} placeholder="e.g. NorthLane Fintech"
             className="w-full mb-6 px-4 py-2.5 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-600" />

      <label className="block text-sm font-medium mb-2">Transcript</label>
      <textarea value={text} onChange={(e) => setText(e.target.value)}
                placeholder="Paste the full diarized transcript with speaker labels (Name: text). Minimum ~500 words, ≥2 speakers."
                className="w-full min-h-[240px] p-4 font-mono text-sm border-2 border-dashed border-slate-300 rounded-lg outline-none focus:border-blue-600 focus:border-solid" />

      {result && (
        <div className={`mt-4 p-4 rounded-lg border ${result.accepted ? "bg-emerald-50 border-emerald-300 text-emerald-900" : "bg-red-50 border-red-300 text-red-900"}`}>
          <div className="font-semibold mb-1">{result.validation.title || result.message}</div>
          <div className="text-sm">{result.validation.detail || result.message}</div>
        </div>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <button onClick={() => router.push("/dashboard")} className="px-5 py-2.5 border border-slate-300 rounded-lg">Cancel</button>
        <button onClick={submit} disabled={submitting || !text || !prospect}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg font-semibold disabled:opacity-50">
          {submitting ? "Validating…" : "Analyze →"}
        </button>
      </div>
    </main>
    </>
  );
}
